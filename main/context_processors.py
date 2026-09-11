def connected_users(request):
    # With no DB sessions we only show the current session user (if logged in)
    email = request.session.get('fake_user_email')
    name = request.session.get('fake_user_name')
    if email:
        return {'connected_users': [{'email': email, 'name': name}]}
    return {'connected_users': []}
