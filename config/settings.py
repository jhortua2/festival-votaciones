"""
Configuración de Django para Tu Voto Vallenato (Festival de la Leyenda Vallenata 2027).

Los datos sensibles (contraseña de la base de datos, clave secreta) se leen del
archivo .env, que NO se sube al repositorio. Copie .env.example como .env.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _cargar_env(ruta: Path) -> None:
    """Lee un archivo .env sencillo (CLAVE=valor) sin dependencias externas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "solo-para-desarrollo-cambie-esta-clave")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

if not DEBUG and SECRET_KEY.startswith("solo-para-desarrollo"):
    # En producción la clave secreta (con la que se firman las sesiones y el token CSRF) es obligatoria
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY en el archivo .env antes de usar DJANGO_DEBUG=0.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Apps del proyecto (una por dominio, RNF-11)
    "cuentas",
    "votaciones",
    "auditoria",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "votaciones.context_processors.festival",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Base de datos: MySQL por defecto. Con DB_ENGINE=sqlite se usa un archivo local
# (útil para probar rápido sin instalar MySQL).
# ---------------------------------------------------------------------------
if os.environ.get("DB_ENGINE", "mysql").lower() == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "festival_votaciones"),
            "USER": os.environ.get("DB_USER", "root"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"},
        }
    }

AUTH_USER_MODEL = "cuentas.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "cuentas:login"
LOGIN_REDIRECT_URL = "votaciones:inicio"
LOGOUT_REDIRECT_URL = "votaciones:inicio"

# Tamaño máximo de imagen de una opción (propuesto por el equipo; pendiente de validación)
MAX_IMAGEN_OPCION_MB = 2

MESSAGE_TAGS = {
    40: "danger",  # messages.ERROR -> clase Bootstrap "alert-danger"
}

# ---------------------------------------------------------------------------
# Seguridad de formularios, sesiones y cabeceras (Entrega 3)
# ---------------------------------------------------------------------------
# Token CSRF: lo genera CsrfViewMiddleware y va en cada formulario POST con {% csrf_token %}.
CSRF_COOKIE_HTTPONLY = True           # JavaScript no puede leer la cookie del token
CSRF_COOKIE_SAMESITE = "Lax"          # la cookie no viaja en peticiones desde otros sitios
CSRF_FAILURE_VIEW = "cuentas.views.csrf_fallo"  # página propia cuando el token falta o no es válido

# Sesión
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 2 * 60 * 60      # la sesión dura máximo 2 horas
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Cabeceras de seguridad
X_FRAME_OPTIONS = "DENY"              # nadie puede meter la app en un <iframe> (clickjacking)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Intentos de inicio de sesión: después de 5 fallos seguidos con el mismo correo, se bloquea 15 minutos
LOGIN_MAX_INTENTOS = int(os.environ.get("LOGIN_MAX_INTENTOS", "5"))
LOGIN_BLOQUEO_MINUTOS = int(os.environ.get("LOGIN_BLOQUEO_MINUTOS", "15"))

if os.environ.get("DJANGO_HTTPS", "0") == "1":
    # Solo al desplegar con un certificado HTTPS (DJANGO_HTTPS=1 en el .env): cookies seguras y HTTPS obligatorio.
    # En el PC y en las pruebas de GitHub se trabaja con http, por eso viene apagado.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]
