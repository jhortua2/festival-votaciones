"""Módulo del jurado (pantallas 15 y 16 · CU-09 · RF-15).

El jurado ve solo las votaciones a las que fue asignado y califica cada opción
con un puntaje. La calificación se envía una sola vez y no se modifica (RN-14).
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Calificacion, Votacion
from .servicios import CalificacionRechazada, calificar


def solo_jurado(vista):
    @wraps(vista)
    @login_required
    def envuelta(request, *args, **kwargs):
        if not request.user.es_jurado:
            messages.error(request, "Esa sección es solo para jurados.")
            return redirect("votaciones:inicio")
        return vista(request, *args, **kwargs)

    return envuelta


@solo_jurado
def inicio(request):
    """Pantalla 15 · Votaciones asignadas al jurado."""
    asignadas = list(request.user.votaciones_como_jurado.filter(publicada=True).select_related("categoria"))
    hechas = set(Calificacion.objects.filter(jurado=request.user).values_list("votacion_id", flat=True))
    for v in asignadas:
        v.calificada = v.pk in hechas
    return render(request, "jurado/inicio.html", {"votaciones": asignadas})


@solo_jurado
def calificar_votacion(request, pk):
    """Pantalla 16 · Calificar cada opción de 1 a la escala configurada."""
    votacion = get_object_or_404(request.user.votaciones_como_jurado.select_related("categoria"), pk=pk, publicada=True)
    previas = {c.opcion_id: c for c in Calificacion.objects.filter(jurado=request.user, votacion=votacion)}
    opciones = list(votacion.opciones_activas())
    for o in opciones:
        o.previa = previas.get(o.pk)
    error = None
    if request.method == "POST" and not previas:
        puntajes = {o.pk: request.POST.get(f"puntaje_{o.pk}") for o in opciones}
        comentarios = {o.pk: request.POST.get(f"comentario_{o.pk}", "").strip() for o in opciones}
        try:
            calificar(request.user, votacion, puntajes, comentarios, request)
        except CalificacionRechazada as e:
            error = e.mensaje
            for o in opciones:
                o.elegido = puntajes.get(o.pk)
        else:
            messages.success(request, f"Calificación de «{votacion.nombre}» enviada. Gracias.")
            return redirect("jurado:inicio")
    return render(request, "jurado/calificar.html", {
        "votacion": votacion, "opciones": opciones, "ya_califico": bool(previas),
        "escala": range(1, votacion.escala_maxima + 1), "error": error,
    })
