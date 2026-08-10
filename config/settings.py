"""
Configuración del monolito modular «Fototeca CCP».

Todas las opciones sensibles se leen de variables de entorno (archivo .env).
"""

import os
import re
from pathlib import Path
from urllib.parse import quote_plus

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# interpolate=False conserva la sintaxis de plantillas de Railway (${{VAR}}),
# que de otro modo dotenv intentaría expandir y dejaría valores corruptos.
load_dotenv(BASE_DIR / ".env", interpolate=False)


def env(clave, por_defecto=None):
    valor = os.getenv(clave, por_defecto)
    if isinstance(valor, str):
        valor = valor.strip().strip('"').strip("'")
    return valor


def env_bool(clave, por_defecto=False):
    valor = env(clave)
    if valor is None or valor == "":
        return por_defecto
    return valor.lower() in {"1", "true", "yes", "on", "si", "sí"}


def env_list(clave, por_defecto=""):
    return [x.strip() for x in (env(clave, por_defecto) or "").split(",") if x.strip()]


# ---------------------------------------------------------------- núcleo ----

DEBUG = env_bool("DEBUG", True)

SECRET_KEY = env("SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "Falta SECRET_KEY. Defínela en las variables de entorno antes de "
            "desplegar con DEBUG=False."
        )
    # Solo para desarrollo local: nunca se usa con DEBUG=False.
    SECRET_KEY = "clave-de-desarrollo-no-apta-para-produccion"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or (["*"] if DEBUG else [])

# Railway expone el dominio público del servicio en esta variable.
_railway_host = env("RAILWAY_PUBLIC_DOMAIN")
if _railway_host and _railway_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_host)

EN_RAILWAY = any(
    env(clave)
    for clave in (
        "RAILWAY_PUBLIC_DOMAIN",
        "RAILWAY_PRIVATE_DOMAIN",
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_ENVIRONMENT_NAME",
        "RAILWAY_SERVICE_NAME",
        "RAILWAY_PROJECT_ID",
    )
)

# El health-check de Railway llega desde su red interna con la cabecera
# Host: healthcheck.railway.app. Sin este permiso Django responde 400 y el
# despliegue se marca como fallido aunque la aplicación esté sana.
HOST_HEALTHCHECK_RAILWAY = "healthcheck.railway.app"
if EN_RAILWAY and HOST_HEALTHCHECK_RAILWAY not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(HOST_HEALTHCHECK_RAILWAY)

# URL base pública del sitio (se usa para armar los enlaces mágicos).
SITE_URL = (env("SITE_URL") or (f"https://{_railway_host}" if _railway_host else "http://127.0.0.1:8000")).rstrip("/")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if _railway_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_railway_host}")
if SITE_URL.startswith("https://") and SITE_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(SITE_URL)

# --------------------------------------------------------- aplicaciones ----

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Módulos del monolito
    "apps.core",
    "apps.accounts",
    "apps.gallery",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.marca",
            ],
        },
    },
]

# ------------------------------------------------------------ base datos ----

_PLANTILLA_RAILWAY = re.compile(r"\$\{\{.*?\}\}")

# Valores de ejemplo de .env.example: si llegan tal cual, no son configuración
# real y hay que avisarlo en vez de intentar conectarse a «host:puerto».
_MARCAS_DE_EJEMPLO = ("usuario:clave@host", "://usuario:clave", "@host:puerto")


def _sin_resolver(valor):
    """¿Quedó una plantilla `${{VAR}}` de Railway sin sustituir?"""
    return bool(valor) and bool(_PLANTILLA_RAILWAY.search(valor))


def _es_de_ejemplo(url):
    return any(marca in url for marca in _MARCAS_DE_EJEMPLO)


def _url_base_datos():
    """
    Prioridad:
      1) DATABASE_URL (Railway la inyecta ya resuelta dentro del contenedor).
      2) PG* sueltas, si están resueltas.
      3) SQLite local, para poder levantar el proyecto sin credenciales.
    """
    url = env("DATABASE_URL")
    if url and not _sin_resolver(url):
        if _es_de_ejemplo(url):
            raise ImproperlyConfigured(
                "DATABASE_URL sigue teniendo el valor de ejemplo de .env.example "
                "(«postgresql://usuario:clave@host:puerto/base»). En Railway debe "
                "referenciar el servicio de Postgres: DATABASE_URL=${{ Postgres.DATABASE_URL }} "
                "(sin espacios), no una URL escrita a mano."
            )
        return url

    host = env("PGHOST")
    usuario = env("PGUSER") or env("POSTGRES_USER")
    clave = env("PGPASSWORD") or env("POSTGRES_PASSWORD")
    nombre = env("PGDATABASE") or env("POSTGRES_DB")
    puerto = env("PGPORT", "5432")
    if host and usuario and clave and nombre and not _sin_resolver(host):
        # Las credenciales van escapadas: una contraseña con @, / o : rompería
        # la URL si se concatenara en crudo.
        return (
            f"postgresql://{quote_plus(usuario)}:{quote_plus(clave)}"
            f"@{host}:{puerto}/{nombre}"
        )

    return None


_url_bd = _url_base_datos()

if _url_bd:
    try:
        _config_bd = dj_database_url.parse(
            _url_bd,
            conn_max_age=int(env("DB_CONN_MAX_AGE", "600")),
            conn_health_checks=True,
            ssl_require=env_bool("DB_SSL_REQUIRE", False),
        )
    except Exception as exc:
        raise ImproperlyConfigured(
            "No se pudo interpretar DATABASE_URL: "
            f"{exc}. Debe tener la forma "
            "postgresql://usuario:contraseña@host:5432/base. En Railway lo "
            "habitual es dejar que la inyecte el propio servicio con "
            "DATABASE_URL=${{ Postgres.DATABASE_URL }} (sin espacios)."
        ) from exc

    if not _config_bd.get("NAME"):
        raise ImproperlyConfigured(
            "DATABASE_URL no incluye el nombre de la base de datos."
        )

    DATABASES = {"default": _config_bd}
else:
    # Modo desarrollo sin Postgres accesible.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

USANDO_POSTGRES = DATABASES["default"]["ENGINE"].endswith("postgresql")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------- autenticación ----

AUTH_USER_MODEL = "accounts.Usuario"

AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.BackendCorreo",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:ingresar"
LOGIN_REDIRECT_URL = "gallery:galeria"
LOGOUT_REDIRECT_URL = "accounts:ingresar"

SESSION_COOKIE_AGE = int(env("SESSION_COOKIE_AGE", str(60 * 60 * 12)))  # 12 horas
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ------------------------------------------------------- enlaces mágicos ----

# "supabase"  -> el correo lo envía Supabase Auth (signInWithOtp).
# "local"     -> Django genera y envía el enlace firmado (útil en desarrollo).
MAGIC_LINK_BACKEND = (env("MAGIC_LINK_BACKEND") or "").lower() or None

SUPABASE_URL = (env("SUPABASE_URL") or "").rstrip("/")
SUPABASE_ANON_KEY = env("SUPABASE_ANON_PUBLIC") or env("SUPABASE_ANON_KEY") or ""
SUPABASE_SERVICE_ROLE = env("SUPABASE_SERVICE_ROLE") or ""

if not SUPABASE_URL:
    # Se puede derivar del usuario de conexión: "postgres.<project-ref>"
    _usuario_supabase = env("SUPABASE_DB_USER") or ""
    if "." in _usuario_supabase:
        SUPABASE_URL = f"https://{_usuario_supabase.split('.', 1)[1]}.supabase.co"

if MAGIC_LINK_BACKEND is None:
    MAGIC_LINK_BACKEND = "supabase" if (SUPABASE_URL and SUPABASE_ANON_KEY) else "local"

# Vigencia del enlace mágico propio de Django (minutos).
MAGIC_LINK_TTL_MINUTOS = int(env("MAGIC_LINK_TTL_MINUTOS", "20"))
# Máximo de solicitudes de enlace por correo dentro de la ventana (anti-spam).
MAGIC_LINK_MAX_SOLICITUDES = int(env("MAGIC_LINK_MAX_SOLICITUDES", "5"))
MAGIC_LINK_VENTANA_MINUTOS = int(env("MAGIC_LINK_VENTANA_MINUTOS", "15"))

# --------------------------------------------------------------- correo ----

EMAIL_BACKEND = env("EMAIL_BACKEND") or (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Fototeca CCP <no-responder@ccpalmira.org.co>")

# -------------------------------------------------------------- galería ----

# Si es True, la galería se puede ver sin iniciar sesión.
# Por defecto es False: el acceso es solo con enlace mágico.
GALERIA_PUBLICA = env_bool("GALERIA_PUBLICA", False)

# Límites de carga de imágenes.
IMAGEN_TAMANIO_MAXIMO_MB = int(env("IMAGEN_TAMANIO_MAXIMO_MB", "12"))
IMAGEN_ANCHO_MAXIMO = int(env("IMAGEN_ANCHO_MAXIMO", "2400"))
MINIATURA_ANCHO = int(env("MINIATURA_ANCHO", "640"))
FORMATOS_PERMITIDOS = ["JPEG", "PNG", "WEBP"]

DATA_UPLOAD_MAX_MEMORY_SIZE = IMAGEN_TAMANIO_MAXIMO_MB * 1024 * 1024 * 2
FILE_UPLOAD_MAX_MEMORY_SIZE = IMAGEN_TAMANIO_MAXIMO_MB * 1024 * 1024

# ------------------------------------------------ estáticos e i18n/l10n ----

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ------------------------------------------------------------ seguridad ----

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    # El health-check entra por HTTP desde la red interna: si se le redirige a
    # HTTPS responde 301 y Railway lo cuenta como caído.
    SECURE_REDIRECT_EXEMPT = [r"^salud/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Activar solo cuando el dominio definitivo vaya a servirse siempre por
    # HTTPS: entrar a la lista de preload del navegador es difícil de revertir.
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)

# ------------------------------------------------------------- logging ----

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "[{levelname}] {name}: {message}", "style": "{"}},
    "handlers": {"consola": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["consola"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["consola"], "propagate": False},
    },
}
