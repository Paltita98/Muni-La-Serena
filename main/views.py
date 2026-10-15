import secrets
from datetime import timedelta
from django.shortcuts import render, redirect
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

from admin_demo_app.models import CodigoRecuperacion, Usuario

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
            elif password_valid and any('funcion' in role_name for role_name in role_names):
                role = 'FUNCIONARIO'
            else:
                role = None

            if role:
                request.session.cycle_key()
                request.session['user_id'] = user.pk
                request.session['user_role'] = role
                request.session['user_email'] = user.email
                request.session['user_name'] = f'{user.nombres} {user.apellidos}'.strip()
                destination = 'admin_dashboard_view' if role == 'ADMIN' else 'funcionario_demo_view'
                return redirect(destination)

        messages.error(request, 'Correo o contraseña incorrectos, o usuario sin un rol de acceso válido.')

    return render(request, 'main/login.html')

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
                challenge.usuario.save(update_fields=['password_hash'])
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

