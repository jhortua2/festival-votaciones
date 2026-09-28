"""Panel de administración de la Fundación (pantallas 10 a 14 · CU-05 a CU-08)."""
import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from auditoria.models import Registro
from auditoria.servicios import registrar
from cuentas.models import Usuario

from .forms_panel import CategoriaForm, JustificacionForm, OpcionForm, VotacionForm
from .models import Categoria, Edicion, Opcion, Votacion, Voto


def solo_admin(vista):
    """Solo usuarios con rol administrador (o superusuario) entran al panel."""

    @wraps(vista)
    @login_required
    def envuelta(request, *args, **kwargs):
        if not request.user.es_admin:
            messages.error(request, "Esa sección es solo para administradores.")
            return redirect("votaciones:inicio")
        return vista(request, *args, **kwargs)

    return envuelta


def _edicion(request):
    edicion = Edicion.actual()
    if edicion is None:
        edicion = Edicion.objects.create(anio=2027, nombre="Festival de la Leyenda Vallenata 2027", activa=True)
    return edicion


# ---------------------------------------------------------------- 10. Panel
@solo_admin
def panel(request):
    edicion = _edicion(request)
    votaciones = Votacion.objects.filter(categoria__edicion=edicion).select_related("categoria").annotate(n_votos=Count("votos"))
    inicio_dia = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return render(request, "panel/panel.html", {
        "seccion": "panel",
        "votaciones": votaciones,
        "n_abiertas": sum(1 for v in votaciones if v.esta_abierta),
        "votos_hoy": Voto.objects.filter(votacion__categoria__edicion=edicion, fecha__gte=inicio_dia).count(),
        "n_categorias": Categoria.objects.filter(edicion=edicion, activa=True).count(),
        "n_votantes": Usuario.objects.filter(rol=Usuario.Rol.VOTANTE).count(),
        "auditoria": Registro.objects.select_related("usuario")[:8],
    })


# ---------------------------------------------------------------- 11. Categorías
@solo_admin
def categorias(request):
    edicion = _edicion(request)
    form = CategoriaForm(request.POST or None, edicion=edicion)
    if request.method == "POST" and form.is_valid():
        cat = form.save(commit=False)
        cat.edicion = edicion
        cat.save()
        registrar(request, "categoria_creada", cat.nombre)
        messages.success(request, f"Categoría «{cat.nombre}» creada.")
        return redirect("panel:categorias")
    cats = Categoria.objects.filter(edicion=edicion).annotate(n_vot=Count("votaciones"))
    return render(request, "panel/categorias.html", {"seccion": "categorias", "categorias": cats, "form": form})


@solo_admin
def categoria_editar(request, pk):
    cat = get_object_or_404(Categoria, pk=pk)
    form = CategoriaForm(request.POST or None, instance=cat)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request, "categoria_editada", cat.nombre)
        messages.success(request, "Categoría actualizada.")
        return redirect("panel:categorias")
    return render(request, "panel/form.html", {"seccion": "categorias", "form": form, "titulo": f"Editar categoría: {cat.nombre}", "volver": "panel:categorias"})


@solo_admin
@require_POST
def categoria_estado(request, pk):
    cat = get_object_or_404(Categoria, pk=pk)
    abiertas = [v for v in cat.votaciones.all() if v.esta_abierta]
    if cat.activa and abiertas and request.POST.get("confirmar") != "1":
        messages.warning(request, f"«{cat.nombre}» tiene {len(abiertas)} votación(es) abierta(s). Vuelve a pulsar «Inactivar» para confirmar.")
        request.session["confirmar_categoria"] = cat.pk
        return redirect("panel:categorias")
    cat.activa = not cat.activa
    cat.save(update_fields=["activa"])
    request.session.pop("confirmar_categoria", None)
    registrar(request, "categoria_activada" if cat.activa else "categoria_inactivada", cat.nombre)
    messages.success(request, "Categoría activada." if cat.activa else "Categoría inactivada.")
    return redirect("panel:categorias")


# ---------------------------------------------------------------- 12. Votaciones
@solo_admin
def votaciones(request):
    edicion = _edicion(request)
    lista = (Votacion.objects.filter(categoria__edicion=edicion).select_related("categoria")
             .annotate(n_votos=Count("votos", distinct=True), n_ops=Count("opciones", distinct=True)))
    return render(request, "panel/votaciones.html", {"seccion": "votaciones", "votaciones": lista})


@solo_admin
def votacion_form(request, pk=None):
    edicion = _edicion(request)
    votacion = get_object_or_404(Votacion, pk=pk) if pk else None
    form = VotacionForm(request.POST or None, instance=votacion, edicion=edicion)
    if request.method == "POST" and form.is_valid():
        v = form.save()
        registrar(request, "votacion_editada" if pk else "votacion_creada", v.nombre)
        messages.success(request, "Votación guardada." + ("" if v.publicada else " Queda en borrador: agrega opciones y publícala."))
        return redirect("panel:opciones", pk=v.pk)
    titulo = f"Editar votación: {votacion.nombre}" if votacion else "Nueva votación"
    return render(request, "panel/form.html", {"seccion": "votaciones", "form": form, "titulo": titulo, "volver": "panel:votaciones",
                                               "nota": "Se guarda como borrador. Para publicarla necesita mínimo 2 opciones activas (RN-07)."})


@solo_admin
@require_POST
def votacion_publicar(request, pk):
    v = get_object_or_404(Votacion, pk=pk)
    if not v.puede_publicarse():
        messages.error(request, "No se puede publicar: agrega mínimo 2 opciones activas (RN-07).")
    else:
        v.publicada = True
        v.save(update_fields=["publicada"])
        registrar(request, "votacion_publicada", v.nombre)
        messages.success(request, f"«{v.nombre}» publicada. Estado: {v.estado_etiqueta}.")
    destino = request.POST.get("next", "")
    return redirect(destino if destino.startswith("/panel/") else "panel:votaciones")


@solo_admin
def votacion_cerrar(request, pk):
    """CU-06 flujo 4b: cerrar antes de tiempo exige justificación."""
    v = get_object_or_404(Votacion, pk=pk)
    form = JustificacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        v.cerrada_manualmente = timezone.now()
        v.justificacion_cierre = form.cleaned_data["justificacion"]
        v.save(update_fields=["cerrada_manualmente", "justificacion_cierre"])
        registrar(request, "votacion_cerrada", f"{v.nombre}: {v.justificacion_cierre}")
        messages.success(request, "Votación cerrada.")
        return redirect("panel:votaciones")
    return render(request, "panel/form.html", {"seccion": "votaciones", "form": form, "titulo": f"Cerrar antes de tiempo: {v.nombre}",
                                               "volver": "panel:votaciones", "boton": "Cerrar votación", "peligro": True,
                                               "nota": "Después de cerrarla no se reciben más votos. La justificación queda en auditoría."})


# ---------------------------------------------------------------- 13. Opciones
@solo_admin
def opciones(request, pk):
    v = get_object_or_404(Votacion.objects.select_related("categoria"), pk=pk)
    form = OpcionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        o = form.save(commit=False)
        o.votacion = v
        o.save()
        registrar(request, "opcion_creada", f"{v.nombre}: {o.nombre}")
        messages.success(request, f"Opción «{o.nombre}» agregada.")
        return redirect("panel:opciones", pk=v.pk)
    ops = v.opciones.annotate(n_votos=Count("votos"))
    return render(request, "panel/opciones.html", {
        "seccion": "votaciones", "votacion": v, "opciones": ops, "form": form,
        "tiene_votos": v.votos.exists(), "just_form": JustificacionForm(),
    })


@solo_admin
def opcion_editar(request, pk):
    o = get_object_or_404(Opcion, pk=pk)
    form = OpcionForm(request.POST or None, request.FILES or None, instance=o)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request, "opcion_editada", o.nombre)
        messages.success(request, "Opción actualizada.")
        return redirect("panel:opciones", pk=o.votacion_id)
    return render(request, "panel/form.html", {"seccion": "votaciones", "form": form, "titulo": f"Editar opción: {o.nombre}",
                                               "volver_url": f"/panel/votaciones/{o.votacion_id}/opciones/", "multipart": True})


@solo_admin
@require_POST
def opcion_estado(request, pk):
    """RN-08: con votos no se elimina; se inactiva con justificación."""
    o = get_object_or_404(Opcion, pk=pk)
    if o.activa:
        form = JustificacionForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Escribe una justificación para inactivar la opción.")
            return redirect("panel:opciones", pk=o.votacion_id)
        o.activa = False
        o.justificacion_inactivacion = form.cleaned_data["justificacion"]
        registrar(request, "opcion_inactivada", f"{o.nombre}: {o.justificacion_inactivacion}")
        messages.success(request, "Opción inactivada y registrada en auditoría.")
    else:
        o.activa = True
        o.justificacion_inactivacion = ""
        registrar(request, "opcion_reactivada", o.nombre)
        messages.success(request, "Opción reactivada.")
    o.save(update_fields=["activa", "justificacion_inactivacion"])
    return redirect("panel:opciones", pk=o.votacion_id)


@solo_admin
@require_POST
def opcion_eliminar(request, pk):
    o = get_object_or_404(Opcion, pk=pk)
    if o.tiene_votos():
        messages.error(request, "No se puede eliminar: la opción tiene votos. Inactívala con una justificación (RN-08).")
    else:
        registrar(request, "opcion_eliminada", o.nombre)
        o.delete()
        messages.success(request, "Opción eliminada.")
    return redirect("panel:opciones", pk=o.votacion_id)


# ---------------------------------------------------------------- 14. Resultados
@solo_admin
def resultados(request, pk=None):
    edicion = _edicion(request)
    todas = Votacion.objects.filter(categoria__edicion=edicion, publicada=True).select_related("categoria")
    v = get_object_or_404(todas, pk=pk) if pk else todas.first()
    contexto = {"seccion": "resultados", "todas": todas, "votacion": v}
    if v:
        contexto["filas"], contexto["total"] = v.conteo()
        contexto["rechazados"] = Registro.objects.filter(accion="voto_rechazado", detalle__startswith=v.nombre).count()
        registrar(request, "resultados_consultados", v.nombre)
    return render(request, "panel/resultados.html", contexto)


@solo_admin
def resultados_csv(request, pk):
    v = get_object_or_404(Votacion, pk=pk)
    filas, total = v.conteo()
    registrar(request, "resultados_exportados", f"{v.nombre} (CSV)")
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="resultados-votacion-{v.pk}.csv"'
    respuesta.write("﻿")  # BOM para que Excel abra bien las tildes
    w = csv.writer(respuesta, delimiter=";")
    w.writerow(["Votación", v.nombre])
    w.writerow(["Estado", v.estado_etiqueta])
    w.writerow(["Generado", timezone.localtime().strftime("%Y-%m-%d %H:%M")])
    w.writerow([])
    w.writerow(["Opción", "Votos", "Porcentaje"])
    for o in filas:
        w.writerow([o.nombre, o.total, f"{o.porcentaje:.1f}".replace(".", ",")])
    w.writerow(["TOTAL", total, "100"])
    return respuesta


@solo_admin
def auditoria(request):
    registros = Registro.objects.select_related("usuario")[:200]
    return render(request, "panel/auditoria.html", {"seccion": "auditoria", "registros": registros})
