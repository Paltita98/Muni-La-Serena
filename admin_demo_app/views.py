from django.shortcuts import render


def admin_dashboard_view(request):
    return render(request, 'admin_demo_app/admin_demo.html')


def admin_demo_view(request):
    return admin_dashboard_view(request)


def admin_nuevo_usuario_view(request):
    return render(request, 'admin_demo_app/nuevo_usuario.html')


def admin_usuarios_view(request):
    return render(request, 'admin_demo_app/usuarios_roles.html')


def admin_delegaciones_view(request):
    return render(request, 'admin_demo_app/delegaciones.html')


def admin_catalogos_view(request):
    return render(request, 'admin_demo_app/catalogos_metas.html')


def admin_auditoria_view(request):
    return render(request, 'admin_demo_app/auditoria_sistema.html')


def nueva_delegacion_view(request):
    return render(request, 'admin_demo_app/delegaciones.html')


def nuevo_usuario_view(request):
    return render(request, 'admin_demo_app/nuevo_usuario.html')
