CREATE DATABASE sgr_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE sgr_db;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- 1. SEGURIDAD Y ORGANIZACIÓN (RF-001, RF-002, RNF-004, RNF-005) -> CU-09, CU-10
-- =============================================================================

-- Catálogo de roles del sistema (Administrador, Coordinador, Delegado, Funcionario,
-- Verificador, Usuario de Consulta), usados en el diagrama de caso de uso general.
CREATE TABLE rol (
    id_rol      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(60)  NOT NULL,
    descripcion VARCHAR(255) NULL,
    CONSTRAINT uq_rol_nombre UNIQUE (nombre)
) ENGINE=InnoDB;

-- Delegaciones o unidades organizacionales (RF-001) -> CU-09
CREATE TABLE delegacion (
    id_delegacion   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(120) NOT NULL,
    ambito          VARCHAR(120) NULL,
    estado          ENUM('activa', 'inactiva') NOT NULL DEFAULT 'activa',
    fecha_creacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_delegacion_nombre UNIQUE (nombre)
) ENGINE=InnoDB;

-- Cargos (RF-003) -> CU-15
CREATE TABLE cargo (
    id_cargo         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nombre           VARCHAR(100) NOT NULL,
    estado           ENUM('activo', 'inactivo') NOT NULL DEFAULT 'activo',
    vigencia_desde   DATE NOT NULL,
    vigencia_hasta   DATE NULL,
    CONSTRAINT uq_cargo_nombre UNIQUE (nombre),
    CONSTRAINT ck_cargo_vigencia CHECK (vigencia_hasta IS NULL OR vigencia_hasta >= vigencia_desde)
) ENGINE=InnoDB;

-- Usuarios / funcionarios del sistema (RF-002) -> CU-10
-- Un usuario representa a cualquier actor humano (Administrador, Coordinador,
-- Delegado, Funcionario o Verificador); el rol o roles se asignan en usuario_rol.
CREATE TABLE usuario (
    id_usuario          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    identificador_inst  VARCHAR(20)  NOT NULL,
    nombres             VARCHAR(100) NOT NULL,
    apellidos           VARCHAR(100) NOT NULL,
    email               VARCHAR(150) NOT NULL,
    password_hash       VARCHAR(255) NOT NULL,
    id_cargo            INT UNSIGNED NULL,
    id_delegacion       INT UNSIGNED NULL,
    estado              ENUM('activo', 'inactivo') NOT NULL DEFAULT 'activo',
    fecha_creacion      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_usuario_identificador UNIQUE (identificador_inst),
    CONSTRAINT uq_usuario_email UNIQUE (email),
    CONSTRAINT fk_usuario_cargo
        FOREIGN KEY (id_cargo) REFERENCES cargo (id_cargo)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_usuario_delegacion
        FOREIGN KEY (id_delegacion) REFERENCES delegacion (id_delegacion)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Responsable(s) de una delegación (referencia diferida a usuario)
ALTER TABLE delegacion
    ADD COLUMN id_responsable INT UNSIGNED NULL AFTER ambito,
    ADD CONSTRAINT fk_delegacion_responsable
        FOREIGN KEY (id_responsable) REFERENCES usuario (id_usuario)
        ON DELETE SET NULL ON UPDATE CASCADE;

-- Relación N:M usuario <-> rol (RF-002: "uno o más roles autorizados")
CREATE TABLE usuario_rol (
    id_usuario  INT UNSIGNED NOT NULL,
    id_rol      INT UNSIGNED NOT NULL,
    PRIMARY KEY (id_usuario, id_rol),
    CONSTRAINT fk_usuariorol_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_usuariorol_rol
        FOREIGN KEY (id_rol) REFERENCES rol (id_rol)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- 2. CATÁLOGOS Y CONFIGURACIÓN DE MEDICIÓN (RF-003 a RF-007) -> CU-15, CU-11
-- =============================================================================

-- Catálogo jerárquico de tipo de actividad / servicio / atención / subatención
-- por área (RF-004). id_padre permite anidar subatención -> atención -> servicio.
CREATE TABLE catalogo_tipo (
    id_catalogo   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    categoria     ENUM('actividad', 'servicio', 'atencion', 'subatencion') NOT NULL,
    nombre        VARCHAR(120) NOT NULL,
    codigo        VARCHAR(30)  NOT NULL,
    area          VARCHAR(80)  NULL,
    id_padre      INT UNSIGNED NULL,
    estado        ENUM('activo', 'inactivo') NOT NULL DEFAULT 'activo',
    CONSTRAINT uq_catalogo_codigo UNIQUE (codigo),
    CONSTRAINT fk_catalogo_padre
        FOREIGN KEY (id_padre) REFERENCES catalogo_tipo (id_catalogo)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Ítems medibles asociados a un cargo (RF-003)
CREATE TABLE item_medicion (
    id_item      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_cargo     INT UNSIGNED NOT NULL,
    nombre       VARCHAR(120) NOT NULL,
    tipo         ENUM('cuantitativo', 'porcentual') NOT NULL DEFAULT 'cuantitativo',
    unidad       VARCHAR(30)  NULL,
    formula_desc VARCHAR(255) NULL COMMENT 'Fórmula específica para ítems porcentuales (RN-002)',
    estado       ENUM('activo', 'inactivo') NOT NULL DEFAULT 'activo',
    CONSTRAINT fk_item_cargo
        FOREIGN KEY (id_cargo) REFERENCES cargo (id_cargo)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Períodos de medición (RF-005, RN-013) -> CU-15
CREATE TABLE periodo (
    id_periodo          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    fecha_inicio         DATE NOT NULL,
    fecha_termino         DATE NOT NULL,
    dias_computables      SMALLINT UNSIGNED NOT NULL,
    estado               ENUM('abierto', 'cerrado') NOT NULL DEFAULT 'abierto',
    version_parametros   INT UNSIGNED NOT NULL DEFAULT 1,
    fecha_creacion        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_periodo_fechas CHECK (fecha_termino >= fecha_inicio)
) ENGINE=InnoDB;

-- Metas, umbrales y ponderaciones por ítem/cargo/funcionario/período
-- (RF-006, RF-007, RN-001, RN-002) -> CU-11
-- Regla de negocio: al menos uno de (id_cargo, id_funcionario) debe estar
-- definido. Se valida a nivel de aplicación, ya que MariaDB no admite un
-- CHECK que combine dos columnas usadas como FOREIGN KEY (error 1901).
CREATE TABLE meta (
    id_meta            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_item            INT UNSIGNED NOT NULL,
    id_cargo           INT UNSIGNED NULL,
    id_funcionario     INT UNSIGNED NULL,
    id_periodo         INT UNSIGNED NOT NULL,
    valor_objetivo     DECIMAL(12,2) NOT NULL,
    unidad             VARCHAR(30) NULL,
    ponderador_pct     DECIMAL(5,2) NOT NULL,
    umbral_minimo_pct  DECIMAL(5,2) NOT NULL DEFAULT 80.00 COMMENT 'RN-006',
    maximo_computable_pct DECIMAL(5,2) NOT NULL DEFAULT 150.00 COMMENT 'RN-005',
    id_autor           INT UNSIGNED NOT NULL,
    fecha_registro     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    vigente            TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT ck_meta_valor_objetivo CHECK (valor_objetivo > 0),
    CONSTRAINT fk_meta_item
        FOREIGN KEY (id_item) REFERENCES item_medicion (id_item)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_meta_cargo
        FOREIGN KEY (id_cargo) REFERENCES cargo (id_cargo)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_meta_funcionario
        FOREIGN KEY (id_funcionario) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_meta_periodo
        FOREIGN KEY (id_periodo) REFERENCES periodo (id_periodo)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_meta_autor
        FOREIGN KEY (id_autor) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- 3. REGISTRO DE ACTIVIDADES Y EVIDENCIAS (RF-009 a RF-015) -> CU-01, CU-02,
--    CU-03, CU-04, CU-05, CU-06
-- =============================================================================

-- Actividades registradas por un funcionario (RF-009 a RF-011, RF-022, RN-003)
-- -> CU-01 (incluye CU-02 Generar Identificador de Evidencia y CU-06 Validar
-- Datos de Actividad, aplicados a nivel de aplicación/trigger antes del INSERT).
CREATE TABLE actividad (
    id_actividad        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    codigo_evidencia     CHAR(12) NOT NULL COMMENT 'Generado por CU-02, único e inmutable (RN-010)',
    id_funcionario      INT UNSIGNED NOT NULL,
    id_periodo          INT UNSIGNED NOT NULL,
    fecha_actividad      DATE NOT NULL,
    descripcion          VARCHAR(500) NOT NULL COMMENT 'Actividad / solicitud / problema atendido',
    accion               VARCHAR(255) NOT NULL,
    contacto_nombre      VARCHAR(150) NULL,
    contacto_telefono    VARCHAR(20) NULL,
    id_item             INT UNSIGNED NOT NULL,
    id_catalogo_tipo     INT UNSIGNED NULL,
    ingreso_agenda       TINYINT(1) NOT NULL DEFAULT 0,
    estado               ENUM('pendiente', 'validada', 'rechazada', 'en_correccion')
                         NOT NULL DEFAULT 'pendiente',
    fecha_registro       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_actividad_codigo UNIQUE (codigo_evidencia),
    CONSTRAINT fk_actividad_funcionario
        FOREIGN KEY (id_funcionario) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_actividad_periodo
        FOREIGN KEY (id_periodo) REFERENCES periodo (id_periodo)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_actividad_item
        FOREIGN KEY (id_item) REFERENCES item_medicion (id_item)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_actividad_catalogo
        FOREIGN KEY (id_catalogo_tipo) REFERENCES catalogo_tipo (id_catalogo)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_actividad_funcionario_periodo ON actividad (id_funcionario, id_periodo);
CREATE INDEX idx_actividad_estado ON actividad (estado);
CREATE INDEX idx_actividad_fecha ON actividad (fecha_actividad);

-- Evidencias adjuntas a una actividad (RF-012, RNF-017) -> CU-03
-- Relación 1:N con actividad (permite re-adjuntar tras una corrección, RN-010).
CREATE TABLE evidencia (
    id_evidencia    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_actividad    INT UNSIGNED NOT NULL,
    archivo_ruta    VARCHAR(255) NOT NULL,
    formato         VARCHAR(10)  NOT NULL,
    tamanio_bytes   INT UNSIGNED NOT NULL,
    id_autor        INT UNSIGNED NOT NULL,
    fecha_carga     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado          ENUM('pendiente', 'aprobada', 'rechazada', 'en_correccion')
                    NOT NULL DEFAULT 'pendiente',
    CONSTRAINT ck_evidencia_formato CHECK (formato IN ('jpg','jpeg','png','pdf')),
    CONSTRAINT ck_evidencia_tamanio CHECK (tamanio_bytes > 0 AND tamanio_bytes <= 5242880),
    CONSTRAINT fk_evidencia_actividad
        FOREIGN KEY (id_actividad) REFERENCES actividad (id_actividad)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_evidencia_autor
        FOREIGN KEY (id_autor) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_evidencia_actividad ON evidencia (id_actividad);

-- Validación de evidencias por un Verificador (RF-013, RF-014, RN-009) -> CU-04
-- (CU-05 Notificar Evidencia Rechazada se ejecuta a nivel de aplicación cuando
-- decision = 'rechazada', «extend» de este caso de uso).
CREATE TABLE validacion (
    id_validacion   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_evidencia    INT UNSIGNED NOT NULL,
    id_verificador  INT UNSIGNED NOT NULL,
    decision        ENUM('aprobada', 'rechazada', 'correccion') NOT NULL,
    observacion     VARCHAR(500) NULL,
    fecha           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_validacion_evidencia
        FOREIGN KEY (id_evidencia) REFERENCES evidencia (id_evidencia)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_validacion_verificador
        FOREIGN KEY (id_verificador) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_validacion_evidencia ON validacion (id_evidencia);

-- =============================================================================
-- 4. ATENCIÓN SOCIAL (RF-004, RF-015, RN-012) -> HU-03 del Product Backlog
-- =============================================================================

-- Persona usuaria atendida (datos mínimos y ficticios, RNF-009 / privacidad)
CREATE TABLE persona_usuaria (
    id_persona          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    referencia_anonima  VARCHAR(40) NOT NULL COMMENT 'Identificador ficticio, no dato real',
    fecha_registro      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_persona_referencia UNIQUE (referencia_anonima)
) ENGINE=InnoDB;

-- Hasta 3 gestiones/atenciones por persona usuaria (RN-012)
CREATE TABLE atencion_social (
    id_atencion       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_persona        INT UNSIGNED NOT NULL,
    id_actividad      INT UNSIGNED NULL,
    id_catalogo_tipo  INT UNSIGNED NOT NULL,
    id_funcionario    INT UNSIGNED NOT NULL,
    orden_gestion     TINYINT UNSIGNED NOT NULL COMMENT '1, 2 o 3 (RN-012)',
    fecha             DATE NOT NULL,
    resultado         VARCHAR(255) NULL,
    fecha_registro    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_atencion_orden CHECK (orden_gestion BETWEEN 1 AND 3),
    CONSTRAINT uq_atencion_persona_orden UNIQUE (id_persona, orden_gestion),
    CONSTRAINT fk_atencion_persona
        FOREIGN KEY (id_persona) REFERENCES persona_usuaria (id_persona)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_atencion_actividad
        FOREIGN KEY (id_actividad) REFERENCES actividad (id_actividad)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_atencion_catalogo
        FOREIGN KEY (id_catalogo_tipo) REFERENCES catalogo_tipo (id_catalogo)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_atencion_funcionario
        FOREIGN KEY (id_funcionario) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- 5. AGENDA COLECTIVA Y COMPROMISOS (RF-016 a RF-021) -> CU-07, CU-08
-- =============================================================================

CREATE TABLE compromiso (
    id_compromiso       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_actividad_origen  INT UNSIGNED NULL COMMENT 'Origen opcional desde CU-01 (A1)',
    id_delegacion       INT UNSIGNED NOT NULL,
    solicitante          VARCHAR(150) NOT NULL,
    territorio           VARCHAR(120) NULL,
    id_responsable       INT UNSIGNED NOT NULL,
    area_apoyo           VARCHAR(120) NULL,
    fecha_comprometida    DATE NOT NULL,
    estado               ENUM('ingresado', 'pendiente', 'en_proceso', 'realizado')
                         NOT NULL DEFAULT 'ingresado',
    observacion          VARCHAR(500) NULL,
    fecha_registro        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_compromiso_actividad
        FOREIGN KEY (id_actividad_origen) REFERENCES actividad (id_actividad)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_compromiso_delegacion
        FOREIGN KEY (id_delegacion) REFERENCES delegacion (id_delegacion)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_compromiso_responsable
        FOREIGN KEY (id_responsable) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_compromiso_estado ON compromiso (estado);
CREATE INDEX idx_compromiso_fecha ON compromiso (fecha_comprometida);

-- Historial de cambios de estado de un compromiso (RF-018) -> CU-08
CREATE TABLE compromiso_estado_historial (
    id_historial     INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_compromiso    INT UNSIGNED NOT NULL,
    estado_anterior  ENUM('ingresado', 'pendiente', 'en_proceso', 'realizado') NULL,
    estado_nuevo     ENUM('ingresado', 'pendiente', 'en_proceso', 'realizado') NOT NULL,
    id_autor         INT UNSIGNED NOT NULL,
    fecha            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observacion      VARCHAR(500) NULL,
    CONSTRAINT fk_cehist_compromiso
        FOREIGN KEY (id_compromiso) REFERENCES compromiso (id_compromiso)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cehist_autor
        FOREIGN KEY (id_autor) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- 6. INDICADORES, AJUSTES Y ALERTAS (RF-022 a RF-031, RF-037, RN-004 a RN-011)
--    -> CU-12, CU-16, CU-17, CU-14
-- =============================================================================

-- Indicador calculado por funcionario/meta/período (RF-022 a RF-027) -> CU-12
CREATE TABLE indicador (
    id_indicador             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_funcionario           INT UNSIGNED NOT NULL,
    id_meta                  INT UNSIGNED NOT NULL,
    avance_actual            DECIMAL(12,2) NOT NULL DEFAULT 0,
    cumplimiento_pct         DECIMAL(6,2)  NOT NULL DEFAULT 0 COMMENT 'RN-004',
    meta_esperada_dia_pct    DECIMAL(6,2)  NOT NULL DEFAULT 0 COMMENT 'RN-007',
    cumplimiento_ponderado   DECIMAL(6,2)  NOT NULL DEFAULT 0 COMMENT 'RN-005',
    semaforo                 ENUM('verde', 'ambar', 'rojo') NOT NULL DEFAULT 'rojo' COMMENT 'RN-008',
    fecha_calculo            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_indicador_func_meta UNIQUE (id_funcionario, id_meta),
    CONSTRAINT fk_indicador_funcionario
        FOREIGN KEY (id_funcionario) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_indicador_meta
        FOREIGN KEY (id_meta) REFERENCES meta (id_meta)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_indicador_semaforo ON indicador (semaforo);

-- Incentivos y penalizaciones (RF-025, RN-011)
CREATE TABLE ajuste_incentivo (
    id_ajuste       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_funcionario  INT UNSIGNED NOT NULL,
    id_periodo      INT UNSIGNED NOT NULL,
    tipo            ENUM('incentivo', 'penalizacion') NOT NULL,
    motivo          VARCHAR(255) NOT NULL,
    valor_pct       DECIMAL(6,2) NOT NULL,
    id_responsable  INT UNSIGNED NOT NULL,
    fecha           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ajuste_funcionario
        FOREIGN KEY (id_funcionario) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_ajuste_periodo
        FOREIGN KEY (id_periodo) REFERENCES periodo (id_periodo)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_ajuste_responsable
        FOREIGN KEY (id_responsable) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Reglas de alerta configurables (RF-037) -> CU-14
CREATE TABLE alerta_regla (
    id_regla        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tipo            ENUM('vencimiento_compromiso', 'evidencia_pendiente', 'avance_bajo_umbral')
                    NOT NULL,
    umbral          DECIMAL(6,2) NULL COMMENT 'Ej.: % de avance o días de anticipación',
    id_rol_destino  INT UNSIGNED NULL,
    activo          TINYINT(1) NOT NULL DEFAULT 1,
    id_autor        INT UNSIGNED NOT NULL,
    fecha_actualiza DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reglaalerta_rol
        FOREIGN KEY (id_rol_destino) REFERENCES rol (id_rol)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_reglaalerta_autor
        FOREIGN KEY (id_autor) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Alertas generadas (instancias) -> CU-14
CREATE TABLE alerta (
    id_alerta         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_regla          INT UNSIGNED NOT NULL,
    entidad_ref       VARCHAR(60)  NOT NULL COMMENT 'Tabla de origen, ej. compromiso, evidencia',
    id_entidad_ref    INT UNSIGNED NOT NULL,
    motivo            VARCHAR(255) NOT NULL,
    id_responsable    INT UNSIGNED NOT NULL,
    fecha_generada    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado            ENUM('pendiente', 'revisada') NOT NULL DEFAULT 'pendiente',
    fecha_revision    DATETIME NULL,
    CONSTRAINT fk_alerta_regla
        FOREIGN KEY (id_regla) REFERENCES alerta_regla (id_regla)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_alerta_responsable
        FOREIGN KEY (id_responsable) REFERENCES usuario (id_usuario)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_alerta_estado ON alerta (estado);

-- =============================================================================
-- 7. AUDITORÍA (RF-036, RNF-008) -> CU-13
-- =============================================================================

CREATE TABLE auditoria (
    id_auditoria    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_usuario      INT UNSIGNED NULL,
    fecha           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accion          ENUM('crear', 'modificar', 'eliminar', 'validar', 'cambiar_estado',
                         'acceso_denegado') NOT NULL,
    entidad         VARCHAR(60)  NOT NULL COMMENT 'Nombre de la tabla/entidad afectada',
    id_entidad      INT UNSIGNED NULL,
    valor_anterior  JSON NULL,
    valor_nuevo     JSON NULL,
    CONSTRAINT fk_auditoria_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_auditoria_entidad ON auditoria (entidad, id_entidad);
CREATE INDEX idx_auditoria_usuario_fecha ON auditoria (id_usuario, fecha);

todas esas?