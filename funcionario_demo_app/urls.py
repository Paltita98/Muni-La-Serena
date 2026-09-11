from django.urls import path
from . import views

urlpatterns = [
    path('', views.funcionario_demo_view, name='funcionario_demo_view'),
    path('actividad/new/', views.registrar_actividad_view, name='registrar_actividad_view'),
    path('compromiso/new/', views.nuevo_compromiso_view, name='nuevo_compromiso_view'),
]
