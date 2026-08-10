from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("ingresar/", views.ingresar, name="ingresar"),
    path("ingresar/clave/", views.ingresar_con_clave, name="ingresar_clave"),
    path("enlace-enviado/", views.enlace_enviado, name="enlace_enviado"),
    path("salir/", views.salir, name="salir"),
    # Enlace mágico emitido por Django
    path("enlace/<str:token>/", views.validar_enlace, name="validar_enlace"),
    # Enlace mágico emitido por Supabase
    path("supabase/retorno/", views.retorno_supabase, name="retorno_supabase"),
    path("supabase/sesion/", views.sesion_supabase, name="sesion_supabase"),
]
