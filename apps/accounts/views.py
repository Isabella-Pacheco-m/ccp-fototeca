import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST

from . import servicios
from .forms import FormularioClave, FormularioEnlace
from .supabase import ErrorSupabase, correo_de, usuario_desde_access_token, verificar_token_hash

logger = logging.getLogger(__name__)

BACKEND_SESION = "apps.accounts.backends.BackendCorreo"


def _destino_seguro(request, candidato):
    """Solo permite redirigir a rutas del propio sitio."""
    if candidato and url_has_allowed_host_and_scheme(
        candidato, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidato
    return reverse(settings.LOGIN_REDIRECT_URL)


def _iniciar_sesion(request, usuario, siguiente=""):
    login(request, usuario, backend=BACKEND_SESION)
    usuario.registrar_ingreso()
    return redirect(_destino_seguro(request, siguiente))


@require_http_methods(["GET", "POST"])
def ingresar(request):
    if request.user.is_authenticated:
        return redirect(_destino_seguro(request, request.GET.get("next", "")))

    siguiente = request.POST.get("next") or request.GET.get("next", "")
    formulario = FormularioEnlace(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        correo = formulario.cleaned_data["correo"]
        try:
            servicios.solicitar_enlace(request, correo, siguiente)
        except servicios.ErrorEnvio as exc:
            messages.error(request, str(exc))
        else:
            # Mensaje idéntico exista o no la cuenta: no se filtra el padrón.
            request.session["correo_enlace"] = correo
            return redirect("accounts:enlace_enviado")

    return render(
        request,
        "accounts/ingresar.html",
        {"formulario": formulario, "next": siguiente},
    )


def enlace_enviado(request):
    return render(
        request,
        "accounts/enlace_enviado.html",
        {
            "correo": request.session.get("correo_enlace", ""),
            "minutos": settings.MAGIC_LINK_TTL_MINUTOS,
        },
    )


def validar_enlace(request, token):
    """Consume un enlace mágico emitido por Django (backend ``local``)."""
    usuario = servicios.consumir_enlace_local(token)
    if usuario is None:
        messages.error(
            request,
            "El enlace no es válido, ya fue utilizado o venció. Solicita uno nuevo.",
        )
        return redirect("accounts:ingresar")
    messages.success(request, f"Bienvenido/a, {usuario.nombre or usuario.correo}.")
    return _iniciar_sesion(request, usuario, request.GET.get("next", ""))


@require_http_methods(["GET"])
def retorno_supabase(request):
    """
    Punto de retorno del enlace enviado por Supabase.

    Admite las dos variantes de plantilla de correo:
      * ``?token_hash=...&type=magiclink`` → se verifica aquí mismo.
      * ``#access_token=...``              → el fragmento no viaja al servidor,
        así que la plantilla lo reenvía por POST a ``sesion_supabase``.
    """
    error = request.GET.get("error_description") or request.GET.get("error")
    if error:
        messages.error(request, f"Supabase rechazó el enlace: {error}")
        return redirect("accounts:ingresar")

    token_hash = request.GET.get("token_hash")
    if token_hash:
        try:
            datos = verificar_token_hash(token_hash, request.GET.get("type", "magiclink"))
        except ErrorSupabase as exc:
            messages.error(request, str(exc))
            return redirect("accounts:ingresar")
        return _entrar_con_supabase(request, datos, request.GET.get("next", ""))

    return render(request, "accounts/retorno_supabase.html", {"next": request.GET.get("next", "")})


@csrf_protect
@require_POST
def sesion_supabase(request):
    """Recibe el access token leído por JavaScript y abre la sesión de Django."""
    try:
        cuerpo = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "Solicitud mal formada."}, status=400)

    access_token = (cuerpo.get("access_token") or "").strip()
    if not access_token:
        return JsonResponse({"ok": False, "error": "Falta el token de acceso."}, status=400)

    try:
        datos = usuario_desde_access_token(access_token)
    except ErrorSupabase as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=401)

    correo = correo_de(datos)
    usuario = servicios.usuario_autorizado(correo)
    if usuario is None:
        return JsonResponse(
            {
                "ok": False,
                "error": "Tu correo no tiene acceso autorizado a la Fototeca. "
                         "Solicítalo al administrador.",
            },
            status=403,
        )

    servicios.vincular_supabase(usuario, datos)
    login(request, usuario, backend=BACKEND_SESION)
    usuario.registrar_ingreso()
    destino = _destino_seguro(request, cuerpo.get("next", ""))
    return JsonResponse({"ok": True, "destino": destino})


def _entrar_con_supabase(request, datos_supabase, siguiente=""):
    correo = correo_de(datos_supabase)
    usuario = servicios.usuario_autorizado(correo)
    if usuario is None:
        messages.error(
            request,
            "Tu correo no tiene acceso autorizado a la Fototeca. Solicítalo al administrador.",
        )
        return redirect("accounts:ingresar")
    servicios.vincular_supabase(usuario, datos_supabase)
    messages.success(request, f"Bienvenido/a, {usuario.nombre or usuario.correo}.")
    return _iniciar_sesion(request, usuario, siguiente)


@require_http_methods(["GET", "POST"])
def ingresar_con_clave(request):
    """Acceso alterno con contraseña para el superadministrador."""
    if request.user.is_authenticated:
        return redirect("dashboard:inicio" if request.user.es_superadmin else "gallery:galeria")

    formulario = FormularioClave(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = authenticate(
            request,
            correo=formulario.cleaned_data["correo"],
            password=formulario.cleaned_data["password"],
        )
        if usuario is None:
            messages.error(request, "Credenciales incorrectas o cuenta deshabilitada.")
        elif not usuario.es_superadmin:
            messages.error(request, "Esta entrada es solo para superadministradores. Usa el enlace mágico.")
        else:
            siguiente = request.POST.get("next") or reverse("dashboard:inicio")
            return _iniciar_sesion(request, usuario, siguiente)

    return render(request, "accounts/ingresar_clave.html", {"formulario": formulario})


@require_http_methods(["GET", "POST"])
def salir(request):
    if request.method == "POST":
        logout(request)
        messages.info(request, "Cerraste sesión correctamente.")
        return redirect("accounts:ingresar")
    return render(request, "accounts/salir.html")
