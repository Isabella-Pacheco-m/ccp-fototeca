"""
Cliente mínimo de Supabase Auth (GoTrue) sobre su API REST.

Se usa únicamente para el envío y la verificación de enlaces mágicos; la
identidad de la Fototeca sigue viviendo en la tabla de usuarios de Django.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIEMPO_ESPERA = 12  # segundos


class ErrorSupabase(Exception):
    """Falla al comunicarse con Supabase Auth."""


def configurado():
    return bool(settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY)


def _cabeceras(clave=None):
    clave = clave or settings.SUPABASE_ANON_KEY
    return {
        "apikey": clave,
        "Authorization": f"Bearer {clave}",
        "Content-Type": "application/json",
    }


def _url(ruta):
    if not settings.SUPABASE_URL:
        raise ErrorSupabase("SUPABASE_URL no está configurada.")
    return f"{settings.SUPABASE_URL}/auth/v1/{ruta.lstrip('/')}"


def _detalle_error(respuesta):
    try:
        cuerpo = respuesta.json()
    except ValueError:
        return respuesta.text[:200]
    return cuerpo.get("msg") or cuerpo.get("error_description") or cuerpo.get("message") or str(cuerpo)[:200]


def enviar_enlace(correo, url_retorno):
    """
    Pide a Supabase que envíe el correo con el enlace mágico.

    ``create_user`` va en False: la autorización la concede el superadministrador
    dentro de la Fototeca, no el formulario de ingreso.
    """
    if not configurado():
        raise ErrorSupabase("Faltan SUPABASE_URL o SUPABASE_ANON_PUBLIC en el entorno.")

    try:
        respuesta = requests.post(
            _url("otp"),
            params={"redirect_to": url_retorno},
            json={"email": correo, "create_user": True},
            headers=_cabeceras(),
            timeout=TIEMPO_ESPERA,
        )
    except requests.RequestException as exc:
        raise ErrorSupabase(f"No hubo respuesta de Supabase: {exc}") from exc

    if respuesta.status_code >= 400:
        raise ErrorSupabase(f"Supabase respondió {respuesta.status_code}: {_detalle_error(respuesta)}")
    return True


def verificar_token_hash(token_hash, tipo="magiclink"):
    """
    Verifica del lado del servidor un enlace con ``token_hash`` (plantilla de
    correo con ``{{ .TokenHash }}``). Devuelve el diccionario del usuario.
    """
    try:
        respuesta = requests.post(
            _url("verify"),
            json={"type": tipo, "token_hash": token_hash},
            headers=_cabeceras(),
            timeout=TIEMPO_ESPERA,
        )
    except requests.RequestException as exc:
        raise ErrorSupabase(f"No hubo respuesta de Supabase: {exc}") from exc

    if respuesta.status_code >= 400:
        raise ErrorSupabase(f"Enlace inválido o vencido ({_detalle_error(respuesta)}).")

    datos = respuesta.json()
    usuario = datos.get("user")
    if not usuario:
        raise ErrorSupabase("Supabase no devolvió el usuario asociado al enlace.")
    return usuario


def usuario_desde_access_token(access_token):
    """Valida un access token (flujo implícito, ``#access_token=...``)."""
    try:
        respuesta = requests.get(
            _url("user"),
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=TIEMPO_ESPERA,
        )
    except requests.RequestException as exc:
        raise ErrorSupabase(f"No hubo respuesta de Supabase: {exc}") from exc

    if respuesta.status_code >= 400:
        raise ErrorSupabase(f"Sesión no válida ({_detalle_error(respuesta)}).")
    return respuesta.json()


def correo_de(usuario_supabase):
    correo = (usuario_supabase or {}).get("email") or ""
    return correo.strip().lower()
