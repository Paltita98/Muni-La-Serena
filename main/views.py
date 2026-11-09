import secrets
from datetime import timedelta
from django.shortcuts import get_object_or_404, render, redirect
from django.core.mail import send_mail
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import validate_email
from django.db.models import Q
from django.utils.crypto import constant_time_compare
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Count, Q, Sum

from admin_demo_app.models import (
    Actividad,
    AtencionSocial,
    CodigoRecuperacion,
    Compromiso,
    Evidencia,
    Meta,
    Notificacion,
    OrganizacionJJVV,
    Periodo,
    Usuario,
)
from funcionario_demo_app.forms import OrganizacionJJVVForm

# --- Vistas Originales ---
def funcionario_demo(request):
    return render(request, 'funcionario_demo.html')

def admin_demo(request):
    return render(request, 'admin_demo.html')

def registrar_actividad(request):
    return render(request, 'registrar_actividad.html')

def nuevo_compromiso(request):
    return render(request, 'nuevo_compromiso.html')


# --- Vistas de Autenticación y Recuperación ---
def login_view(request):
    if request.method == 'POST':
        login_identifier = (request.POST.get('email') or request.POST.get('username') or '').strip()
        password = request.POST.get('password', '')
        user = (
            Usuario.objects.prefetch_related('roles')
            .filter(Q(email__iexact=login_identifier) | Q(identificador_inst__iexact=login_identifier), estado='activo')
            .first()
        )

        if user and password:
            stored_password = user.password_hash or ''
            password_valid = check_password(password, stored_password)
            if not password_valid and constant_time_compare(stored_password, password):
                user.password_hash = make_password(password)
                user.save(update_fields=['password_hash'])
                password_valid = True

            role_names = [role.nombre.casefold() for role in user.roles.all()]
            if password_valid and any('admin' in role_name for role_name in role_names):
                role = 'ADMIN'
            elif password_valid and any('verificador' in role_name for role_name in role_names):
                role = 'VERIFICADOR'
            elif password_valid and any('delegado' in role_name or 'jefatura' in role_name for role_name in role_names):
                role = 'DELEGADO'
            elif password_valid and any('organizaciones comunitarias' in role_name or 'oroc' in role_name for role_name in role_names):
                role = 'ORGANIZACIONES_COMUNITARIAS'
            elif password_valid and any('funcion' in role_name for role_name in role_names):
                role = 'FUNCIONARIO'
            elif password_valid and any('coordinador' in role_name for role_name in role_names):
                role = 'COORDINADOR'
            elif password_valid and any('consulta' in role_name for role_name in role_names):
                role = 'CONSULTA'
            else:
                role = None

            if role:
                request.session.cycle_key()
                request.session['user_id'] = user.pk
                request.session['user_role'] = role
                request.session['user_email'] = user.email
                request.session['user_name'] = f'{user.nombres} {user.apellidos}'.strip()
                if getattr(user, 'debe_cambiar_password', False):
                    request.session['must_change_password'] = True
                    messages.info(request, 'Por seguridad, crea tu contraseña personal para continuar.')
                    return redirect('main:primer_cambio_password')
                messages.success(request, f'Bienvenido/a, {request.session["user_name"]}.')
                destinations = {
                    'ADMIN': 'admin_dashboard_view',
                    'FUNCIONARIO': 'funcionario_demo_view',
                    'VERIFICADOR': 'verificador_evidencias_view',
                    'COORDINADOR': 'main:role_dashboard_view',
                    'DELEGADO': 'delegado_demo_view',
                    'ORGANIZACIONES_COMUNITARIAS': 'main:organizaciones_comunitarias_dashboard_view',
                    'CONSULTA': 'main:role_dashboard_view',
                }
                destination = destinations[role]
                return redirect(destination)

        messages.error(request, 'Correo o contraseña incorrectos, o usuario sin un rol de acceso válido.')

    return render(request, 'main/login.html')


def primer_cambio_password(request):
    if not request.session.get('must_change_password'):
        return redirect('main:login_view')

    user = _usuario_sesion_activo(request)
    if not user or not user.debe_cambiar_password:
        request.session.pop('must_change_password', None)
        return redirect('main:login_view')

    if request.method == 'POST':
        nueva = request.POST.get('nueva_password', '')
        confirmar = request.POST.get('confirmar_password', '')
        if nueva != confirmar:
            messages.error(request, 'Las contraseñas no coinciden.')
        elif check_password(nueva, user.password_hash):
            messages.error(request, 'La contraseña personal debe ser distinta de la contraseña temporal.')
        else:
            try:
                validate_password(nueva, user=user)
            except ValidationError as error:
                for message in error.messages:
                    messages.error(request, message)
            else:
                user.password_hash = make_password(nueva)
                user.debe_cambiar_password = False
                user.save(update_fields=['password_hash', 'debe_cambiar_password'])
                request.session.pop('must_change_password', None)
                messages.success(request, 'Tu contraseña personal quedó guardada.')
                destinations = {
                    'ADMIN': 'admin_dashboard_view',
                    'FUNCIONARIO': 'funcionario_demo_view',
                    'VERIFICADOR': 'verificador_evidencias_view',
                    'COORDINADOR': 'main:role_dashboard_view',
                    'DELEGADO': 'delegado_demo_view',
                    'ORGANIZACIONES_COMUNITARIAS': 'main:organizaciones_comunitarias_dashboard_view',
                    'CONSULTA': 'main:role_dashboard_view',
                }
                return redirect(destinations.get(request.session.get('user_role'), 'main:login_view'))

    return render(request, 'main/nueva_password.html', {'primer_acceso': True})


def role_dashboard_view(request):
    role = request.session.get('user_role')
    if role not in {'COORDINADOR', 'DELEGADO', 'CONSULTA'}:
        return redirect('main:login_view')
    if role == 'COORDINADOR':
        return _coordinator_dashboard(request)
    return render(request, 'main/role_dashboard.html', {'role': role})


def organizaciones_comunitarias_dashboard_view(request):
    if request.session.get('user_role') != 'ORGANIZACIONES_COMUNITARIAS':
        return redirect('main:login_view')
    organizaciones = OrganizacionJJVV.objects.order_by('-pk')
    return render(request, 'main/organizaciones_comunitarias_dashboard.html', {
        'organizaciones_total': organizaciones.count(),
        'socios_activos_total': organizaciones.aggregate(total=Sum('socios_activos'))['total'] or 0,
        'territorios_total': organizaciones.exclude(
            territorio_deleg__isnull=True,
        ).exclude(territorio_deleg='').values('territorio_deleg').distinct().count(),
        'organizaciones_recientes': organizaciones[:5],
    })


def organizaciones_jjvv_list_view(request):
    if request.session.get('user_role') != 'ORGANIZACIONES_COMUNITARIAS':
        return redirect('main:login_view')
    busqueda = request.GET.get('q', '').strip()
    organizaciones = OrganizacionJJVV.objects.all()
    if busqueda:
        organizaciones = organizaciones.filter(
            Q(organizaciones__icontains=busqueda)
            | Q(domicilio_legal__icontains=busqueda)
            | Q(territorio_deleg__icontains=busqueda)
            | Q(n_reg_pj__icontains=busqueda)
            | Q(reg_dir_n__icontains=busqueda)
        )
    return render(request, 'funcionario_demo_app/organizaciones_jjvv_listado.html', {
        'organizaciones': organizaciones.order_by('organizaciones'),
        'busqueda': busqueda,
    })


def nueva_organizacion_jjvv_view(request):
    return _gestionar_organizacion_jjvv(request)


def editar_organizacion_jjvv_view(request, organizacion_id):
    return _gestionar_organizacion_jjvv(request, organizacion_id)


def _gestionar_organizacion_jjvv(request, organizacion_id=None):
    if request.session.get('user_role') != 'ORGANIZACIONES_COMUNITARIAS':
        return redirect('main:login_view')
    organizacion = get_object_or_404(OrganizacionJJVV, pk=organizacion_id) if organizacion_id else None
    form = OrganizacionJJVVForm(
        request.POST if request.method == 'POST' else None,
        instance=organizacion,
    )
    if request.method == 'POST' and form.is_valid():
        organizacion = form.save()
        messages.success(
            request,
            f'Organización «{organizacion.organizaciones}» '
            f'{"actualizada" if organizacion_id else "registrada"} correctamente.',
        )
        return redirect('main:organizaciones_jjvv_list_view')
    return render(request, 'funcionario_demo_app/organizaciones_jjvv_formulario.html', {
        'form': form,
        'organizacion': organizacion,
    })


@require_POST
def eliminar_organizacion_jjvv_view(request, organizacion_id):
    if request.session.get('user_role') != 'ORGANIZACIONES_COMUNITARIAS':
        return redirect('main:login_view')
    organizacion = get_object_or_404(OrganizacionJJVV, pk=organizacion_id)
    nombre = organizacion.organizaciones
    organizacion.delete()
    messages.success(request, f'Organización «{nombre}» eliminada del registro.')
    return redirect('main:organizaciones_jjvv_list_view')


def _coordinator_dashboard(request):
    user = Usuario.objects.filter(
        pk=request.session.get('user_id'),
        estado='activo',
    ).first()
    if user is None:
        return redirect('main:login_view')

    today = timezone.localdate()
    period = Periodo.objects.filter(estado='abierto').order_by('-fecha_inicio').first()
    period_start = period.fecha_inicio if period else today.replace(day=1)
    period_end = period.fecha_termino if period else today
    range_label = (
        f'{period_start:%d/%m/%Y} al {period_end:%d/%m/%Y}'
        if period else f'Mes actual, hasta {today:%d/%m/%Y}'
    )

    activities = Actividad.objects.filter(fecha_actividad__range=(period_start, period_end))
    attentions = AtencionSocial.objects.filter(fecha__range=(period_start, period_end))
    commitments = Compromiso.objects.all()
    open_commitments = commitments.exclude(estado='realizado')
    overdue_commitments = open_commitments.filter(fecha_comprometida__lt=today).count()
    due_soon_commitments = open_commitments.filter(
        fecha_comprometida__range=(today, today + timedelta(days=7)),
    ).count()
    pending_activities = activities.filter(estado__in=('pendiente', 'en_correccion')).count()
    pending_evidence = Evidencia.objects.filter(
        actividad__fecha_actividad__range=(period_start, period_end),
        estado='pendiente',
    ).count()

    metas = list(
        Meta.objects.filter(periodo=period, vigente=True)
        .select_related('item', 'item__cargo', 'cargo', 'funcionario')
        .order_by('item__nombre', 'funcionario__apellidos')
    ) if period else []
    validated_counts = dict(
        Actividad.objects.filter(
            periodo=period,
            estado='validada',
        ).values('item_id').annotate(total=Count('pk')).values_list('item_id', 'total')
    ) if period else {}

    indicator_rows = []
    seen_items = set()
    for meta in metas:
        if meta.item_id in seen_items:
            continue
        seen_items.add(meta.item_id)
        actual = validated_counts.get(meta.item_id, 0)
        target = float(meta.valor_objetivo)
        progress = round(actual * 100 / target, 1) if target else 0
        indicator_rows.append({
            'name': meta.item.nombre,
            'cargo': meta.item.cargo.nombre,
            'actual': actual,
            'target': target,
            'unit': meta.item.unidad or 'registros',
            'weight': meta.ponderador_pct,
            'progress': min(progress, 100),
            'progress_label': f'{progress:g}%',
        })

    alerts = []
    if overdue_commitments:
        alerts.append({
            'title': 'Compromisos vencidos',
            'detail': f'{overdue_commitments} compromiso(s) siguen abiertos después de su fecha comprometida.',
            'tone': 'urgent',
        })
    if pending_activities:
        alerts.append({
            'title': 'Actividades por revisar',
            'detail': f'{pending_activities} actividad(es) están pendientes o en corrección.',
            'tone': 'attention',
        })
    if pending_evidence:
        alerts.append({
            'title': 'Evidencias pendientes',
            'detail': f'{pending_evidence} evidencia(s) esperan revisión.',
            'tone': 'attention',
        })
    if not alerts:
        alerts.append({
            'title': 'Sin alertas operativas',
            'detail': 'No hay pendientes de revisión ni compromisos vencidos en los registros consultados.',
            'tone': 'clear',
        })

    backlog_filters = {
        'q': request.GET.get('q', '').strip(),
        'tipo': request.GET.get('tipo', '').strip(),
        'estado': request.GET.get('estado', '').strip(),
        'territorio': request.GET.get('territorio', '').strip(),
        'desde': request.GET.get('desde', '').strip(),
        'hasta': request.GET.get('hasta', '').strip(),
    }
    dashboard_panels = {'resumen', 'operacion', 'indicadores', 'criterios', 'mejoras', 'tubo'}
    active_dashboard_panel = request.GET.get('panel', '')
    if any(backlog_filters.values()) and not active_dashboard_panel:
        active_dashboard_panel = 'tubo'
    if active_dashboard_panel not in dashboard_panels:
        active_dashboard_panel = 'resumen'
    valid_types = {'compromiso', 'actividad', 'gestion'}
    valid_states = {'ingresado', 'pendiente', 'en_proceso', 'realizado'}
    selected_type = backlog_filters['tipo'] if backlog_filters['tipo'] in valid_types else ''
    selected_state = backlog_filters['estado'] if backlog_filters['estado'] in valid_states else ''
    date_from = parse_date(backlog_filters['desde'])
    date_to = parse_date(backlog_filters['hasta'])
    search_term = backlog_filters['q']
    territory_term = backlog_filters['territorio']

    commitment_rows = Compromiso.objects.all()
    if not selected_type or selected_type == 'compromiso':
        if search_term:
            commitment_rows = commitment_rows.filter(
                Q(solicitante__icontains=search_term)
                | Q(territorio__icontains=search_term)
                | Q(observacion__icontains=search_term)
                | Q(responsable__nombres__icontains=search_term)
                | Q(responsable__apellidos__icontains=search_term)
                | Q(delegacion__nombre__icontains=search_term)
            )
        if territory_term:
            commitment_rows = commitment_rows.filter(
                Q(territorio__icontains=territory_term)
                | Q(delegacion__nombre__icontains=territory_term)
            )
        if selected_state:
            state_map = {
                'ingresado': ('ingresado',),
                'pendiente': ('pendiente', 'revision'),
                'en_proceso': ('en_proceso',),
                'realizado': ('realizado',),
            }
            commitment_rows = commitment_rows.filter(estado__in=state_map[selected_state])
        if date_from:
            commitment_rows = commitment_rows.filter(fecha_registro__date__gte=date_from)
        if date_to:
            commitment_rows = commitment_rows.filter(fecha_registro__date__lte=date_to)
        commitment_rows = commitment_rows.select_related(
            'delegacion', 'persona', 'responsable', 'actividad_origen',
        ).order_by('-fecha_registro')
    else:
        commitment_rows = Compromiso.objects.none()

    activity_rows = Actividad.objects.all()
    if not selected_type or selected_type == 'actividad':
        if search_term:
            activity_rows = activity_rows.filter(
                Q(descripcion__icontains=search_term)
                | Q(accion__icontains=search_term)
                | Q(contacto_nombre__icontains=search_term)
                | Q(funcionario__nombres__icontains=search_term)
                | Q(funcionario__apellidos__icontains=search_term)
                | Q(funcionario__delegacion__nombre__icontains=search_term)
                | Q(item__nombre__icontains=search_term)
            )
        if territory_term:
            activity_rows = activity_rows.filter(funcionario__delegacion__nombre__icontains=territory_term)
        if selected_state:
            state_map = {
                'ingresado': (),
                'pendiente': ('pendiente', 'rechazada'),
                'en_proceso': ('en_correccion',),
                'realizado': ('validada',),
            }
            activity_rows = activity_rows.filter(estado__in=state_map[selected_state])
        if date_from:
            activity_rows = activity_rows.filter(fecha_registro__date__gte=date_from)
        if date_to:
            activity_rows = activity_rows.filter(fecha_registro__date__lte=date_to)
        activity_rows = activity_rows.select_related(
            'funcionario', 'funcionario__delegacion', 'item', 'catalogo_tipo',
        ).order_by('-fecha_registro')
    else:
        activity_rows = Actividad.objects.none()

    attention_rows = AtencionSocial.objects.all()
    if not selected_type or selected_type == 'gestion':
        if search_term:
            attention_rows = attention_rows.filter(
                Q(solicitante__icontains=search_term)
                | Q(descripcion__icontains=search_term)
                | Q(persona__nombre__icontains=search_term)
                | Q(persona__referencia_anonima__icontains=search_term)
                | Q(funcionario__nombres__icontains=search_term)
                | Q(funcionario__apellidos__icontains=search_term)
                | Q(delegacion__nombre__icontains=search_term)
                | Q(catalogo_tipo__nombre__icontains=search_term)
                | Q(catalogo_subtipo__nombre__icontains=search_term)
            )
        if territory_term:
            attention_rows = attention_rows.filter(delegacion__nombre__icontains=territory_term)
        if selected_state == 'pendiente':
            attention_rows = attention_rows.filter(resultado='')
        elif selected_state == 'realizado':
            attention_rows = attention_rows.exclude(resultado='')
        elif selected_state:
            attention_rows = AtencionSocial.objects.none()
        if date_from:
            attention_rows = attention_rows.filter(fecha_registro__date__gte=date_from)
        if date_to:
            attention_rows = attention_rows.filter(fecha_registro__date__lte=date_to)
        attention_rows = attention_rows.select_related(
            'persona', 'delegacion', 'funcionario', 'funcionario__delegacion',
            'catalogo_tipo', 'catalogo_subtipo', 'actividad',
        ).order_by('-fecha_registro')
    else:
        attention_rows = AtencionSocial.objects.none()

    backlog_entries = []
    for compromiso in commitment_rows:
        status = 'realizado' if compromiso.estado == 'realizado' else compromiso.estado
        if status == 'revision':
            status = 'pendiente'
        backlog_entries.append({
            'id': f'compromiso-{compromiso.pk}',
            'tipo': 'compromiso',
            'tipo_label': 'Compromiso',
            'title': compromiso.observacion or 'Solicitud de la comunidad',
            'description': compromiso.observacion or 'Sin descripción adicional.',
            'requester': compromiso.solicitante,
            'territory': compromiso.territorio or compromiso.delegacion.nombre,
            'responsible': f'{compromiso.responsable.nombres} {compromiso.responsable.apellidos}'.strip(),
            'requested_at': compromiso.fecha_registro,
            'event_date': None,
            'due_date': compromiso.fecha_comprometida,
            'status': status,
            'original_status': compromiso.get_estado_display(),
            'detail': compromiso.actividad_origen.descripcion if compromiso.actividad_origen_id else '',
            'delegation': compromiso.delegacion.nombre,
        })

    for actividad in activity_rows:
        status = {
            'pendiente': 'pendiente',
            'rechazada': 'pendiente',
            'en_correccion': 'en_proceso',
            'validada': 'realizado',
        }.get(actividad.estado, 'ingresado')
        backlog_entries.append({
            'id': f'actividad-{actividad.pk}',
            'tipo': 'actividad',
            'tipo_label': 'Actividad',
            'title': actividad.accion or actividad.item.nombre,
            'description': actividad.descripcion,
            'requester': actividad.contacto_nombre or 'No informado',
            'territory': actividad.funcionario.delegacion.nombre if actividad.funcionario.delegacion_id else 'Sin territorio',
            'responsible': f'{actividad.funcionario.nombres} {actividad.funcionario.apellidos}'.strip(),
            'requested_at': actividad.fecha_registro,
            'event_date': actividad.fecha_actividad,
            'due_date': None,
            'status': status,
            'original_status': actividad.get_estado_display(),
            'detail': f'{actividad.item.nombre} · {actividad.codigo_evidencia}',
            'delegation': actividad.funcionario.delegacion.nombre if actividad.funcionario.delegacion_id else 'Sin delegación',
        })

    for atencion in attention_rows:
        status = 'realizado' if atencion.resultado else 'pendiente'
        backlog_entries.append({
            'id': f'gestion-{atencion.pk}',
            'tipo': 'gestion',
            'tipo_label': 'Gestión social',
            'title': atencion.catalogo_subtipo.nombre if atencion.catalogo_subtipo_id else atencion.catalogo_tipo.nombre,
            'description': atencion.descripcion,
            'requester': atencion.solicitante or atencion.persona.nombre or atencion.persona.referencia_anonima,
            'territory': atencion.delegacion.nombre if atencion.delegacion_id else 'Sin territorio',
            'responsible': f'{atencion.funcionario.nombres} {atencion.funcionario.apellidos}'.strip(),
            'requested_at': atencion.fecha_registro,
            'event_date': atencion.fecha,
            'due_date': None,
            'status': status,
            'original_status': 'Con resultado' if atencion.resultado else 'Sin resultado registrado',
            'detail': atencion.resultado or 'Sin resultado o acuerdo registrado.',
            'delegation': atencion.delegacion.nombre if atencion.delegacion_id else 'Sin delegación',
        })

    backlog_entries.sort(key=lambda entry: entry['requested_at'], reverse=True)
    status_labels = {
        'ingresado': 'Ingresado',
        'pendiente': 'Pendiente',
        'en_proceso': 'En proceso',
        'realizado': 'Realizado',
    }
    status_styles = {
        'ingresado': 'border-gray-300 bg-gray-100',
        'pendiente': 'border-amber-200 bg-amber-50',
        'en_proceso': 'border-sky-200 bg-sky-50',
        'realizado': 'border-emerald-200 bg-emerald-50',
    }
    backlog_columns = [
        {
            'key': status,
            'label': label,
            'style': status_styles[status],
            'entries': [entry for entry in backlog_entries if entry['status'] == status],
        }
        for status, label in status_labels.items()
    ]

    return render(request, 'main/coordinador_dashboard.html', {
        'role': 'COORDINADOR',
        'user': user,
        'period': period,
        'range_label': range_label,
        'today': today,
        'active_staff': Usuario.objects.filter(estado='activo').count(),
        'activity_total': activities.count(),
        'activity_pending': pending_activities,
        'attention_total': attentions.count(),
        'commitment_open': open_commitments.count(),
        'commitment_overdue': overdue_commitments,
        'commitment_due_soon': due_soon_commitments,
        'evidence_pending': pending_evidence,
        'indicator_rows': indicator_rows,
        'alerts': alerts,
        'backlog_columns': backlog_columns,
        'backlog_total': len(backlog_entries),
        'backlog_filters': backlog_filters,
        'active_dashboard_panel': active_dashboard_panel,
        'backlog_type_choices': (
            ('', 'Todos los tipos'),
            ('compromiso', 'Compromisos'),
            ('actividad', 'Actividades'),
            ('gestion', 'Gestiones sociales'),
        ),
        'backlog_status_choices': (
            ('', 'Todos los estados'),
            ('ingresado', 'Ingresado'),
            ('pendiente', 'Pendiente'),
            ('en_proceso', 'En proceso'),
            ('realizado', 'Realizado'),
        ),
    })


@require_POST
def logout_view(request):
    request.session.flush()
    messages.success(request, 'Cerraste sesión correctamente.')
    return redirect('main:login_view')


@require_POST
def marcar_notificacion_leida(request, notification_id):
    usuario = _usuario_sesion_activo(request)
    if not usuario:
        return redirect('main:login_view')
    notificacion = get_object_or_404(
        Notificacion,
        pk=notification_id,
        destinatario=usuario,
    )
    if not notificacion.leida:
        notificacion.leida = timezone.now()
        notificacion.save(update_fields=['leida'])
    destino = notificacion.url or request.META.get('HTTP_REFERER', '')
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(destino)
    return redirect('main:login_view')


@require_POST
def marcar_todas_notificaciones_leidas(request):
    usuario = _usuario_sesion_activo(request)
    if not usuario:
        return redirect('main:login_view')
    Notificacion.objects.filter(destinatario=usuario, leida__isnull=True).update(leida=timezone.now())
    destino = request.META.get('HTTP_REFERER', '')
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(destino)
    return redirect('main:login_view')


def _usuario_sesion_activo(request):
    user_id = request.session.get('user_id')
    return Usuario.objects.filter(pk=user_id, estado='activo').first() if user_id else None

def recuperar_password(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Ingresa un correo electrónico válido, por ejemplo nombre@dominio.cl.')
            return render(request, 'main/recuperar_password.html')
        request.session['reset_email_mask'] = _enmascarar_correo(email)
        request.session.pop('reset_user_id', None)
        request.session.pop('codigo_validado', None)
        request.session['reset_started_at'] = timezone.now().timestamp()
        request.session['reset_resends'] = 0
        request.session['reset_attempts'] = 0
        user = Usuario.objects.filter(email__iexact=email, estado='activo').first()
        if user:
            try:
                _emitir_codigo_recuperacion(request, user)
            except Exception:
                pass
        messages.success(request, f'Si el correo corresponde a una cuenta activa, recibirás un código de 6 dígitos en {request.session["reset_email_mask"]}. Revisa también la carpeta de spam.')
        return redirect('main:validar_codigo')
    return render(request, 'main/recuperar_password.html')


def _enmascarar_correo(email):
    local, separator, domain = email.partition('@')
    if not separator:
        return '****'
    visible = local[:1]
    return f'{visible}****@{domain}'


def _emitir_codigo_recuperacion(request, user, reenvio=False):
    codigo = f'{secrets.randbelow(1_000_000):06d}'
    challenge = CodigoRecuperacion.objects.filter(usuario=user).order_by('-creado').first()
    reenvios = challenge.reenvios + 1 if reenvio and challenge else 0
    send_mail(
        'Código de recuperación - Sistema Municipal',
        f'Tu código de verificación de 6 dígitos es: {codigo}\n\nEste código expira en 10 minutos.',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    CodigoRecuperacion.objects.filter(usuario=user).delete()
    CodigoRecuperacion.objects.create(
        usuario=user,
        codigo_hash=make_password(codigo),
        expira=timezone.now() + timedelta(minutes=10),
        reenvios=reenvios,
    )
    request.session['reset_user_id'] = user.pk
    request.session['reset_started_at'] = timezone.now().timestamp()
    request.session['reset_resends'] = reenvios
    request.session['reset_attempts'] = 0
    request.session.pop('codigo_validado', None)


def validar_codigo(request):
    user_id = request.session.get('reset_user_id')
    challenge = CodigoRecuperacion.objects.filter(usuario_id=user_id).order_by('-creado').first() if user_id else None
    correo_destino = request.session.get('reset_email_mask', 'tu correo registrado')
    if request.method == 'POST':
        codigo_ingresado = ''.join(request.POST.get(f'd{n}', '') for n in range(1, 7))
        intentos = challenge.intentos if challenge else request.session.get('reset_attempts', 0)
        if not challenge:
            if intentos >= 5:
                messages.error(request, 'Se agotaron los intentos. Solicita un nuevo código.')
            else:
                request.session['reset_attempts'] = intentos + 1
                messages.error(request, 'Código incorrecto o vencido. Verifica los seis dígitos o solicita uno nuevo.')
        elif challenge.expira <= timezone.now():
            messages.error(request, 'Código incorrecto o vencido. Verifica los seis dígitos o solicita uno nuevo.')
        elif challenge.intentos >= 5:
            messages.error(request, 'Se agotaron los intentos. Solicita un nuevo código.')
        elif len(codigo_ingresado) == 6 and codigo_ingresado.isdigit() and check_password(codigo_ingresado, challenge.codigo_hash):
            request.session['codigo_validado'] = True
            return redirect('main:nueva_password')
        else:
            challenge.intentos += 1
            challenge.save(update_fields=['intentos'])
            messages.error(request, 'Código incorrecto o vencido. Verifica los seis dígitos o solicita uno nuevo.')
    started_at = challenge.creado.timestamp() if challenge else request.session.get('reset_started_at', timezone.now().timestamp())
    reenvios = challenge.reenvios if challenge else request.session.get('reset_resends', 0)
    intentos = challenge.intentos if challenge else request.session.get('reset_attempts', 0)
    return render(request, 'main/validar_codigo.html', {
        'correo_destino': correo_destino,
        'segundos_reenvio': max(0, 60 - int(timezone.now().timestamp() - started_at)),
        'puede_reenviar': reenvios < 3,
        'intentos_restantes': max(0, 5 - intentos),
    })


def reenviar_codigo(request):
    user_id = request.session.get('reset_user_id')
    challenge = CodigoRecuperacion.objects.filter(usuario_id=user_id).order_by('-creado').first() if user_id else None
    if request.method != 'POST':
        return redirect('main:recuperar_password')
    if not challenge:
        started_at = request.session.get('reset_started_at', 0)
        reenvios = request.session.get('reset_resends', 0)
        if reenvios >= 3:
            messages.error(request, 'Se alcanzó el máximo de tres reenvíos.')
        elif timezone.now().timestamp() - started_at < 60:
            messages.error(request, 'Espera 60 segundos antes de reenviar el código.')
        else:
            request.session['reset_resends'] = reenvios + 1
            request.session['reset_started_at'] = timezone.now().timestamp()
            messages.success(request, 'Si el correo corresponde a una cuenta activa, enviaremos un nuevo código.')
        return redirect('main:validar_codigo')
    if challenge.reenvios >= 3 or challenge.creado > timezone.now() - timedelta(seconds=60):
        messages.error(request, 'Espera un minuto antes de reenviar el código. El máximo es de tres reenvíos.')
    else:
        try:
            _emitir_codigo_recuperacion(request, challenge.usuario, reenvio=True)
            messages.success(request, 'Enviamos un nuevo código a tu correo.')
        except Exception:
            messages.error(request, 'No fue posible enviar el correo. Inténtalo más tarde.')
    return redirect('main:validar_codigo')

def nueva_password(request):
    user_id = request.session.get('reset_user_id')
    challenge = CodigoRecuperacion.objects.filter(usuario_id=user_id).order_by('-creado').first() if user_id else None
    if not request.session.get('codigo_validado') or not challenge or challenge.expira <= timezone.now():
        return redirect('main:login_view')
    if request.method == 'POST':
        nueva = request.POST.get('nueva_password', '')
        confirmar = request.POST.get('confirmar_password', '')
        if nueva != confirmar:
            messages.error(request, 'Las contraseñas no coinciden.')
        else:
            try:
                validate_password(nueva, user=challenge.usuario)
            except ValidationError as error:
                for message in error.messages:
                    messages.error(request, message)
            else:
                challenge.usuario.password_hash = make_password(nueva)
                challenge.usuario.debe_cambiar_password = False
                challenge.usuario.save(update_fields=['password_hash', 'debe_cambiar_password'])
                challenge.delete()
                request.session.pop('reset_user_id', None)
                request.session.pop('codigo_validado', None)
                request.session.pop('reset_email_mask', None)
                request.session.pop('reset_started_at', None)
                request.session.pop('reset_resends', None)
                request.session.pop('reset_attempts', None)
                messages.success(request, 'Contraseña actualizada correctamente. Ya puedes iniciar sesión.')
                return redirect('main:login_view')
    return render(request, 'main/nueva_password.html')

