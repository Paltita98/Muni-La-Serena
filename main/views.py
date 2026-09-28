import random
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils.crypto import constant_time_compare

from admin_demo_app.models import Usuario

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
        email = (request.POST.get('email') or request.POST.get('username') or '').strip()
        password = request.POST.get('password', '')
        user = (
            Usuario.objects.prefetch_related('roles')
            .filter(email__iexact=email, estado='activo')
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
        email = request.POST.get('email')
        
        # Generar código aleatorio de 6 dígitos
        codigo = str(random.randint(100000, 999999))
        
        # Guardar temporalmente en sesión para validarlo en la siguiente vista
        request.session['reset_codigo'] = codigo
        request.session['reset_email'] = email
        
        # Enviar el correo electrónico
        asunto = 'Código de recuperación - Sistema Municipal'
        mensaje = f'Tu código de verificación de 6 dígitos es: {codigo}\n\nEste código expira en 10 minutos.'
        
        try:
            send_mail(asunto, mensaje, settings.DEFAULT_FROM_EMAIL, [email])
            return redirect('main:validar_codigo')
        except Exception as e:
            messages.error(request, f'Hubo un problema al enviar el correo. Revisa tu configuración SMTP.')
            
    return render(request, 'main/recuperar_password.html')

def validar_codigo(request):
    correo_destino = request.session.get('reset_email', '')
    
    # Si ingresa directo a la URL sin haber pasado por recuperar, lo devolvemos
    if not correo_destino:
        return redirect('main:recuperar_password')
        
    if request.method == 'POST':
        # Concatenar los 6 inputs del formulario
        codigo_ingresado = (
            request.POST.get('d1', '') + request.POST.get('d2', '') + 
            request.POST.get('d3', '') + request.POST.get('d4', '') + 
            request.POST.get('d5', '') + request.POST.get('d6', '')
        )
        codigo_guardado = request.session.get('reset_codigo')
        
        if codigo_ingresado == codigo_guardado:
            # Si el código es correcto, habilitamos el paso final
            request.session['codigo_validado'] = True
            return redirect('main:nueva_password')
        else:
            messages.error(request, 'Código incorrecto. Inténtalo de nuevo.')
            
    return render(request, 'main/validar_codigo.html', {'correo_destino': correo_destino})

def nueva_password(request):
    # Validar que el usuario haya pasado la prueba del código
    if not request.session.get('codigo_validado'):
        return redirect('main:login_view')
        
    if request.method == 'POST':
        nueva = request.POST.get('nueva_password')
        confirmar = request.POST.get('confirmar_password')
        
        if nueva == confirmar:
            # En un entorno real, aquí actualizarías el hash de la BD:
            # usuario = Usuario.objects.get(email=request.session['reset_email'])
            # usuario.set_password(nueva)
            # usuario.save()
            
            messages.success(request, 'Contraseña actualizada correctamente. Ya puedes iniciar sesión.')
            
            # Limpiar todos los datos temporales de la sesión
            request.session.pop('reset_email', None)
            request.session.pop('reset_codigo', None)
            request.session.pop('codigo_validado', None)
            
            return redirect('main:login_view')
        else:
            messages.error(request, 'Las contraseñas no coinciden.')
            
    return render(request, 'main/nueva_password.html')

