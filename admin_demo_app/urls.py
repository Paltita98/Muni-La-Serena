from django.urls import path
from . import views

urlpatterns = [
    # Panel y secciones del administrador
    path('panel/', views.admin_demo_view, name='admin_demo'),
    path('panel/', views.admin_demo_view, name='admin_dashboard_view'),
    path('usuarios/', views.admin_usuarios_view, name='admin_usuarios_view'),
    path('usuarios/nuevo/', views.admin_nuevo_usuario_view, name='admin_nuevo_usuario_view'),
    path('usuarios/nuevo/', views.nuevo_usuario_view, name='nuevo_usuario_view'),
    path('usuarios/<int:usuario_id>/editar/', views.editar_usuario_view, name='editar_usuario_view'),
    path('delegaciones/', views.admin_delegaciones_view, name='admin_delegaciones_view'),
    path('delegaciones/nueva/', views.nueva_delegacion_view, name='nueva_delegacion_view'),
    path('catalogos-metas/', views.admin_catalogos_view, name='admin_catalogos_view'),
    path('auditoria/', views.admin_auditoria_view, name='admin_auditoria_view'),
]

