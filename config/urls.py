from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Rutas principales (Login y recuperación) - App Main
    path('', include('main.urls')),
    
    # Rutas de roles
    path('administrador/', include('admin_demo_app.urls')),
    path('funcionario/', include('funcionario_demo_app.urls')),
]

# Servir archivos multimedia en modo local/debug
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

