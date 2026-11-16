def connected_users(request):
    # With no DB sessions we only show the current session user (if logged in)
    email = request.session.get('fake_user_email')
    name = request.session.get('fake_user_name')
    if email:
        return {'connected_users': [{'email': email, 'name': name}]}
    return {'connected_users': []}


def current_user(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return {'current_user': None}

    user_name = request.session.get('user_name', '').strip()
    user_rut = request.session.get('user_rut', '').strip()
    if not user_rut:
        from admin_demo_app.models import Usuario

        user = Usuario.objects.filter(pk=user_id, estado='activo').first()
        if user:
            user_name = f'{user.nombres} {user.apellidos}'.strip()
            user_rut = user.identificador_inst

    return {
        'current_user': {
            'name': user_name,
            'rut': user_rut,
        },
    }


def current_measurement_period(request):
    if not request.session.get('user_id'):
        return {'current_measurement_period': None}

    from admin_demo_app.models import Periodo

    return {
        'current_measurement_period': Periodo.objects.filter(
            estado='abierto',
        ).order_by('-fecha_inicio').first(),
    }


def user_notifications(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return {'user_notifications': [], 'unread_notifications_count': 0}

    from admin_demo_app.models import Notificacion

    user_notifications = Notificacion.objects.filter(destinatario_id=user_id)
    unread_notifications = Notificacion.objects.filter(
        destinatario_id=user_id,
        leida__isnull=True,
    )
    if request.session.get('user_role') == 'FUNCIONARIO':
        user_notifications = user_notifications.exclude(tipo='administracion')
        unread_notifications = unread_notifications.exclude(tipo='administracion')

    notifications = list(
        user_notifications.select_related('actor').order_by('-creada')[:8]
    )
    unread_count = unread_notifications.count()
    return {
        'user_notifications': notifications,
        'unread_notifications_count': unread_count,
        'notifications_authenticated': True,
    }
