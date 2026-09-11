from django.urls import path
from . import views

urlpatterns = [
    path('', views.funcionario_demo_view, name='funcionario_demo_view'),
    path('actividades/', views.actividades_view, name='actividades_view'),
    path('agenda-colectiva/', views.agenda_colectiva_view, name='agenda_colectiva_view'),
    path('mis-evidencias/', views.mis_evidencias_view, name='mis_evidencias_view'),
    path('actividad/new/', views.registrar_actividad_view, name='registrar_actividad_view'),
    path('compromiso/new/', views.nuevo_compromiso_view, name='nuevo_compromiso_view'),
]
