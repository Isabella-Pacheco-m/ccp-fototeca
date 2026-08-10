from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    # Fotografías
    path("fotografias/", views.fotografias, name="fotografias"),
    path("fotografias/nueva/", views.fotografia_nueva, name="fotografia_nueva"),
    path("fotografias/<uuid:pk>/editar/", views.fotografia_editar, name="fotografia_editar"),
    path("fotografias/<uuid:pk>/eliminar/", views.fotografia_eliminar, name="fotografia_eliminar"),
    path("fotografias/<uuid:pk>/publicacion/", views.fotografia_publicacion, name="fotografia_publicacion"),
    # Categorías
    path("categorias/", views.categorias, name="categorias"),
    path("categorias/<int:pk>/editar/", views.categoria_editar, name="categoria_editar"),
    path("categorias/<int:pk>/eliminar/", views.categoria_eliminar, name="categoria_eliminar"),
    # Usuarios
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/nuevo/", views.usuario_nuevo, name="usuario_nuevo"),
    path("usuarios/<int:pk>/editar/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/eliminar/", views.usuario_eliminar, name="usuario_eliminar"),
    path("usuarios/<int:pk>/acceso/", views.usuario_acceso, name="usuario_acceso"),
    path("usuarios/<int:pk>/enviar-enlace/", views.usuario_enviar_enlace, name="usuario_enviar_enlace"),
]
