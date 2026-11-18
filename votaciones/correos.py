"""Correo con el comprobante del voto (RF-10).

Se envía DESPUÉS de guardar el voto: si el correo falla, el voto ya quedó registrado y no se pierde.
Con un servidor de correo real (SMTP) se envía en segundo plano para que votar no se vuelva lento;
sin servidor (modo de prueba) el correo se imprime en la terminal.
"""
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import connection
from django.template import loader
from django.urls import reverse
from django.utils import timezone

from auditoria.models import Registro


def _mensaje(voto, protocolo, dominio):
    contexto = {
        "voto": voto,
        "usuario": voto.usuario,
        "fecha": timezone.localtime(voto.fecha),
        "enlace": f"{protocolo}://{dominio}{reverse('cuentas:mis_votos')}",
    }
    asunto = "".join(loader.render_to_string("votaciones/correo_comprobante_asunto.txt", contexto).splitlines())
    mensaje = EmailMultiAlternatives(asunto, loader.render_to_string("votaciones/correo_comprobante.txt", contexto),
                                     settings.DEFAULT_FROM_EMAIL, [voto.usuario.email])
    mensaje.attach_alternative(loader.render_to_string("votaciones/correo_comprobante.html", contexto), "text/html")
    return mensaje


def _enviar(mensaje, voto, ip):
    try:
        mensaje.send()
    except Exception as e:  # noqa: BLE001 - servidor caído, clave mala, sin internet: el voto ya está guardado
        Registro.objects.create(usuario=voto.usuario, accion="correo_fallido", ip=ip,
                                detalle=f"Comprobante {voto.codigo}: {type(e).__name__}")


def enviar_comprobante(voto, request):
    """Envía el comprobante al correo del votante. Nunca lanza errores hacia quien vota."""
    if not voto.usuario.email:
        return
    mensaje = _mensaje(voto, request.scheme, request.get_host())
    ip = request.META.get("REMOTE_ADDR")
    if settings.EMAIL_BACKEND.endswith("smtp.EmailBackend"):
        def trabajo():
            try:
                _enviar(mensaje, voto, ip)
            finally:
                connection.close()       # el hilo abrió su propia conexión a MySQL
        threading.Thread(target=trabajo, daemon=True).start()
    else:
        _enviar(mensaje, voto, ip)
