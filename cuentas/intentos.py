"""Límite de intentos de inicio de sesión (seguridad básica, Entrega 3).

Después de LOGIN_MAX_INTENTOS fallos seguidos con el mismo correo, ese correo queda
bloqueado LOGIN_BLOQUEO_MINUTOS minutos. Así se frena a quien intenta adivinar contraseñas.
Se usa la caché de Django (en memoria del servidor); un inicio de sesión correcto limpia el contador.
"""
from django.conf import settings
from django.core.cache import cache


def _clave(correo):
    return f"login_fallos:{correo.strip().lower()}"


def bloqueado(correo):
    return cache.get(_clave(correo), 0) >= settings.LOGIN_MAX_INTENTOS


def fallo(correo):
    clave = _clave(correo)
    cache.add(clave, 0, timeout=settings.LOGIN_BLOQUEO_MINUTOS * 60)
    try:
        return cache.incr(clave)
    except ValueError:
        cache.set(clave, 1, timeout=settings.LOGIN_BLOQUEO_MINUTOS * 60)
        return 1


def limpiar(correo):
    cache.delete(_clave(correo))
