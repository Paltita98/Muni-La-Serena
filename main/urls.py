from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    # Flujo de autenticación exclusivo
    path('', views.login_view, name='login_view'),
    path('login/', views.login_view, name='login_view'),
    path('recuperar-password/', views.recuperar_password, name='recuperar_password'),
    path('validar-codigo/', views.validar_codigo, name='validar_codigo'),
    path('nueva-password/', views.nueva_password, name='nueva_password'),
]
