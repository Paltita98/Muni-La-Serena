from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_demo_view, name='admin_demo_view'),
]
