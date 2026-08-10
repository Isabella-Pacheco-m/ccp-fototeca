from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url


def acceso_galeria(vista):
    """
    Exige sesión iniciada para ver la galería.

    Con ``GALERIA_PUBLICA=True`` en el entorno, la galería queda abierta a
    cualquier visitante; por defecto el acceso es solo con enlace mágico.
    """

    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if settings.GALERIA_PUBLICA or request.user.is_authenticated:
            return vista(request, *args, **kwargs)
        return redirect_to_login(request.get_full_path(), resolve_url(settings.LOGIN_URL))

    return envoltura


def solo_superadmin(vista):
    """Restringe el panel de administración al rol de superadministrador."""

    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), resolve_url(settings.LOGIN_URL))
        if not request.user.es_superadmin:
            raise PermissionDenied("Se requiere el rol de superadministrador.")
        return vista(request, *args, **kwargs)

    return envoltura
