from django.db import models
from django.utils import timezone

# =============================================================================
# 1. SEGURIDAD Y ORGANIZACIÓN
# =============================================================================

class Rol(models.Model):
    nombre = models.CharField(max_length=60, unique=True, verbose_name="Nombre del Rol")
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.nombre


class Cargo(models.Model):
    ESTADO_CHOICES = [('activo', 'Activo'), ('inactivo', 'Inactivo')]
    
    nombre = models.CharField(max_length=100, unique=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='activo')
    vigencia_desde = models.DateField(blank=True, null=True)
    vigencia_hasta = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"

    def __str__(self):
        return self.nombre


class Delegacion(models.Model):
    ESTADO_CHOICES = [('activa', 'Activa'), ('inactiva', 'Inactiva')]
    
    nombre = models.CharField(max_length=120, unique=True)
    ambito = models.CharField(max_length=120, blank=True, null=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    # Relación diferida con Usuario usando cadena de texto para evitar errores circulares
    responsable = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='delegaciones_a_cargo')

    class Meta:
        verbose_name = "Delegación"
        verbose_name_plural = "Delegaciones"

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    ESTADO_CHOICES = [('activo', 'Activo'), ('inactivo', 'Inactivo')]
    
    identificador_inst = models.CharField(max_length=20, unique=True, verbose_name="Identificador (RUT/ID)")
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    email = models.EmailField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255) # En un entorno real se usa la auth nativa de Django
    cargo = models.ForeignKey(Cargo, on_delete=models.SET_NULL, null=True, blank=True)
    delegacion = models.ForeignKey(Delegacion, on_delete=models.SET_NULL, null=True, blank=True)
    roles = models.ManyToManyField(Rol, related_name='usuarios') # Reemplaza la tabla intermedia usuario_rol
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Usuario Funcionario"
        verbose_name_plural = "Usuarios Funcionarios"

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.identificador_inst})"


# =============================================================================
# 2. CATÁLOGOS Y CONFIGURACIÓN
# =============================================================================

class Periodo(models.Model):
    ESTADO_CHOICES = [('abierto', 'Abierto'), ('cerrado', 'Cerrado')]
    
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField()
    dias_computables = models.PositiveSmallIntegerField()
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='abierto')
    version_parametros = models.PositiveIntegerField(default=1)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Período de Medición"
        verbose_name_plural = "Períodos de Medición"

    def __str__(self):
        return f"Período {self.fecha_inicio} al {self.fecha_termino}"


class ItemMedicion(models.Model):
    TIPO_CHOICES = [('cuantitativo', 'Cuantitativo'), ('porcentual', 'Porcentual')]
    ESTADO_CHOICES = [('activo', 'Activo'), ('inactivo', 'Inactivo')]

    cargo = models.ForeignKey(Cargo, on_delete=models.RESTRICT)
    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='cuantitativo')
    unidad = models.CharField(max_length=30, blank=True, null=True)
    formula_desc = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='activo')

    class Meta:
        verbose_name = "Ítem de Medición"
        verbose_name_plural = "Ítems de Medición"

    def __str__(self):
        return f"{self.nombre} ({self.cargo.nombre})"


# =============================================================================
# 3. REGISTRO DE ACTIVIDADES Y EVIDENCIAS
# =============================================================================

class Actividad(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'), 
        ('validada', 'Validada'), 
        ('rechazada', 'Rechazada'), 
        ('en_correccion', 'En Corrección')
    ]
    
    codigo_evidencia = models.CharField(max_length=12, unique=True)
    funcionario = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    periodo = models.ForeignKey(Periodo, on_delete=models.RESTRICT)
    fecha_actividad = models.DateField()
    descripcion = models.CharField(max_length=500)
    accion = models.CharField(max_length=255)
    contacto_nombre = models.CharField(max_length=150, blank=True, null=True)
    contacto_telefono = models.CharField(max_length=20, blank=True, null=True)
    item = models.ForeignKey(ItemMedicion, on_delete=models.RESTRICT)
    catalogo_tipo = models.ForeignKey(
        'CatalogoTipo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='actividades',
    )
    ingreso_agenda = models.BooleanField(default=False)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Actividad Registrada"
        verbose_name_plural = "Actividades Registradas"

    def __str__(self):
        return f"ACT {self.codigo_evidencia} - {self.funcionario.apellidos}"

class Evidencia(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'), 
        ('aprobada', 'Aprobada'), 
        ('rechazada', 'Rechazada'), 
        ('en_correccion', 'En Corrección')
    ]

    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE, related_name='evidencias')
    archivo = models.FileField(upload_to='evidencias/%Y/%m/') # Django maneja la ruta y el archivo físico
    formato = models.CharField(max_length=10)
    tamanio_bytes = models.PositiveIntegerField()
    autor = models.ForeignKey(Usuario, on_delete=models.RESTRICT)
    fecha_carga = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')

    class Meta:
        verbose_name = "Evidencia Adjunta"
        verbose_name_plural = "Evidencias Adjuntas"

    def __str__(self):
        return f"Evidencia de {self.actividad.codigo_evidencia}"


class CatalogoTipo(models.Model):
    CATEGORIA_CHOICES = [
        ('actividad', 'Actividad'),
        ('servicio', 'Servicio'),
        ('atencion', 'Atención'),
        ('subatencion', 'Subatención'),
    ]
    ESTADO_CHOICES = [('activo', 'Activo'), ('inactivo', 'Inactivo')]

    categoria = models.CharField(max_length=15, choices=CATEGORIA_CHOICES)
    nombre = models.CharField(max_length=120)
    codigo = models.CharField(max_length=30, unique=True)
    area = models.CharField(max_length=80, blank=True, null=True)
    padre = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hijos',
    )
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='activo')

    class Meta:
        verbose_name = 'Tipo de Catálogo'
        verbose_name_plural = 'Tipos de Catálogo'

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class Meta(models.Model):
    item = models.ForeignKey(ItemMedicion, on_delete=models.RESTRICT)
    cargo = models.ForeignKey(Cargo, on_delete=models.RESTRICT, null=True, blank=True)
    funcionario = models.ForeignKey(
        Usuario, on_delete=models.RESTRICT, null=True, blank=True,
        related_name='metas_asignadas',
    )
    periodo = models.ForeignKey(Periodo, on_delete=models.RESTRICT)
    valor_objetivo = models.DecimalField(max_digits=12, decimal_places=2)
    unidad = models.CharField(max_length=30, blank=True, null=True)
    ponderador_pct = models.DecimalField(max_digits=5, decimal_places=2)
    umbral_minimo_pct = models.DecimalField(max_digits=5, decimal_places=2, default=80.00)
    maximo_computable_pct = models.DecimalField(max_digits=5, decimal_places=2, default=150.00)
    autor = models.ForeignKey(
        Usuario, on_delete=models.RESTRICT, related_name='metas_creadas',
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    vigente = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Meta'
        verbose_name_plural = 'Metas'
        constraints = [
            models.CheckConstraint(
                check=models.Q(valor_objetivo__gt=0),
                name='meta_valor_objetivo_positivo',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.cargo_id and not self.funcionario_id:
            raise ValidationError('La meta debe asociarse a un cargo o a un funcionario.')

    def __str__(self):
        return f'Meta de {self.item}'


class Validacion(models.Model):
    DECISION_CHOICES = [
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
        ('correccion', 'En corrección'),
    ]

    evidencia = models.ForeignKey(Evidencia, on_delete=models.CASCADE, related_name='validaciones')
    verificador = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='validaciones_realizadas')
    decision = models.CharField(max_length=10, choices=DECISION_CHOICES)
    observacion = models.CharField(max_length=500, blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Validación'
        verbose_name_plural = 'Validaciones'

    def __str__(self):
        return f'{self.evidencia} - {self.get_decision_display()}'


class PersonaUsuaria(models.Model):
    referencia_anonima = models.CharField(max_length=40, unique=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Persona Usuaria'
        verbose_name_plural = 'Personas Usuarias'

    def __str__(self):
        return self.referencia_anonima


class AtencionSocial(models.Model):
    persona = models.ForeignKey(PersonaUsuaria, on_delete=models.RESTRICT, related_name='atenciones')
    actividad = models.ForeignKey(Actividad, on_delete=models.SET_NULL, null=True, blank=True)
    catalogo_tipo = models.ForeignKey(CatalogoTipo, on_delete=models.RESTRICT)
    funcionario = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='atenciones_sociales')
    orden_gestion = models.PositiveSmallIntegerField()
    fecha = models.DateField()
    resultado = models.CharField(max_length=255, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Atención Social'
        verbose_name_plural = 'Atenciones Sociales'
        constraints = [
            models.UniqueConstraint(fields=('persona', 'orden_gestion'), name='atencion_persona_orden_unico'),
            models.CheckConstraint(check=models.Q(orden_gestion__gte=1, orden_gestion__lte=3), name='atencion_orden_valido'),
        ]

    def __str__(self):
        return f'{self.persona} - Gestión {self.orden_gestion}'


class Compromiso(models.Model):
    ESTADO_CHOICES = [
        ('ingresado', 'Ingresado'), ('pendiente', 'Pendiente'),
        ('en_proceso', 'En proceso'), ('realizado', 'Realizado'),
    ]

    actividad_origen = models.ForeignKey(Actividad, on_delete=models.SET_NULL, null=True, blank=True)
    delegacion = models.ForeignKey(Delegacion, on_delete=models.RESTRICT, related_name='compromisos')
    solicitante = models.CharField(max_length=150)
    territorio = models.CharField(max_length=120, blank=True, null=True)
    responsable = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='compromisos_responsable')
    area_apoyo = models.CharField(max_length=120, blank=True, null=True)
    fecha_comprometida = models.DateField()
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='ingresado')
    observacion = models.CharField(max_length=500, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Compromiso'
        verbose_name_plural = 'Compromisos'

    def __str__(self):
        return f'{self.solicitante} - {self.fecha_comprometida}'


class CompromisoEstadoHistorial(models.Model):
    ESTADO_CHOICES = Compromiso.ESTADO_CHOICES

    compromiso = models.ForeignKey(Compromiso, on_delete=models.CASCADE, related_name='historial_estados')
    estado_anterior = models.CharField(max_length=12, choices=ESTADO_CHOICES, null=True, blank=True)
    estado_nuevo = models.CharField(max_length=12, choices=ESTADO_CHOICES)
    autor = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='cambios_compromisos')
    fecha = models.DateTimeField(auto_now_add=True)
    observacion = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        verbose_name = 'Historial de Estado de Compromiso'
        verbose_name_plural = 'Historial de Estados de Compromisos'


class Indicador(models.Model):
    SEMAFORO_CHOICES = [('verde', 'Verde'), ('ambar', 'Ámbar'), ('rojo', 'Rojo')]

    funcionario = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='indicadores')
    meta = models.ForeignKey(Meta, on_delete=models.RESTRICT, related_name='indicadores')
    avance_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cumplimiento_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    meta_esperada_dia_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cumplimiento_ponderado = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    semaforo = models.CharField(max_length=5, choices=SEMAFORO_CHOICES, default='rojo')
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Indicador'
        verbose_name_plural = 'Indicadores'
        constraints = [models.UniqueConstraint(fields=('funcionario', 'meta'), name='indicador_funcionario_meta_unico')]


class AjusteIncentivo(models.Model):
    TIPO_CHOICES = [('incentivo', 'Incentivo'), ('penalizacion', 'Penalización')]

    funcionario = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='ajustes_recibidos')
    periodo = models.ForeignKey(Periodo, on_delete=models.RESTRICT)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)
    motivo = models.CharField(max_length=255)
    valor_pct = models.DecimalField(max_digits=6, decimal_places=2)
    responsable = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='ajustes_autorizados')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ajuste de Incentivo'
        verbose_name_plural = 'Ajustes de Incentivos'


class AlertaRegla(models.Model):
    TIPO_CHOICES = [
        ('vencimiento_compromiso', 'Vencimiento de compromiso'),
        ('evidencia_pendiente', 'Evidencia pendiente'),
        ('avance_bajo_umbral', 'Avance bajo umbral'),
    ]

    tipo = models.CharField(max_length=25, choices=TIPO_CHOICES)
    umbral = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    rol_destino = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True)
    activo = models.BooleanField(default=True)
    autor = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='reglas_alerta_creadas')
    fecha_actualiza = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Regla de Alerta'
        verbose_name_plural = 'Reglas de Alertas'


class Alerta(models.Model):
    ESTADO_CHOICES = [('pendiente', 'Pendiente'), ('revisada', 'Revisada')]

    regla = models.ForeignKey(AlertaRegla, on_delete=models.RESTRICT, related_name='alertas')
    entidad_ref = models.CharField(max_length=60)
    id_entidad_ref = models.PositiveIntegerField()
    motivo = models.CharField(max_length=255)
    responsable = models.ForeignKey(Usuario, on_delete=models.RESTRICT, related_name='alertas_recibidas')
    fecha_generada = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=9, choices=ESTADO_CHOICES, default='pendiente')
    fecha_revision = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Alerta'
        verbose_name_plural = 'Alertas'


class Auditoria(models.Model):
    ACCION_CHOICES = [
        ('crear', 'Crear'), ('modificar', 'Modificar'), ('eliminar', 'Eliminar'),
        ('validar', 'Validar'), ('cambiar_estado', 'Cambiar estado'),
        ('acceso_denegado', 'Acceso denegado'),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='auditorias')
    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=16, choices=ACCION_CHOICES)
    entidad = models.CharField(max_length=60)
    id_entidad = models.PositiveIntegerField(null=True, blank=True)
    valor_anterior = models.JSONField(null=True, blank=True)
    valor_nuevo = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'
        indexes = [models.Index(fields=('entidad', 'id_entidad'))]