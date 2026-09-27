from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Las rutas de login y recuperación irán en la app principal (main)
    path('', include('main.urls')),
    
    # Rutas para las otras aplicaciones
    path('administrador/', include('admin_demo_app.urls')),
    path('funcionario/', include('funcionario_demo_app.urls')),
]

# Configuración para servir archivos multimedia en modo DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

