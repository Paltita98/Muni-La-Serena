from django.contrib import messages
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from main.notifications import (
    notificar,
    notificar_administradores,
    notificar_asignados_meta,
    notificar_usuarios_cargo,
    notificar_usuarios_delegacion,
    notificar_usuarios_rol,
)
from .forms import CatalogoTipoForm, DelegacionForm, ItemMedicionForm, MetaForm, RolForm, UsuarioForm
from .models import AtencionSocial, Auditoria, CatalogoTipo, Compromiso, Delegacion, ItemMedicion, Meta, Periodo, Rol, Usuario, Alerta


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
            creado = record is None
            record = form.save()
            actor_id = request.session.get('user_id')
            accion = 'creado' if creado else 'actualizado'
            notificar_administradores(actor_id, f'{title} «{record}» {accion}.')
            if isinstance(record, Meta):
                notificar_asignados_meta(record, actor_id, f'Se {accion} una meta para {record.item.nombre}.')
            elif isinstance(record, Delegacion) and not creado:
                notificar_usuarios_delegacion(record, actor_id, f'La delegación {record.nombre} fue actualizada por administración.')
            elif isinstance(record, ItemMedicion):
                notificar_usuarios_cargo(
                    record.cargo_id,
                    actor_id,
                    f'El ítem {record.nombre} fue {accion} por administración.',
                )
            elif isinstance(record, Rol):
                notificar_usuarios_rol(
                    record.pk,
                    actor_id,
                    f'El rol {record.nombre} y sus permisos fueron {accion}.',
                )
            messages.success(request, f'{title} guardado correctamente.')
            if isinstance(record, CatalogoTipo):
                success_url = 'admin_subatenciones_view' if record.categoria == 'subatencion' else 'admin_tipos_atencion_view'
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
        descripcion = str(record)
        try:
            record.delete()
        except ProtectedError:
            messages.error(request, 'No se puede eliminar porque existen registros relacionados.')
        else:
            notificar_administradores(
                request.session.get('user_id'),
                f'Se eliminó {model._meta.verbose_name} «{descripcion}».',
            )
            messages.success(request, 'Registro eliminado correctamente.')
    return redirect(success_url)


def _listing_row(cells, search, filters=None, edit_url='', delete_url='', record_id=''):
    return {
        'cells': cells,
        'search': search,
        'filters': filters or {},
        'edit_url': edit_url,
        'delete_url': delete_url,
        'record_id': record_id,
    }


def _render_admin_listing(request, title, active, sections):
    return render(request, 'admin_demo_app/admin_listado.html', {
        'titulo': title,
        'seccion_activa': active,
        'secciones': sections,
    })


def _filter(key, label, options):
    return {'key': key, 'label': label, 'options': options}


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
    usuarios = Usuario.objects.prefetch_related('roles').select_related('cargo', 'delegacion').order_by('apellidos', 'nombres')
    roles = Rol.objects.order_by('nombre')
    delegaciones = Delegacion.objects.order_by('nombre')
    rows = []
    for usuario in usuarios:
        nombres_roles = list(usuario.roles.values_list('nombre', flat=True))
        delegacion = usuario.delegacion.nombre if usuario.delegacion_id else 'Sin delegación'
        rows.append(_listing_row(
            [f'{usuario.nombres} {usuario.apellidos}', usuario.identificador_inst, usuario.email,
             ', '.join(nombres_roles) or 'Sin rol', delegacion, usuario.get_estado_display()],
            f'{usuario.nombres} {usuario.apellidos} {usuario.identificador_inst} {usuario.email} {" ".join(nombres_roles)} {delegacion} {usuario.estado}',
            {'estado': usuario.estado, 'delegacion': delegacion.casefold(), 'rol': '|'.join(r.casefold() for r in nombres_roles)},
            reverse('editar_usuario_view', args=[usuario.pk]), reverse('eliminar_usuario_view'), usuario.pk,
        ))
    return _render_admin_listing(request, 'Usuarios', 'usuarios', [{
        'titulo': 'Usuarios registrados',
        'columnas': ['Nombre', 'Identificador', 'Correo', 'Rol', 'Delegación', 'Estado'],
        'filas': rows,
        'filtros': [
            _filter('estado', 'Estado', [('activo', 'Activo'), ('inactivo', 'Inactivo')]),
            _filter('rol', 'Rol', [(r.nombre.casefold(), r.nombre) for r in roles]),
            _filter('delegacion', 'Delegación', [(d.nombre.casefold(), d.nombre) for d in delegaciones] + [('sin delegación', 'Sin delegación')]),
        ],
        'crear_url': reverse('admin_nuevo_usuario_view'),
        'crear_texto': 'Nuevo usuario',
        'editar': True,
        'eliminar': True,
        'eliminar_texto': 'Desactivar',
    }])


def admin_delegaciones_view(request):
    denied = _admin_access(request)
    if denied:
        return denied
    delegaciones = Delegacion.objects.select_related('responsable').order_by('nombre')
    rows = []
    for delegacion in delegaciones:
        rows.append(_listing_row(
            [delegacion.codigo or '-', delegacion.nombre, delegacion.direccion or '-', delegacion.comuna or '-', delegacion.get_estado_display()],
            f'{delegacion.codigo or ""} {delegacion.nombre} {delegacion.direccion or ""} {delegacion.comuna or ""} {delegacion.estado}',
            {'estado': delegacion.estado}, reverse('editar_delegacion_view', args=[delegacion.pk]),
            reverse('eliminar_delegacion_view'), delegacion.pk,
        ))
    return _render_admin_listing(request, 'Delegaciones', 'delegaciones', [{
        'titulo': 'Delegaciones registradas',
        'columnas': ['Código', 'Nombre', 'Dirección', 'Comuna', 'Estado'],
        'filas': rows,
        'filtros': [_filter('estado', 'Estado', [('activa', 'Activa'), ('inactiva', 'Inactiva')])],
        'crear_url': reverse('nueva_delegacion_view'),
        'crear_texto': 'Nueva delegación',
        'editar': True,
        'eliminar': True,
    }])


def admin_catalogos_view(request):
    return admin_items_metas_view(request)


def admin_roles_view(request):
    denied = _admin_access(request)
    if denied:
        return denied
    roles = Rol.objects.order_by('nombre')
    alcances = sorted({r.alcance_autorizado for r in roles if r.alcance_autorizado})
    rows = [_listing_row(
        [rol.nombre, rol.descripcion or '-', ', '.join(rol.permisos or []) or '-', rol.alcance_autorizado or '-'],
        f'{rol.nombre} {rol.descripcion or ""} {" ".join(rol.permisos or [])} {rol.alcance_autorizado}',
        {'alcance': rol.alcance_autorizado.casefold()}, reverse('editar_rol_view', args=[rol.pk]),
        reverse('eliminar_rol_view'), rol.pk,
    ) for rol in roles]
    return _render_admin_listing(request, 'Roles', 'roles', [{
        'titulo': 'Roles y permisos', 'columnas': ['Nombre', 'Descripción', 'Permisos', 'Alcance autorizado'],
        'filas': rows, 'filtros': [_filter('alcance', 'Alcance', [(a.casefold(), a) for a in alcances])],
        'crear_url': reverse('nuevo_rol_view'), 'crear_texto': 'Nuevo rol', 'editar': True, 'eliminar': True,
    }])


def admin_items_metas_view(request):
    denied = _admin_access(request)
    if denied:
        return denied
    items = ItemMedicion.objects.select_related('cargo').order_by('nombre')
    cargos = list(items.values_list('cargo__nombre', flat=True).distinct())
    item_rows = [_listing_row(
        [item.codigo or '-', item.nombre, item.descripcion or '-', item.cargo.nombre, item.get_estado_display()],
        f'{item.codigo or ""} {item.nombre} {item.descripcion or ""} {item.cargo.nombre} {item.estado}',
        {'estado': item.estado, 'cargo': item.cargo.nombre.casefold()},
        reverse('editar_item_view', args=[item.pk]), reverse('eliminar_item_view'), item.pk,
    ) for item in items]
    metas = Meta.objects.select_related('item', 'item__cargo', 'cargo', 'funcionario', 'periodo').order_by('-fecha_registro')
    periodos = Periodo.objects.order_by('-fecha_inicio')
    meta_rows = [_listing_row(
        [f'META-{meta.pk}', meta.item.nombre, str(meta.funcionario or meta.item.cargo), str(meta.valor_objetivo), f'{meta.ponderador_pct}%'],
        f'META-{meta.pk} {meta.item.nombre} {meta.cargo or ""} {meta.funcionario or ""} {meta.periodo} {meta.valor_objetivo}',
        {'vigente': 'vigente' if meta.vigente else 'inactiva', 'periodo': str(meta.periodo_id)},
        reverse('editar_meta_view', args=[meta.pk]), reverse('eliminar_meta_view'), meta.pk,
    ) for meta in metas]
    return _render_admin_listing(request, 'Ítems y metas', 'items_metas', [
        {'titulo': 'Ítems del proyecto', 'columnas': ['Código', 'Nombre', 'Descripción', 'Cargo', 'Estado'],
         'filas': item_rows, 'filtros': [_filter('estado', 'Estado', [('activo', 'Activo'), ('inactivo', 'Inactivo')]), _filter('cargo', 'Cargo', [(c.casefold(), c) for c in cargos if c])],
         'crear_url': reverse('nuevo_item_view'), 'crear_texto': 'Nuevo ítem', 'editar': True, 'eliminar': True},
        {'titulo': 'Metas', 'columnas': ['Código', 'Ítem', 'Asignación', 'Valor objetivo', 'Ponderación'],
         'filas': meta_rows, 'filtros': [_filter('vigente', 'Estado', [('vigente', 'Vigente'), ('inactiva', 'Inactiva')]), _filter('periodo', 'Período', [(str(p.pk), str(p)) for p in periodos])],
         'crear_url': reverse('nueva_meta_view'), 'crear_texto': 'Nueva meta', 'editar': True, 'eliminar': True},
    ])


def _admin_attention_catalog(request, category, title, active):
    denied = _admin_access(request)
    if denied:
        return denied
    catalogos = CatalogoTipo.objects.filter(categoria=category).select_related('padre').order_by('nombre')
    tipos = CatalogoTipo.objects.filter(categoria='atencion').order_by('nombre')
    rows = [_listing_row(
        [catalogo.codigo, catalogo.nombre, catalogo.descripcion or '-', str(catalogo.padre or '-') if category == 'subatencion' else catalogo.get_estado_display()],
        f'{catalogo.codigo} {catalogo.nombre} {catalogo.descripcion or ""} {catalogo.padre or ""} {catalogo.estado}',
        {'estado': catalogo.estado, 'tipo': str(catalogo.padre_id or '')},
        reverse('editar_catalogo_atencion_view', args=[catalogo.pk]), reverse('eliminar_catalogo_atencion_view'), catalogo.pk,
    ) for catalogo in catalogos]
    columns = ['Código', 'Nombre', 'Descripción', 'Tipo asociado' if category == 'subatencion' else 'Estado']
    filters = [_filter('estado', 'Estado', [('activo', 'Activo'), ('inactivo', 'Inactivo')])]
    if category == 'subatencion':
        filters.append(_filter('tipo', 'Tipo de Atención', [(str(t.pk), t.nombre) for t in tipos]))
    return _render_admin_listing(request, title, active, [{
        'titulo': f'{title} registrados', 'columnas': columns, 'filas': rows, 'filtros': filters,
        'crear_url': reverse('nuevo_catalogo_atencion_view'), 'crear_texto': f'Nuevo {title.lower()}',
        'editar': True, 'eliminar': True,
    }])


def admin_tipos_atencion_view(request):
    return _admin_attention_catalog(request, 'atencion', 'Tipos de Atención', 'tipos_atencion')


def admin_subatenciones_view(request):
    return _admin_attention_catalog(request, 'subatencion', 'Sub Atenciones', 'subatenciones')


def admin_atenciones_view(request):
    denied = _admin_access(request)
    if denied:
        return denied
    atenciones = AtencionSocial.objects.select_related('persona', 'catalogo_tipo', 'catalogo_subtipo', 'delegacion', 'funcionario').order_by('-fecha', '-id')
    delegaciones = Delegacion.objects.order_by('nombre')
    tipos = CatalogoTipo.objects.filter(categoria='atencion').order_by('nombre')
    rows = [_listing_row(
        [atencion.solicitante or atencion.persona.referencia_anonima,
         atencion.catalogo_tipo.nombre,
         atencion.catalogo_subtipo.nombre if atencion.catalogo_subtipo_id else '-',
         atencion.descripcion or atencion.resultado or '-',
         atencion.delegacion.nombre if atencion.delegacion_id else '-',
         str(atencion.funcionario), atencion.fecha.strftime('%d/%m/%Y')],
        f'{atencion.solicitante} {atencion.persona.referencia_anonima} {atencion.catalogo_tipo.nombre} {atencion.catalogo_subtipo or ""} {atencion.descripcion} {atencion.delegacion or ""} {atencion.funcionario} {atencion.fecha}',
        {'delegacion': atencion.delegacion.nombre.casefold() if atencion.delegacion_id else '', 'tipo': str(atencion.catalogo_tipo_id)},
    ) for atencion in atenciones]
    return _render_admin_listing(request, 'Atenciones', 'atenciones', [{
        'titulo': 'Atenciones registradas', 'columnas': ['Solicitante', 'Tipo', 'Sub Atención', 'Descripción', 'Delegación', 'Responsable', 'Fecha'],
        'filas': rows,
        'filtros': [_filter('tipo', 'Tipo', [(str(t.pk), t.nombre) for t in tipos]), _filter('delegacion', 'Delegación', [(d.nombre.casefold(), d.nombre) for d in delegaciones])],
        'solo_lectura': True,
    }])


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
    return _manage_record(request, Rol, RolForm, 'Rol', 'admin_roles_view')


def editar_rol_view(request, rol_id):
    return _manage_record(request, Rol, RolForm, 'Rol', 'admin_roles_view', rol_id)


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
            actor_id = request.session.get('user_id')
            autor = meta.autor if meta else get_object_or_404(
                Usuario, pk=actor_id, estado='activo',
            )
            funcionarios = list(form.cleaned_data['funcionarios'])
            asignacion_individual = bool(funcionarios)
            metas_guardadas = []
            with transaction.atomic():
                meta_base = form.save(commit=False)
                meta_base.autor = autor
                if meta and funcionarios:
                    asignado_actual = next(
                        (persona for persona in funcionarios if persona.pk == meta.funcionario_id),
                        funcionarios[0],
                    )
                    meta_base.funcionario = asignado_actual
                    meta_base.save()
                    metas_guardadas.append(meta_base)
                    funcionarios = [persona for persona in funcionarios if persona.pk != asignado_actual.pk]
                elif not funcionarios:
                    meta_base.funcionario = None
                    meta_base.cargo = meta_base.item.cargo
                    meta_base.save()
                    metas_guardadas.append(meta_base)
                else:
                    meta_base.funcionario = funcionarios.pop(0)
                    meta_base.save()
                    metas_guardadas.append(meta_base)

                for funcionario in funcionarios:
                    copia_meta = Meta.objects.create(
                        item=meta_base.item,
                        cargo=meta_base.item.cargo,
                        funcionario=funcionario,
                        periodo=meta_base.periodo,
                        valor_objetivo=meta_base.valor_objetivo,
                        ponderador_pct=meta_base.ponderador_pct,
                        umbral_minimo_pct=meta_base.umbral_minimo_pct,
                        maximo_computable_pct=meta_base.maximo_computable_pct,
                        autor=autor,
                        vigente=meta_base.vigente,
                    )
                    metas_guardadas.append(copia_meta)

            notificar_administradores(actor_id, f'Meta para {meta_base.item.nombre} guardada.')
            for meta_guardada in metas_guardadas:
                notificar_asignados_meta(
                    meta_guardada,
                    actor_id,
                    f'Se guardó una meta para {meta_guardada.item.nombre}.',
                )
            cantidad = len(metas_guardadas)
            mensajes = f'Meta guardada correctamente para {cantidad} funcionarios.' if asignacion_individual else 'Meta guardada correctamente para el cargo.'
            messages.success(request, mensajes)
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
            creado = usuario is None
            usuario = form.save()
            actor_id = request.session.get('user_id')
            accion = 'creada' if creado else 'actualizada'
            notificar_administradores(actor_id, f'La cuenta de {usuario.nombres} {usuario.apellidos} fue {accion}.')
            notificar(
                usuario.pk,
                f'Tu cuenta fue {accion} por administración.' if not creado else 'Tu cuenta fue creada. Ya puedes ingresar al sistema.',
                tipo='administracion',
                url='/login/',
                actor_id=actor_id,
            )
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
        notificar_administradores(
            request.session.get('user_id'),
            f'La cuenta de {usuario.nombres} {usuario.apellidos} fue desactivada.',
        )
        messages.success(request, 'Usuario desactivado. Su historial se conservó.')
    return redirect('admin_usuarios_view')
