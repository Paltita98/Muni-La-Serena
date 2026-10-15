from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CatalogoTipoForm, DelegacionForm, ItemMedicionForm, MetaForm, RolForm, UsuarioForm
from .models import Auditoria, CatalogoTipo, Compromiso, Delegacion, ItemMedicion, Meta, Periodo, Rol, Usuario, Alerta


def _admin_access(request):
    if request.session.get('user_role') != 'ADMIN':
        return redirect('main:login_view')
    return None


def _manage_record(request, model, form_class, title, success_url, record_id=None):
    denied = _admin_access(request)
    if denied:
        return denied
    record = get_object_or_404(model, pk=record_id) if record_id else None
    if request.method == 'POST':
        form = form_class(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, f'{title} guardado correctamente.')
            return redirect(success_url)
    else:
        form = form_class(instance=record)
    return render(request, 'admin_demo_app/registro_admin.html', {
        'form': form,
        'titulo': f'Editar {title.lower()}' if record else f'Nuevo {title.lower()}',
        'url_cancelar': success_url,
    })


def _delete_record(request, model, success_url):
    denied = _admin_access(request)
    if denied:
        return denied
    if request.method == 'POST':
        record = get_object_or_404(model, pk=request.POST.get('record_id'))
        try:
            record.delete()
        except ProtectedError:
            messages.error(request, 'No se puede eliminar porque existen registros relacionados.')
        else:
            messages.success(request, 'Registro eliminado correctamente.')
    return redirect(success_url)


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
    if request.session.get('user_role') != 'ADMIN':
        return redirect('main:login_view')
    return admin_dashboard_view(request)


def admin_nuevo_usuario_view(request):
    return gestionar_usuario_view(request)


def admin_usuarios_view(request):
    denied = _admin_access(request)
    if denied:
        return denied
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
    denied = _admin_access(request)
    if denied:
        return denied
    delegaciones = Delegacion.objects.select_related('responsable').prefetch_related('compromisos').order_by('nombre')
    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        delegaciones = delegaciones.filter(Q(nombre__icontains=busqueda) | Q(codigo__icontains=busqueda) | Q(comuna__icontains=busqueda))
    for delegacion in delegaciones:
        delegacion.funcionarios_count = Usuario.objects.filter(delegacion=delegacion, estado='activo').count()
        delegacion.compromisos_count = Compromiso.objects.filter(delegacion=delegacion).count()
    return render(request, 'admin_demo_app/delegaciones.html', {'delegaciones': delegaciones, 'busqueda': busqueda})


def admin_catalogos_view(request):
    denied = _admin_access(request)
    if denied:
        return denied
    return render(request, 'admin_demo_app/catalogos_metas.html', {
        'periodos': Periodo.objects.order_by('-fecha_inicio'),
        'metas': Meta.objects.select_related('item', 'cargo', 'funcionario', 'periodo').order_by('-fecha_registro'),
        'items': ItemMedicion.objects.select_related('cargo').order_by('nombre'),
        'roles': Rol.objects.order_by('nombre'),
        'catalogos_atencion': CatalogoTipo.objects.filter(categoria__in=('atencion', 'subatencion')).order_by('categoria', 'nombre'),
    })


def admin_auditoria_view(request):
    denied = _admin_access(request)
    if denied:
        return denied
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
    return _manage_record(request, Delegacion, DelegacionForm, 'Delegación', 'admin_delegaciones_view')


def editar_delegacion_view(request, delegacion_id):
    return _manage_record(request, Delegacion, DelegacionForm, 'Delegación', 'admin_delegaciones_view', delegacion_id)


def eliminar_delegacion_view(request):
    return _delete_record(request, Delegacion, 'admin_delegaciones_view')


def nuevo_rol_view(request):
    return _manage_record(request, Rol, RolForm, 'Rol', 'admin_catalogos_view')


def editar_rol_view(request, rol_id):
    return _manage_record(request, Rol, RolForm, 'Rol', 'admin_catalogos_view', rol_id)


def eliminar_rol_view(request):
    return _delete_record(request, Rol, 'admin_catalogos_view')


def nuevo_item_view(request):
    return _manage_record(request, ItemMedicion, ItemMedicionForm, 'Ítem', 'admin_catalogos_view')


def editar_item_view(request, item_id):
    return _manage_record(request, ItemMedicion, ItemMedicionForm, 'Ítem', 'admin_catalogos_view', item_id)


def eliminar_item_view(request):
    return _delete_record(request, ItemMedicion, 'admin_catalogos_view')


def gestionar_meta_view(request, meta_id=None):
    denied = _admin_access(request)
    if denied:
        return denied
    meta = get_object_or_404(Meta, pk=meta_id) if meta_id else None
    if request.method == 'POST':
        form = MetaForm(request.POST, instance=meta)
        if form.is_valid():
            meta = form.save(commit=False)
            if not meta.pk:
                meta.autor = get_object_or_404(Usuario, pk=request.session.get('user_id'), estado='activo')
            meta.save()
            messages.success(request, 'Meta guardada correctamente.')
            return redirect('admin_catalogos_view')
    else:
        form = MetaForm(instance=meta)
    return render(request, 'admin_demo_app/registro_admin.html', {
        'form': form,
        'titulo': 'Editar meta' if meta else 'Nueva meta',
        'url_cancelar': 'admin_catalogos_view',
    })


def nueva_meta_view(request):
    return gestionar_meta_view(request)


def editar_meta_view(request, meta_id):
    return gestionar_meta_view(request, meta_id)


def eliminar_meta_view(request):
    return _delete_record(request, Meta, 'admin_catalogos_view')


def nuevo_catalogo_atencion_view(request):
    return _manage_record(request, CatalogoTipo, CatalogoTipoForm, 'Tipo o subatención', 'admin_catalogos_view')


def editar_catalogo_atencion_view(request, catalogo_id):
    return _manage_record(request, CatalogoTipo, CatalogoTipoForm, 'Tipo o subatención', 'admin_catalogos_view', catalogo_id)


def eliminar_catalogo_atencion_view(request):
    return _delete_record(request, CatalogoTipo, 'admin_catalogos_view')


def nuevo_usuario_view(request):
    return gestionar_usuario_view(request)


def gestionar_usuario_view(request, usuario_id=None):
    denied = _admin_access(request)
    if denied:
        return denied
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


def eliminar_usuario_view(request):
    denied = _admin_access(request)
    if denied:
        return denied
    if request.method == 'POST':
        usuario = get_object_or_404(Usuario, pk=request.POST.get('record_id'))
        usuario.estado = 'inactivo'
        usuario.save(update_fields=['estado'])
        messages.success(request, 'Usuario desactivado. Su historial se conservó.')
    return redirect('admin_usuarios_view')
