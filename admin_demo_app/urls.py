from django.urls import path
from . import views

urlpatterns = [
    # Panel y secciones del administrador
    path('panel/', views.admin_demo_view, name='admin_demo'),
    path('panel/', views.admin_demo_view, name='admin_dashboard_view'),
    path('usuarios/', views.admin_usuarios_view, name='admin_usuarios_view'),
    path('usuarios/nuevo/', views.admin_nuevo_usuario_view, name='admin_nuevo_usuario_view'),
    path('usuarios/nuevo/', views.nuevo_usuario_view, name='nuevo_usuario_view'),
    path('usuarios/<int:usuario_id>/editar/', views.editar_usuario_view, name='editar_usuario_view'),
    path('usuarios/desactivar/', views.eliminar_usuario_view, name='eliminar_usuario_view'),
    path('delegaciones/', views.admin_delegaciones_view, name='admin_delegaciones_view'),
    path('delegaciones/nueva/', views.nueva_delegacion_view, name='nueva_delegacion_view'),
    path('delegaciones/<int:delegacion_id>/editar/', views.editar_delegacion_view, name='editar_delegacion_view'),
    path('delegaciones/eliminar/', views.eliminar_delegacion_view, name='eliminar_delegacion_view'),
    path('catalogos-metas/', views.admin_catalogos_view, name='admin_catalogos_view'),
    path('roles/nuevo/', views.nuevo_rol_view, name='nuevo_rol_view'),
    path('roles/<int:rol_id>/editar/', views.editar_rol_view, name='editar_rol_view'),
    path('roles/eliminar/', views.eliminar_rol_view, name='eliminar_rol_view'),
    path('items/nuevo/', views.nuevo_item_view, name='nuevo_item_view'),
    path('items/<int:item_id>/editar/', views.editar_item_view, name='editar_item_view'),
    path('items/eliminar/', views.eliminar_item_view, name='eliminar_item_view'),
    path('metas/nueva/', views.nueva_meta_view, name='nueva_meta_view'),
    path('metas/<int:meta_id>/editar/', views.editar_meta_view, name='editar_meta_view'),
    path('metas/eliminar/', views.eliminar_meta_view, name='eliminar_meta_view'),
    path('catalogos-atencion/nuevo/', views.nuevo_catalogo_atencion_view, name='nuevo_catalogo_atencion_view'),
    path('catalogos-atencion/<int:catalogo_id>/editar/', views.editar_catalogo_atencion_view, name='editar_catalogo_atencion_view'),
    path('catalogos-atencion/eliminar/', views.eliminar_catalogo_atencion_view, name='eliminar_catalogo_atencion_view'),
    path('auditoria/', views.admin_auditoria_view, name='admin_auditoria_view'),
]

