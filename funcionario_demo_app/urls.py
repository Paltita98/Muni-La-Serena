from django.urls import path
from . import views

urlpatterns = [
    # Panel y vistas del funcionario
    path('panel/', views.funcionario_demo_view, name='funcionario_demo'),
    path('panel/', views.funcionario_demo_view, name='funcionario_demo_view'),
    path('actividades/', views.actividades_view, name='actividades_view'),
    path('actividades/<int:actividad_id>/', views.actividad_detalle_view, name='actividad_detalle_view'),
    path('atencion-social/', views.atenciones_sociales_view, name='atenciones_sociales_view'),
    path('atencion-social/nueva/', views.nueva_atencion_social_view, name='nueva_atencion_social_view'),
    path('agenda-colectiva/', views.agenda_colectiva_view, name='agenda_colectiva_view'),
    path('evidencias/', views.mis_evidencias_view, name='mis_evidencias_view'),
    path('evidencias/json/', views.evidencias_json_view, name='evidencias_json_view'),
    path('registrar-actividad/', views.registrar_actividad_view, name='registrar_actividad'),
    path('registrar-actividad/', views.registrar_actividad_view, name='registrar_actividad_view'),
    path('nuevo-compromiso/', views.nuevo_compromiso_view, name='nuevo_compromiso'),
    path('nuevo-compromiso/', views.nuevo_compromiso_view, name='nuevo_compromiso_view'),
]

