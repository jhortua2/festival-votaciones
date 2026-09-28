"""Reglas de negocio del voto (CU-04). Se aplican aquí y no en las plantillas (RNF-11)."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.servicios import ip_de, registrar

from .models import Opcion, Votacion, Voto


class VotoRechazado(Exception):
    """El voto no cumple una regla. `motivo` es una clave; `mensaje` es para el votante."""

    def __init__(self, motivo, mensaje):
        super().__init__(mensaje)
        self.motivo = motivo
        self.mensaje = mensaje


def clave_frecuencia(votacion, momento=None):
    if votacion.frecuencia == Votacion.Frecuencia.DIARIA:
        momento = timezone.localtime(momento or timezone.now())
        return momento.date().isoformat()
    return "unica"


def ya_voto(usuario, votacion):
    if not usuario.is_authenticated:
        return False
    return Voto.objects.filter(usuario=usuario, votacion=votacion, clave_frecuencia=clave_frecuencia(votacion)).exists()


def emitir_voto(usuario, opcion_id, request=None):
    """Registra un voto o lanza VotoRechazado. Cubre RN-02, RN-03, RN-04, RN-06 y RF-09."""
    if not usuario.is_authenticated:
        raise VotoRechazado("sin_sesion", "Debes iniciar sesión para votar.")

    with transaction.atomic():
        try:
            opcion = Opcion.objects.select_related("votacion").get(pk=opcion_id)
        except Opcion.DoesNotExist:
            raise VotoRechazado("opcion_invalida", "La opción que elegiste no existe.")

        votacion = opcion.votacion
        if votacion.estado == Votacion.Estado.CERRADA:
            _rechazo(request, usuario, votacion, "cerrada")
            raise VotoRechazado("cerrada", "Esta votación ya cerró. No se reciben más votos.")
        if votacion.estado != Votacion.Estado.ABIERTA:
            _rechazo(request, usuario, votacion, "no_abierta")
            raise VotoRechazado("no_abierta", "Esta votación todavía no está abierta.")
        if not opcion.activa:
            _rechazo(request, usuario, votacion, "opcion_inactiva")
            raise VotoRechazado("opcion_inactiva", "Esa opción ya no está disponible. Elige otra.")

        clave = clave_frecuencia(votacion)
        try:
            # savepoint propio: si falla la restricción única, la transacción sigue usable
            with transaction.atomic():
                voto = Voto.objects.create(
                    usuario=usuario, votacion=votacion, opcion=opcion,
                    clave_frecuencia=clave, ip=ip_de(request),
                )
        except IntegrityError:
            _rechazo(request, usuario, votacion, "limite")
            if votacion.frecuencia == Votacion.Frecuencia.DIARIA:
                raise VotoRechazado("limite", "Ya votaste hoy en esta votación. Puedes volver a votar mañana.")
            raise VotoRechazado("limite", "Ya votaste en esta votación. Tu voto anterior sigue contando.")

    registrar(request, "voto_emitido", f"{votacion.nombre} · comprobante {voto.codigo}", usuario=usuario)
    return voto


def _rechazo(request, usuario, votacion, motivo):
    registrar(request, "voto_rechazado", f"{votacion.nombre} · motivo: {motivo}", usuario=usuario)
