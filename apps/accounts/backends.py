from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class BackendCorreo(ModelBackend):
    """Autenticación por correo + contraseña (solo la usa el superadministrador)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        Usuario = get_user_model()
        correo = (kwargs.get("correo") or username or "").strip().lower()
        if not correo or not password:
            return None
        try:
            usuario = Usuario.objects.get(correo=correo)
        except Usuario.DoesNotExist:
            Usuario().set_password(password)  # iguala tiempos, evita enumerar cuentas
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
