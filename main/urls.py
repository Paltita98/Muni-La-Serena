from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.login_view, name='login_view'),
    path('login/', views.login_view, name='login_view'),
    path('cerrar-sesion/', views.logout_view, name='logout_view'),
    path('notificaciones/<int:notification_id>/leer/', views.marcar_notificacion_leida, name='marcar_notificacion_leida'),
    path('notificaciones/leer-todas/', views.marcar_todas_notificaciones_leidas, name='marcar_todas_notificaciones_leidas'),
    path('panel-rol/', views.role_dashboard_view, name='role_dashboard_view'),
    path('recuperar-password/', views.recuperar_password, name='recuperar_password'),
    path('validar-codigo/', views.validar_codigo, name='validar_codigo'),
    path('reenviar-codigo/', views.reenviar_codigo, name='reenviar_codigo'),
    path('nueva-password/', views.nueva_password, name='nueva_password'),
]

