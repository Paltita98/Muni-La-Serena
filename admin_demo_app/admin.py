from django.contrib import admin
from .forms import UsuarioForm
from .models import (
    AjusteIncentivo,
    Alerta,
    AlertaRegla,
    Actividad,
    AtencionSocial,
    Auditoria,
    Cargo,
    CatalogoTipo,
    Compromiso,
    CompromisoEstadoHistorial,
    Delegacion,
    Evidencia,
    Indicador,
    ItemMedicion,
    Meta,
    Periodo,
    PersonaUsuaria,
    Rol,
    Usuario,
    Validacion,
)

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estado', 'vigencia_desde', 'vigencia_hasta')
    list_filter = ('estado',)
    search_fields = ('nombre',)
    exclude = ('vigencia_desde', 'vigencia_hasta')

@admin.register(Delegacion)
class DelegacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estado', 'responsable', 'fecha_creacion')
    list_filter = ('estado',)
    search_fields = ('nombre', 'ambito')

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    form = UsuarioForm
    list_display = ('identificador_inst', 'nombres', 'apellidos', 'email', 'cargo', 'delegacion', 'estado')
    list_filter = ('estado', 'cargo', 'delegacion')
    search_fields = ('identificador_inst', 'nombres', 'apellidos', 'email')
    filter_horizontal = ('roles',) # Crea una interfaz visual mejorada para la relación de roles

@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ('fecha_inicio', 'fecha_termino', 'dias_computables', 'estado')
    list_filter = ('estado',)
    search_fields = ('fecha_inicio', 'fecha_termino')

@admin.register(ItemMedicion)
class ItemMedicionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cargo', 'tipo', 'estado')
    list_filter = ('tipo', 'estado', 'cargo')
    search_fields = ('nombre',)


@admin.register(CatalogoTipo)
class CatalogoTipoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria', 'area', 'padre', 'estado')
    list_filter = ('categoria', 'estado', 'area')
    search_fields = ('codigo', 'nombre', 'area')


@admin.register(Meta)
class MetaAdmin(admin.ModelAdmin):
    list_display = ('item', 'cargo', 'funcionario', 'periodo', 'valor_objetivo', 'vigente')
    list_filter = ('vigente', 'periodo', 'cargo')
    search_fields = ('item__nombre', 'funcionario__nombres', 'funcionario__apellidos')
    autocomplete_fields = ('item', 'cargo', 'funcionario', 'periodo', 'autor')

@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ('codigo_evidencia', 'funcionario', 'fecha_actividad', 'item', 'catalogo_tipo', 'estado')
    list_filter = ('estado', 'ingreso_agenda', 'periodo')
    search_fields = ('codigo_evidencia', 'descripcion', 'funcionario__nombres', 'funcionario__identificador_inst')

@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = ('actividad', 'formato', 'autor', 'fecha_carga', 'estado')
    list_filter = ('estado', 'formato')
    search_fields = ('actividad__codigo_evidencia',)


@admin.register(Validacion)
class ValidacionAdmin(admin.ModelAdmin):
    list_display = ('evidencia', 'verificador', 'decision', 'fecha')
    list_filter = ('decision', 'fecha')
    search_fields = ('evidencia__actividad__codigo_evidencia', 'verificador__nombres')
    autocomplete_fields = ('evidencia', 'verificador')


@admin.register(PersonaUsuaria)
class PersonaUsuariaAdmin(admin.ModelAdmin):
    list_display = ('referencia_anonima', 'fecha_registro')
    search_fields = ('referencia_anonima',)


@admin.register(AtencionSocial)
class AtencionSocialAdmin(admin.ModelAdmin):
    list_display = ('persona', 'orden_gestion', 'fecha', 'funcionario', 'catalogo_tipo')
    list_filter = ('orden_gestion', 'fecha', 'catalogo_tipo')
    search_fields = ('persona__referencia_anonima', 'resultado', 'funcionario__nombres')
    autocomplete_fields = ('persona', 'actividad', 'catalogo_tipo', 'funcionario')


@admin.register(Compromiso)
class CompromisoAdmin(admin.ModelAdmin):
    list_display = ('solicitante', 'delegacion', 'responsable', 'fecha_comprometida', 'estado')
    list_filter = ('estado', 'delegacion', 'fecha_comprometida')
    search_fields = ('solicitante', 'territorio', 'observacion')
    autocomplete_fields = ('actividad_origen', 'delegacion', 'responsable')


@admin.register(CompromisoEstadoHistorial)
class CompromisoEstadoHistorialAdmin(admin.ModelAdmin):
    list_display = ('compromiso', 'estado_anterior', 'estado_nuevo', 'autor', 'fecha')
    list_filter = ('estado_nuevo', 'fecha')
    search_fields = ('compromiso__solicitante', 'autor__nombres')
    autocomplete_fields = ('compromiso', 'autor')


@admin.register(Indicador)
class IndicadorAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'meta', 'avance_actual', 'cumplimiento_pct', 'semaforo', 'fecha_calculo')
    list_filter = ('semaforo', 'fecha_calculo')
    search_fields = ('funcionario__nombres', 'funcionario__apellidos', 'meta__item__nombre')
    autocomplete_fields = ('funcionario', 'meta')


@admin.register(AjusteIncentivo)
class AjusteIncentivoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'periodo', 'tipo', 'valor_pct', 'responsable', 'fecha')
    list_filter = ('tipo', 'periodo', 'fecha')
    search_fields = ('funcionario__nombres', 'funcionario__apellidos', 'motivo')
    autocomplete_fields = ('funcionario', 'periodo', 'responsable')


@admin.register(AlertaRegla)
class AlertaReglaAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'umbral', 'rol_destino', 'activo', 'autor', 'fecha_actualiza')
    list_filter = ('tipo', 'activo', 'rol_destino')
    search_fields = ('tipo', 'autor__nombres')
    autocomplete_fields = ('rol_destino', 'autor')


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ('regla', 'entidad_ref', 'motivo', 'responsable', 'estado', 'fecha_generada')
    list_filter = ('estado', 'entidad_ref', 'fecha_generada')
    search_fields = ('entidad_ref', 'motivo', 'responsable__nombres')
    autocomplete_fields = ('regla', 'responsable')


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'accion', 'entidad', 'id_entidad')
    list_filter = ('accion', 'entidad', 'fecha')
    search_fields = ('entidad', 'usuario__nombres', 'usuario__apellidos')
    autocomplete_fields = ('usuario',)
    readonly_fields = ('fecha',)