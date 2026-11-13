"""Vistas públicas: inicio, categorías, votaciones, opciones, confirmación y comprobante."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Categoria, Edicion, Opcion, Votacion, Voto
from .forms import VotoForm
from .servicios import VotoRechazado, emitir_voto, voto_en_categoria


def _votaciones_publicas():
    edicion = Edicion.actual()
    return (
        Votacion.objects.filter(publicada=True, categoria__activa=True, categoria__edicion=edicion)
        .select_related("categoria")
    )


def _resultados_publicados():
    """Votaciones cuyos resultados puede ver el público según su visibilidad (RN-10), con su ganador.
    No incluye ningún dato de los votantes."""
    publicadas = []
    for v in _votaciones_publicas().order_by("categoria__orden", "apertura"):
        if v.resultados_publicos():
            v.filas, v.total = v.resultados_ponderados()
            v.g = v.ganadores(v.filas)
            v.ranking = v.ranking_publico(v.filas) if v.es_independiente else None
            lider = v.g["oficial"]["opciones"]
            v.lider = lider[0] if len(lider) == 1 else None
            v.lider_pct = (v.lider.pct_jurado if v.es_independiente else v.lider.final) if v.lider else None
            if v.g["publico"]:                                  # modo independiente: también el del público
                pub = v.g["publico"]["opciones"]
                v.lider_pub = pub[0] if len(pub) == 1 else None
            publicadas.append(v)
    return publicadas


def inicio(request):
    """Pantalla 1 · CU-03 · RF-07"""
    edicion = Edicion.actual()
    votaciones = list(_votaciones_publicas())
    abiertas = [v for v in votaciones if v.esta_abierta]
    categorias = Categoria.objects.filter(edicion=edicion, activa=True) if edicion else []
    # Resultados en el inicio (Eje 4): las abiertas en tiempo real primero, luego las cerradas.
    resultados = sorted(_resultados_publicados(), key=lambda v: (not v.esta_abierta, v.categoria.orden))
    return render(request, "votaciones/inicio.html", {
        "abiertas": abiertas,
        "destacada": abiertas[0] if abiertas else None,
        "categorias": categorias,
        "resultados": resultados[:3],
        "hay_mas_resultados": len(resultados) > 3,
    })


def ediciones(request):
    """Ediciones anuales del Festival (Entrega 2): la activa y las anteriores, con sus categorías."""
    lista = Edicion.objects.prefetch_related("categorias").annotate(
        n_vot=Count("categorias__votaciones", filter=Q(categorias__votaciones__publicada=True, categorias__activa=True)))
    for e in lista:
        e.cats = [c for c in e.categorias.all() if c.activa]
    return render(request, "votaciones/ediciones.html", {"ediciones": lista})


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
        "voto_categoria": voto_en_categoria(request.user, votacion.categoria),
        "n_opciones": votacion.opciones_activas().count(),
        "es_jurado_aqui": request.user.is_authenticated and votacion.jurados.filter(pk=request.user.pk).exists(),
        "es_admin": request.user.is_authenticated and request.user.es_admin,
    }
    if votacion.resultados_publicos():
        contexto["resultados"], contexto["total"] = votacion.conteo()
        contexto["ganadores"] = votacion.ganadores()
    return render(request, "votaciones/detalle.html", contexto)


def resultados(request):
    """Publicación de resultados (Eje 4). Solo aparecen las votaciones cuya visibilidad lo permite (RN-10):
    «públicos en tiempo real» desde que abren, «públicos al cierre» cuando cierran. Las de «solo
    administradores» nunca se muestran aquí. No se expone ningún dato de los votantes."""
    return render(request, "votaciones/resultados.html", {"votaciones": _resultados_publicados(), "edicion": Edicion.actual()})


def votacion_opciones(request, pk):
    """Pantalla 7 · CU-04 paso 1: seleccionar opción (todavía no se registra nada)."""
    votacion = _votacion_publica(pk)
    return render(request, "votaciones/opciones.html", {
        "votacion": votacion,
        "opciones": votacion.opciones_activas(),
        "voto_categoria": voto_en_categoria(request.user, votacion.categoria),
        "es_admin": request.user.is_authenticated and request.user.es_admin,
    })


@login_required
def confirmar(request, pk):
    """Pantalla 8 · CU-04 pasos 2-3: confirmar. Con POST (formulario + CSRF) se emite el voto."""
    votacion = _votacion_publica(pk)
    datos = request.POST if request.method == "POST" else request.GET
    if not datos.get("opcion"):
        messages.warning(request, "Elige una opción antes de votar.")
        return redirect("votaciones:opciones", pk=pk)

    form = VotoForm(votacion, datos, exigir_confirmacion=request.method == "POST")
    if not form.is_valid():
        if "opcion" in form.errors:
            # CP-06: la opción no existe o pertenece a otra votación/categoría
            return render(request, "votaciones/rechazo.html", {
                "votacion": votacion, "motivo": "opcion_invalida", "mensaje": form.errors["opcion"][0],
            }, status=400)
        opcion = Opcion.objects.get(pk=datos.get("opcion"))
        return render(request, "votaciones/confirmacion.html", {"votacion": votacion, "opcion": opcion, "form": form})

    opcion = form.cleaned_data["opcion"]
    if request.method == "POST":
        try:
            voto = emitir_voto(request.user, opcion.pk, request, votacion=votacion)
        except VotoRechazado as e:
            return render(request, "votaciones/rechazo.html", {"votacion": votacion, "motivo": e.motivo, "mensaje": e.mensaje}, status=409)
        return redirect("votaciones:comprobante", codigo=voto.codigo)

    return render(request, "votaciones/confirmacion.html", {"votacion": votacion, "opcion": opcion, "form": form})


@login_required
def comprobante(request, codigo):
    """Pantalla 9 · RF-10: mensaje posterior con código de comprobante."""
    voto = get_object_or_404(Voto.objects.select_related("opcion", "votacion__categoria"), codigo=codigo, usuario=request.user)
    return render(request, "votaciones/comprobante.html", {"voto": voto})
