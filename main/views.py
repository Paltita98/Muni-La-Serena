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
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Count

from admin_demo_app.models import (
    Actividad,
    AtencionSocial,
    CodigoRecuperacion,
    Compromiso,
    Evidencia,
    Meta,
    Notificacion,
    Periodo,
    Usuario,
)

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
            elif password_valid and any('funcion' in role_name for role_name in role_names):
                role = 'FUNCIONARIO'
            elif password_valid and any('coordinador' in role_name for role_name in role_names):
                role = 'COORDINADOR'
            elif password_valid and any('delegado' in role_name or 'jefatura' in role_name for role_name in role_names):
                role = 'DELEGADO'
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
                    'DELEGADO': 'main:role_dashboard_view',
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
                    'DELEGADO': 'main:role_dashboard_view',
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

