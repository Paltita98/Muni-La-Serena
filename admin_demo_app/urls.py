from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard_view, name='admin_dashboard_view'),
    path('nuevo-usuario/', views.admin_nuevo_usuario_view, name='admin_nuevo_usuario_view'),
    path('usuarios/', views.admin_usuarios_view, name='admin_usuarios_view'),
    path('delegaciones/', views.admin_delegaciones_view, name='admin_delegaciones_view'),
    path('catalogos/', views.admin_catalogos_view, name='admin_catalogos_view'),
    path('auditoria/', views.admin_auditoria_view, name='admin_auditoria_view'),
    path('nuevo-usuario-directo/', views.nuevo_usuario_view, name='nuevo_usuario_view'),
    path('usuarios/<int:usuario_id>/editar/', views.editar_usuario_view, name='editar_usuario_view'),
    path('nueva-delegacion/', views.nueva_delegacion_view, name='nueva_delegacion_view'),
]
