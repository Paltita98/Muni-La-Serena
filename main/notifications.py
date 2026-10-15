from django.db.models import Q

from admin_demo_app.models import Notificacion, Usuario


def notificar(destinatario_id, mensaje, tipo='sistema', url='', actor_id=None):
    if not destinatario_id:
        return None
    return Notificacion.objects.create(
        destinatario_id=destinatario_id,
        actor_id=actor_id,
        tipo=tipo,
        mensaje=mensaje[:500],
        url=url[:255],
    )


def notificar_administradores(actor_id, mensaje, tipo='administracion', url=''):
    administradores = Usuario.objects.filter(
        estado='activo',
        roles__nombre__icontains='admin',
    ).distinct().values_list('pk', flat=True)
    return [
        notificar(admin_id, mensaje, tipo=tipo, url=url, actor_id=actor_id)
        for admin_id in administradores
    ]


def notificar_accion_funcionario(funcionario_id, mensaje, url, tipo='actividad'):
    notificar_administradores(funcionario_id, mensaje, tipo=tipo, url=url)


def notificar_asignados_meta(meta, actor_id, mensaje):
    if meta.funcionario_id:
        destinatarios = Usuario.objects.filter(pk=meta.funcionario_id, estado='activo')
    elif meta.cargo_id:
        destinatarios = Usuario.objects.filter(cargo_id=meta.cargo_id, estado='activo')
    else:
        destinatarios = Usuario.objects.none()
    for destinatario_id in destinatarios.values_list('pk', flat=True):
        notificar(
            destinatario_id,
            mensaje,
            tipo='administracion',
            url='/funcionario/panel/',
            actor_id=actor_id,
        )


def notificar_usuarios_delegacion(delegacion, actor_id, mensaje):
    usuarios = Usuario.objects.filter(estado='activo').filter(
        Q(delegacion_id=delegacion.pk) | Q(delegaciones_autorizadas__pk=delegacion.pk),
    ).distinct()
    for destinatario_id in usuarios.values_list('pk', flat=True):
        notificar(
            destinatario_id,
            mensaje,
            tipo='administracion',
            url='/funcionario/panel/',
            actor_id=actor_id,
        )


def notificar_usuarios_cargo(cargo_id, actor_id, mensaje, url='/funcionario/panel/'):
    usuarios = Usuario.objects.filter(cargo_id=cargo_id, estado='activo')
    for destinatario_id in usuarios.values_list('pk', flat=True):
        notificar(
            destinatario_id,
            mensaje,
            tipo='administracion',
            url=url,
            actor_id=actor_id,
        )


def notificar_usuarios_rol(rol_id, actor_id, mensaje):
    usuarios = Usuario.objects.filter(roles__pk=rol_id, estado='activo').distinct()
    for destinatario_id in usuarios.values_list('pk', flat=True):
        notificar(
            destinatario_id,
            mensaje,
            tipo='administracion',
            url='/funcionario/panel/',
            actor_id=actor_id,
        )
