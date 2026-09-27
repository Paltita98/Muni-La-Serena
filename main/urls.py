from django.urls import path
from . import views

urlpatterns = [
    # Rutas de Autenticación
    path('', views.login_view, name='login_view'),
    path('login/', views.login_view, name='login_view'),
    path('recuperar-password/', views.recuperar_password, name='recuperar_password'),
    path('validar-codigo/', views.validar_codigo, name='validar_codigo'),
    path('nueva-password/', views.nueva_password, name='nueva_password'),
    
    # Vistas generales que tenías definidas
    path('admin-demo/', views.admin_demo, name='admin_demo'),
    path('funcionario-demo/', views.funcionario_demo, name='funcionario_demo'),
    path('registrar-actividad/', views.registrar_actividad, name='registrar_actividad'),
    path('nuevo-compromiso/', views.nuevo_compromiso, name='nuevo_compromiso'),
]
