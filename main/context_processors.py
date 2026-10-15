def connected_users(request):
    # With no DB sessions we only show the current session user (if logged in)
    email = request.session.get('fake_user_email')
    name = request.session.get('fake_user_name')
    if email:
        return {'connected_users': [{'email': email, 'name': name}]}
    return {'connected_users': []}


def user_notifications(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return {'user_notifications': [], 'unread_notifications_count': 0}

    from admin_demo_app.models import Notificacion

    notifications = list(
        Notificacion.objects.filter(destinatario_id=user_id)
        .select_related('actor')
        .order_by('-creada')[:8]
    )
    unread_count = Notificacion.objects.filter(
        destinatario_id=user_id,
        leida__isnull=True,
    ).count()
    return {
        'user_notifications': notifications,
        'unread_notifications_count': unread_count,
        'notifications_authenticated': True,
    }
