from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import UsuarioForm
from .models import Auditoria, Compromiso, Delegacion, Meta, Periodo, Usuario, Alerta


def admin_dashboard_view(request):
    periodo = Periodo.objects.filter(estado='abierto').order_by('-fecha_inicio').first()
    delegaciones_dashboard = list(
        Delegacion.objects.filter(estado='activa').order_by('nombre')[:5]
    )
    for delegacion in delegaciones_dashboard:
        delegacion.funcionarios_count = Usuario.objects.filter(
            delegacion=delegacion,
            estado='activo',
        ).count()
        delegacion.compromisos_count = Compromiso.objects.filter(delegacion=delegacion).count()

    return render(request, 'admin_demo_app/admin_demo.html', {
        'usuarios_activos': Usuario.objects.filter(estado='activo').count(),
        'delegaciones_activas': Delegacion.objects.filter(estado='activa').count(),
        'alertas_pendientes': Alerta.objects.filter(estado='pendiente').count(),
        'periodo_actual': periodo,
        'auditorias_recientes': Auditoria.objects.select_related('usuario').order_by('-fecha')[:5],
        'delegaciones_dashboard': delegaciones_dashboard,
    })


def admin_demo_view(request):
    return admin_dashboard_view(request)


def admin_nuevo_usuario_view(request):
    return gestionar_usuario_view(request)


def admin_usuarios_view(request):
    usuarios = Usuario.objects.prefetch_related('roles').select_related('cargo', 'delegacion')
    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        usuarios = usuarios.filter(
            Q(nombres__icontains=busqueda)
            | Q(apellidos__icontains=busqueda)
            | Q(identificador_inst__icontains=busqueda)
            | Q(email__icontains=busqueda)
        )
    return render(request, 'admin_demo_app/usuarios_roles.html', {
        'usuarios': usuarios,
        'busqueda': busqueda,
    })


def admin_delegaciones_view(request):
    delegaciones = Delegacion.objects.filter(estado='activa').select_related('responsable').prefetch_related('compromisos')
    for delegacion in delegaciones:
        delegacion.funcionarios_count = Usuario.objects.filter(delegacion=delegacion, estado='activo').count()
        delegacion.compromisos_count = Compromiso.objects.filter(delegacion=delegacion).count()
    return render(request, 'admin_demo_app/delegaciones.html', {'delegaciones': delegaciones})


def admin_catalogos_view(request):
    return render(request, 'admin_demo_app/catalogos_metas.html', {
        'periodos': Periodo.objects.order_by('-fecha_inicio'),
        'metas': Meta.objects.select_related('item', 'cargo', 'funcionario', 'periodo').order_by('-fecha_registro'),
    })


def admin_auditoria_view(request):
    auditorias = Auditoria.objects.select_related('usuario').order_by('-fecha')
    accion = request.GET.get('accion', '').strip()
    usuario = request.GET.get('usuario', '').strip()
    if accion:
        auditorias = auditorias.filter(accion=accion)
    if usuario:
        auditorias = auditorias.filter(
            Q(usuario__identificador_inst__icontains=usuario)
            | Q(usuario__nombres__icontains=usuario)
            | Q(usuario__apellidos__icontains=usuario)
        )
    return render(request, 'admin_demo_app/auditoria_sistema.html', {
        'auditorias': auditorias[:100],
        'accion_seleccionada': accion,
        'usuario_filtro': usuario,
    })


def nueva_delegacion_view(request):
    return render(request, 'admin_demo_app/delegaciones.html')


def nuevo_usuario_view(request):
    return gestionar_usuario_view(request)


def gestionar_usuario_view(request, usuario_id=None):
    usuario = get_object_or_404(Usuario, pk=usuario_id) if usuario_id else None
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            usuario = form.save()
            messages.success(request, f'Usuario {usuario.nombres} {usuario.apellidos} guardado correctamente.')
            return redirect('admin_usuarios_view')
    else:
        form = UsuarioForm(instance=usuario)

    return render(request, 'admin_demo_app/nuevo_usuario.html', {
        'form': form,
        'usuario': usuario,
        'modo_edicion': usuario is not None,
    })


def editar_usuario_view(request, usuario_id):
    return gestionar_usuario_view(request, usuario_id)
