"""
Orquestación del ingreso por enlace mágico.

Dos backends intercambiables (``MAGIC_LINK_BACKEND``):
  * ``supabase`` — Supabase Auth envía el correo y verifica el token.
  * ``local``    — Django emite un token firmado y lo envía por SMTP
                   (en desarrollo el correo se imprime en la consola).

En ambos casos la autorización la decide la Fototeca: si el correo no
corresponde a un usuario activo, no se envía nada.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import EnlaceMagico
from .supabase import ErrorSupabase, configurado as supabase_configurado, enviar_enlace

logger = logging.getLogger(__name__)


class ErrorEnvio(Exception):
    """No se pudo enviar el enlace por una falla técnica."""


def ip_de(request):
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def usuario_autorizado(correo):
    Usuario = get_user_model()
    return Usuario.objects.filter(correo=(correo or "").strip().lower(), is_active=True).first()


def excede_limite(usuario):
    """Evita el envío repetido de enlaces al mismo destinatario."""
    desde = timezone.now() - timedelta(minutes=settings.MAGIC_LINK_VENTANA_MINUTOS)
    recientes = EnlaceMagico.objects.filter(usuario=usuario, creado_en__gte=desde).count()
    return recientes >= settings.MAGIC_LINK_MAX_SOLICITUDES


def url_retorno(request):
    return request.build_absolute_uri(reverse("accounts:retorno_supabase"))


def solicitar_enlace(request, correo, siguiente=""):
    """
    Envía el enlace mágico si el correo pertenece a un usuario habilitado.

    Devuelve ``True`` si se envió y ``False`` si el correo no está autorizado.
    La vista muestra el mismo mensaje en ambos casos para no revelar qué
    correos existen en el sistema.
    """
    usuario = usuario_autorizado(correo)
    if usuario is None:
        logger.info("Solicitud de enlace para un correo no autorizado: %s", correo)
        return False

    if excede_limite(usuario):
        raise ErrorEnvio(
            "Se enviaron demasiadas solicitudes para este correo. "
            "Espera unos minutos antes de intentarlo de nuevo."
        )

    backend = settings.MAGIC_LINK_BACKEND
    if backend == "supabase" and supabase_configurado():
        try:
            enviar_enlace(usuario.correo, url_retorno(request))
        except ErrorSupabase as exc:
            logger.error("Supabase no pudo enviar el enlace a %s: %s", usuario.correo, exc)
            raise ErrorEnvio(
                "No fue posible enviar el enlace en este momento. "
                "Comunícate con el administrador de la Fototeca."
            ) from exc
    else:
        _enviar_enlace_local(request, usuario, siguiente)

    return True


def _enviar_enlace_local(request, usuario, siguiente=""):
    enlace, token = EnlaceMagico.emitir(
        usuario,
        ip=ip_de(request),
        agente=request.META.get("HTTP_USER_AGENT", ""),
    )
    ruta = reverse("accounts:validar_enlace", args=[token])
    url = request.build_absolute_uri(ruta)
    if siguiente:
        url = f"{url}?next={siguiente}"

    contexto = {
        "usuario": usuario,
        "url": url,
        "minutos": settings.MAGIC_LINK_TTL_MINUTOS,
    }
    texto = render_to_string("accounts/correo_enlace.txt", contexto)
    html = render_to_string("accounts/correo_enlace.html", contexto)

    mensaje = EmailMultiAlternatives(
        subject="Tu acceso a la Fototeca de la Cámara de Comercio de Palmira",
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[usuario.correo],
    )
    mensaje.attach_alternative(html, "text/html")
    try:
        mensaje.send(fail_silently=False)
    except Exception as exc:
        enlace.delete()
        logger.error("Falla SMTP enviando el enlace a %s: %s", usuario.correo, exc)
        raise ErrorEnvio(
            "No fue posible enviar el correo. Verifica la configuración SMTP."
        ) from exc

    if settings.DEBUG:
        logger.warning("[DESARROLLO] Enlace mágico para %s: %s", usuario.correo, url)


def consumir_enlace_local(token):
    """Valida un token propio de Django y devuelve el usuario, o ``None``."""
    enlace = EnlaceMagico.objects.filter(token_hash=EnlaceMagico.hashear(token)).select_related("usuario").first()
    if enlace is None or not enlace.vigente or not enlace.usuario.is_active:
        return None
    enlace.marcar_usado()
    # Un ingreso invalida los demás enlaces pendientes de esa persona.
    EnlaceMagico.objects.filter(usuario=enlace.usuario, usado_en__isnull=True).update(usado_en=timezone.now())
    return enlace.usuario


def vincular_supabase(usuario, usuario_supabase):
    uid = (usuario_supabase or {}).get("id") or ""
    if uid and usuario.supabase_uid != uid:
        usuario.supabase_uid = uid
        usuario.save(update_fields=["supabase_uid"])
