"""Reglas de negocio del voto (CU-04) y de la calificación del jurado (CU-09).

Se aplican aquí y no en las plantillas (RNF-11)."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from auditoria.servicios import ip_de, registrar

from .models import Calificacion, Opcion, Votacion, Voto


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
        if not votacion.tiene_publico:
            _rechazo(request, usuario, votacion, "solo_jurado")
            raise VotoRechazado("solo_jurado", "En esta votación solo califica el jurado. El público no vota.")
        if votacion.jurados.filter(pk=usuario.pk).exists():
            _rechazo(request, usuario, votacion, "conflicto_jurado")
            raise VotoRechazado("conflicto_jurado", "Eres jurado de esta votación, así que no puedes votar como público (RN-15).")

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


# ---------------------------------------------------------------- Jurado (CU-09)
class CalificacionRechazada(Exception):
    def __init__(self, motivo, mensaje):
        super().__init__(mensaje)
        self.motivo = motivo
        self.mensaje = mensaje


def ya_califico(jurado, votacion):
    return Calificacion.objects.filter(jurado=jurado, votacion=votacion).exists()


def calificar(jurado, votacion, puntajes, comentarios=None, request=None):
    """Registra los puntajes de un jurado para TODAS las opciones activas de una votación.

    `puntajes` es un diccionario {opcion_id: puntaje}. Cubre RF-15, RN-13 y RN-14:
    solo jurados asignados, votación abierta, puntaje entre 1 y la escala, y una sola
    calificación por jurado y opción (la base de datos también lo impide).
    """
    comentarios = comentarios or {}
    if not getattr(jurado, "es_jurado", False):
        raise CalificacionRechazada("no_jurado", "Solo los usuarios con rol de jurado pueden calificar.")
    if not votacion.tiene_jurado:
        raise CalificacionRechazada("sin_jurado", "Esta votación es solo del público; no lleva calificación del jurado.")
    if not votacion.jurados.filter(pk=jurado.pk).exists():
        raise CalificacionRechazada("no_asignado", "No estás asignado como jurado de esta votación.")
    if votacion.estado != Votacion.Estado.ABIERTA:
        raise CalificacionRechazada("no_abierta", "Solo se puede calificar mientras la votación está abierta.")

    opciones = list(votacion.opciones_activas())
    limpios = {}
    for o in opciones:
        valor = puntajes.get(o.pk, puntajes.get(str(o.pk)))
        try:
            valor = int(valor)
        except (TypeError, ValueError):
            raise CalificacionRechazada("incompleta", f"Falta el puntaje de «{o.nombre}». Califica todas las opciones.")
        if not 1 <= valor <= votacion.escala_maxima:
            raise CalificacionRechazada("fuera_de_escala", f"El puntaje de «{o.nombre}» debe estar entre 1 y {votacion.escala_maxima}.")
        limpios[o] = valor

    try:
        with transaction.atomic():
            for o, valor in limpios.items():
                Calificacion.objects.create(jurado=jurado, votacion=votacion, opcion=o, puntaje=valor,
                                            comentario=(comentarios.get(o.pk) or comentarios.get(str(o.pk)) or "")[:255])
    except IntegrityError:
        raise CalificacionRechazada("ya_califico", "Ya enviaste tu calificación para esta votación. No se puede cambiar (RN-14).")

    registrar(request, "calificacion_registrada", f"{votacion.nombre} · {len(limpios)} opciones calificadas", usuario=jurado)
    return limpios
