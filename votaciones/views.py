"""Vistas públicas: inicio, categorías, votaciones, opciones, confirmación y comprobante."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Categoria, Edicion, Opcion, Votacion, Voto
from .servicios import VotoRechazado, emitir_voto, ya_voto


def _votaciones_publicas():
    edicion = Edicion.actual()
    return (
        Votacion.objects.filter(publicada=True, categoria__activa=True, categoria__edicion=edicion)
        .select_related("categoria")
    )


def inicio(request):
    """Pantalla 1 · CU-03 · RF-07"""
    edicion = Edicion.actual()
    votaciones = list(_votaciones_publicas())
    abiertas = [v for v in votaciones if v.esta_abierta]
    categorias = Categoria.objects.filter(edicion=edicion, activa=True) if edicion else []
    return render(request, "votaciones/inicio.html", {
        "abiertas": abiertas,
        "destacada": abiertas[0] if abiertas else None,
        "categorias": categorias,
    })


def categorias(request):
    """Pantalla 4 · CU-03 · RF-07"""
    edicion = Edicion.actual()
    cats = Categoria.objects.filter(edicion=edicion, activa=True) if edicion else []
    return render(request, "votaciones/categorias.html", {"categorias": cats})


def categoria_detalle(request, pk):
    """Pantalla 5 · Votaciones disponibles de una categoría."""
    categoria = get_object_or_404(Categoria, pk=pk, activa=True)
    votaciones = categoria.votaciones.filter(publicada=True)
    return render(request, "votaciones/votaciones.html", {"categoria": categoria, "votaciones": votaciones})


def _votacion_publica(pk):
    votacion = get_object_or_404(Votacion.objects.select_related("categoria"), pk=pk, publicada=True)
    if not votacion.categoria.activa:
        raise Http404
    return votacion


def votacion_detalle(request, pk):
    """Pantalla 6 · Detalle y reglas visibles antes de votar."""
    votacion = _votacion_publica(pk)
    contexto = {
        "votacion": votacion,
        "ya_voto": ya_voto(request.user, votacion),
        "n_opciones": votacion.opciones_activas().count(),
    }
    if votacion.resultados_publicos():
        contexto["resultados"], contexto["total"] = votacion.conteo()
    return render(request, "votaciones/detalle.html", contexto)


def votacion_opciones(request, pk):
    """Pantalla 7 · CU-04 paso 1: seleccionar opción (todavía no se registra nada)."""
    votacion = _votacion_publica(pk)
    return render(request, "votaciones/opciones.html", {
        "votacion": votacion,
        "opciones": votacion.opciones_activas(),
        "ya_voto": ya_voto(request.user, votacion),
    })


@login_required
def confirmar(request, pk):
    """Pantalla 8 · CU-04 pasos 2-3: confirmar. Con POST se emite el voto."""
    votacion = _votacion_publica(pk)
    opcion_id = request.POST.get("opcion") or request.GET.get("opcion")
    if not opcion_id:
        messages.warning(request, "Elige una opción antes de votar.")
        return redirect("votaciones:opciones", pk=pk)
    opcion = get_object_or_404(Opcion, pk=opcion_id, votacion=votacion)

    if request.method == "POST" and request.POST.get("confirmado") == "1":
        try:
            voto = emitir_voto(request.user, opcion.pk, request)
        except VotoRechazado as e:
            return render(request, "votaciones/rechazo.html", {"votacion": votacion, "motivo": e.motivo, "mensaje": e.mensaje}, status=409)
        return redirect("votaciones:comprobante", codigo=voto.codigo)

    return render(request, "votaciones/confirmacion.html", {"votacion": votacion, "opcion": opcion})


@login_required
def comprobante(request, codigo):
    """Pantalla 9 · RF-10: mensaje posterior con código de comprobante."""
    voto = get_object_or_404(Voto.objects.select_related("opcion", "votacion__categoria"), codigo=codigo, usuario=request.user)
    return render(request, "votaciones/comprobante.html", {"voto": voto})
