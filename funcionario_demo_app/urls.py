from django.urls import path
from . import views

app_name = 'funcionario_demo_app'

urlpatterns = [
    # Panel y vistas del funcionario
    path('panel/', views.funcionario_demo_view, name='funcionario_demo'),
    path('registrar-actividad/', views.registrar_actividad, name='registrar_actividad'),
    path('nuevo-compromiso/', views.nuevo_compromiso, name='nuevo_compromiso'),
]

