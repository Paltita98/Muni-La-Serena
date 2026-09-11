from django.urls import path
from . import views

urlpatterns = [
    path('admin-demo/', views.admin_demo, name='admin_demo'),
    path('', views.funcionario_demo, name='funcionario_demo'),
    path('actividad/new/', views.registrar_actividad, name='registrar_actividad'),
    path('compromiso/new/', views.nuevo_compromiso, name='nuevo_compromiso'),
]
