from django.urls import path
from . import views

app_name = 'admin_demo_app'

urlpatterns = [
    # Panel de control del administrador
    path('panel/', views.admin_demo, name='admin_demo'),
]

