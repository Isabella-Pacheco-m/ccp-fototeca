from django.urls import path

from . import views

app_name = "gallery"

urlpatterns = [
    path("", views.galeria, name="galeria"),
    path("fotografia/<uuid:pk>/", views.detalle, name="detalle"),
    path("fotografia/<uuid:pk>/archivo/<str:variante>/", views.archivo, name="archivo"),
    path("fotografia/<uuid:pk>/descargar/", views.descargar, name="descargar"),
]
