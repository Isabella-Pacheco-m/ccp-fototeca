import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class GestorUsuarios(BaseUserManager):
    """Gestor de usuarios identificados por correo electrónico."""

    use_in_migrations = True

    def _crear(self, correo, password=None, **extra):
        if not correo:
            raise ValueError("El correo electrónico es obligatorio.")
        correo = self.normalize_email(correo).lower()
        usuario = self.model(correo=correo, **extra)
        if password:
            usuario.set_password(password)
        else:
            # Las cuentas de consulta entran solo con enlace mágico.
            usuario.set_unusable_password()
        usuario.save(using=self._db)
        return usuario

    def create_user(self, correo, password=None, **extra):
        extra.setdefault("rol", Usuario.Rol.USUARIO)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(correo, password, **extra)

    def create_superuser(self, correo, password=None, **extra):
        extra.setdefault("rol", Usuario.Rol.SUPERADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("Un superadministrador requiere is_staff e is_superuser en True.")
        return self._crear(correo, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Dos roles:
      * SUPERADMIN — gestiona fotografías y usuarios.
      * USUARIO    — solo consulta la galería (ingresa con enlace mágico).
    """

    class Rol(models.TextChoices):
        SUPERADMIN = "superadmin", "Superadministrador"
        USUARIO = "usuario", "Usuario de consulta"

    correo = models.EmailField("correo electrónico", unique=True)
    nombre = models.CharField("nombre completo", max_length=150, blank=True)
    cargo = models.CharField("cargo o dependencia", max_length=150, blank=True)
    rol = models.CharField("rol", max_length=20, choices=Rol.choices, default=Rol.USUARIO)

    is_active = models.BooleanField(
        "acceso habilitado",
        default=True,
        help_text="Si se desactiva, el enlace mágico deja de funcionar para esta persona.",
    )
    is_staff = models.BooleanField("puede entrar al admin de Django", default=False)

    supabase_uid = models.CharField("UID de Supabase", max_length=64, blank=True, db_index=True)

    invitado_por = models.ForeignKey(
        "self",
        verbose_name="invitado por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitaciones",
    )
    notas = models.TextField("notas internas", blank=True)

    date_joined = models.DateTimeField("fecha de alta", default=timezone.now)
    ultimo_ingreso = models.DateTimeField("último ingreso", null=True, blank=True)
    total_ingresos = models.PositiveIntegerField("ingresos", default=0)

    objects = GestorUsuarios()

    USERNAME_FIELD = "correo"
    EMAIL_FIELD = "correo"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["nombre", "correo"]

    def __str__(self):
        return self.nombre or self.correo

    @property
    def es_superadmin(self):
        return self.rol == self.Rol.SUPERADMIN or self.is_superuser

    @property
    def iniciales(self):
        base = (self.nombre or self.correo).strip()
        partes = [p for p in base.replace(".", " ").replace("_", " ").split() if p]
        if not partes:
            return "?"
        if len(partes) == 1:
            return partes[0][:2].upper()
        return (partes[0][0] + partes[1][0]).upper()

    def registrar_ingreso(self):
        self.ultimo_ingreso = timezone.now()
        self.total_ingresos = models.F("total_ingresos") + 1
        self.save(update_fields=["ultimo_ingreso", "total_ingresos"])
        self.refresh_from_db(fields=["total_ingresos"])

    def save(self, *args, **kwargs):
        if self.correo:
            self.correo = self.correo.strip().lower()
        # El rol manda sobre el acceso al admin de Django.
        if self.rol == self.Rol.SUPERADMIN:
            self.is_staff = True
        elif not self.is_superuser:
            self.is_staff = False
        super().save(*args, **kwargs)


class EnlaceMagico(models.Model):
    """
    Enlace de un solo uso emitido por Django (backend "local").
    Solo se guarda el hash del token, nunca el token en claro.
    """

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="enlaces", verbose_name="usuario"
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField()
    usado_en = models.DateTimeField(null=True, blank=True)
    ip_solicitud = models.GenericIPAddressField(null=True, blank=True)
    agente = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "enlace mágico"
        verbose_name_plural = "enlaces mágicos"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["usuario", "-creado_en"])]

    def __str__(self):
        return f"Enlace para {self.usuario.correo} ({self.creado_en:%Y-%m-%d %H:%M})"

    @staticmethod
    def hashear(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def emitir(cls, usuario, ip=None, agente=""):
        """Crea un enlace y devuelve (instancia, token_en_claro)."""
        token = secrets.token_urlsafe(40)
        enlace = cls.objects.create(
            usuario=usuario,
            token_hash=cls.hashear(token),
            expira_en=timezone.now() + timedelta(minutes=settings.MAGIC_LINK_TTL_MINUTOS),
            ip_solicitud=ip,
            agente=(agente or "")[:255],
        )
        return enlace, token

    @property
    def vigente(self):
        return self.usado_en is None and timezone.now() < self.expira_en

    def marcar_usado(self):
        self.usado_en = timezone.now()
        self.save(update_fields=["usado_en"])
