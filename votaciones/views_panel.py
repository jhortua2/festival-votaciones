"""Panel de administración de la Fundación (pantallas 10 a 14 y 17 · CU-05 a CU-08 y CU-10)."""
import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from auditoria.models import Registro
from auditoria.servicios import registrar
from cuentas.models import Usuario

from .forms_panel import (CategoriaForm, EdicionForm, JuradoForm, JustificacionForm, OpcionForm, UsuarioEditarForm,
                          UsuarioForm, VotacionForm)
from .excel import libro_resultados
from .models import Calificacion, Categoria, Edicion, Opcion, Votacion, Voto


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
def ediciones(request):
    """Registrar y consultar las ediciones anuales del Festival."""
    form = EdicionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ed = form.save()
        registrar(request, "edicion_creada", ed.nombre)
        messages.success(request, f"Edición «{ed.nombre}» creada. Actívala para trabajar en ella.")
        return redirect("panel:ediciones")
    lista = Edicion.objects.annotate(n_cat=Count("categorias", distinct=True), n_vot=Count("categorias__votaciones", distinct=True))
    return render(request, "panel/ediciones.html", {"seccion": "ediciones", "ediciones": lista, "form": form})


@solo_admin
def edicion_editar(request, pk):
    ed = get_object_or_404(Edicion, pk=pk)
    form = EdicionForm(request.POST or None, instance=ed)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request, "edicion_editada", ed.nombre)
        messages.success(request, "Edición actualizada.")
        return redirect("panel:ediciones")
    return render(request, "panel/form.html", {"seccion": "ediciones", "form": form, "titulo": f"Editar edición: {ed.nombre}", "volver": "panel:ediciones"})


@solo_admin
@require_POST
def edicion_activar(request, pk):
    """Solo una edición activa: es la que ve el público y la que se administra en el panel."""
    ed = get_object_or_404(Edicion, pk=pk)
    ed.activa = True
    ed.save()
    registrar(request, "edicion_activada", ed.nombre)
    messages.success(request, f"«{ed.nombre}» es ahora la edición activa.")
    return redirect("panel:ediciones")


@solo_admin
@require_POST
def edicion_eliminar(request, pk):
    """Solo se elimina una edición vacía y que no sea la activa; si no, se conserva su historial."""
    ed = get_object_or_404(Edicion, pk=pk)
    if ed.activa:
        messages.error(request, "No se puede eliminar la edición activa. Activa otra edición primero.")
    elif ed.categorias.exists():
        messages.error(request, f"No se puede eliminar «{ed.nombre}»: tiene categorías. Elimínalas primero.")
    else:
        registrar(request, "edicion_eliminada", ed.nombre)
        ed.delete()
        messages.success(request, f"Edición «{ed.nombre}» eliminada.")
    return redirect("panel:ediciones")


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


@solo_admin
@require_POST
def categoria_eliminar(request, pk):
    """Solo se elimina una categoría sin votaciones. Si tiene votaciones, se inactiva (así no se pierden votos)."""
    cat = get_object_or_404(Categoria, pk=pk)
    if cat.votaciones.exists():
        messages.error(request, f"No se puede eliminar «{cat.nombre}»: tiene votaciones. Elimínalas primero o inactiva la categoría.")
    else:
        registrar(request, "categoria_eliminada", cat.nombre)
        cat.delete()
        messages.success(request, f"Categoría «{cat.nombre}» eliminada.")
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
                                               "nota": ("Si ya está publicada, sigue publicada al guardar los cambios." if votacion and votacion.publicada
                                                        else "Se guarda como borrador. Para publicarla necesita mínimo 2 opciones activas (RN-07).")})


@solo_admin
@require_POST
def votacion_publicar(request, pk):
    v = get_object_or_404(Votacion, pk=pk)
    if not v.puede_publicarse():
        messages.error(request, "No se puede publicar: agrega mínimo 2 opciones activas (RN-07).")
    elif v.tiene_jurado and not v.jurados.exists():
        messages.error(request, "No se puede publicar: la votación lleva calificación del jurado y no tiene jurados asignados (RN-13).")
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
@require_POST
def votacion_eliminar(request, pk):
    """Solo se elimina una votación sin votos ni calificaciones (RN-05: los votos no se borran)."""
    v = get_object_or_404(Votacion, pk=pk)
    if v.votos.exists() or v.calificaciones.exists():
        messages.error(request, f"No se puede eliminar «{v.nombre}»: ya tiene votos o calificaciones. Ciérrala en su lugar.")
    else:
        registrar(request, "votacion_eliminada", f"{v.categoria.nombre} · {v.nombre}")
        v.delete()  # sus opciones se eliminan con ella
        messages.success(request, f"Votación «{v.nombre}» eliminada.")
    return redirect("panel:votaciones")


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


# ---------------------------------------------------------------- 17. Jurados
@solo_admin
def jurados(request):
    """CU-10: la Fundación crea las cuentas de los jurados y ve su avance."""
    form = JuradoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        j = Usuario.objects.create_user(username=d["email"], email=d["email"], password=d["password"],
                                        first_name=d["first_name"], last_name=d["last_name"], rol=Usuario.Rol.JURADO)
        registrar(request, "jurado_creado", j.email)
        messages.success(request, f"Jurado {j.get_full_name()} creado. Asígnalo en «Editar» de cada votación.")
        return redirect("panel:jurados")
    lista = (Usuario.objects.filter(rol=Usuario.Rol.JURADO)
             .annotate(n_asignadas=Count("votaciones_como_jurado", distinct=True),
                       n_calif=Count("calificaciones__votacion", distinct=True))
             .order_by("first_name"))
    return render(request, "panel/jurados.html", {"seccion": "jurados", "jurados": lista, "form": form})


# ---------------------------------------------------------------- Usuarios (Eje 4)
def _aplicar_rol(usuario, rol):
    """El rol decide los permisos. Solo el administrador entra al panel."""
    usuario.rol = rol
    usuario.is_staff = rol == Usuario.Rol.ADMIN
    if rol != Usuario.Rol.ADMIN:
        usuario.is_superuser = False


def _es_ultimo_admin(usuario):
    """True si `usuario` es el único administrador activo (no se puede quedar el sistema sin admin)."""
    if not (usuario.is_active and usuario.es_admin):
        return False
    otros = Usuario.objects.filter(is_active=True).filter(Q(rol=Usuario.Rol.ADMIN) | Q(is_superuser=True)).exclude(pk=usuario.pk)
    return not otros.exists()


@solo_admin
def usuarios(request):
    """Gestión de cuentas desde la app: crear administradores, jurados y votantes, cambiar rol y desactivar."""
    form = UsuarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        u = Usuario(username=d["email"], email=d["email"], first_name=d["first_name"], last_name=d["last_name"])
        _aplicar_rol(u, d["rol"])
        u.set_password(d["password1"])
        u.save()
        registrar(request, "usuario_creado", f"{u.email} · rol {u.get_rol_display()}")
        messages.success(request, f"Cuenta de {u.get_full_name() or u.email} creada con rol {u.get_rol_display().lower()}.")
        return redirect("panel:usuarios")

    lista = Usuario.objects.annotate(n_votos=Count("votos", distinct=True)).order_by("rol", "first_name", "email")
    f_rol, buscar = request.GET.get("rol", ""), request.GET.get("q", "").strip()
    if f_rol in Usuario.Rol.values:
        lista = lista.filter(rol=f_rol)
    if buscar:
        lista = lista.filter(Q(email__icontains=buscar) | Q(first_name__icontains=buscar) | Q(last_name__icontains=buscar))
    por_rol = {r: Usuario.objects.filter(rol=r).count() for r in Usuario.Rol.values}
    return render(request, "panel/usuarios.html", {
        "seccion": "usuarios", "form": form, "usuarios": lista, "roles": Usuario.Rol.choices,
        "por_rol": por_rol, "f_rol": f_rol, "q": buscar,
    })


@solo_admin
def usuario_editar(request, pk):
    u = get_object_or_404(Usuario, pk=pk)
    rol_antes = u.rol
    form = UsuarioEditarForm(request.POST or None, instance=u)
    if request.method == "POST" and form.is_valid():
        nuevo_rol = form.cleaned_data["rol"]
        if nuevo_rol != rol_antes and u.pk == request.user.pk:
            form.add_error("rol", "No puedes cambiar tu propio rol. Pídeselo a otro administrador.")
        elif nuevo_rol != Usuario.Rol.ADMIN and _es_ultimo_admin(Usuario.objects.get(pk=u.pk)):
            form.add_error("rol", "Es el único administrador activo; crea otro antes de cambiarle el rol.")
        else:
            u = form.save(commit=False)
            u.username = u.email
            _aplicar_rol(u, nuevo_rol)
            if form.cleaned_data.get("password1"):
                u.set_password(form.cleaned_data["password1"])
            u.save()
            detalle = u.email if nuevo_rol == rol_antes else f"{u.email} · rol {rol_antes} → {nuevo_rol}"
            registrar(request, "usuario_editado", detalle)
            messages.success(request, "Usuario actualizado.")
            return redirect("panel:usuarios")
    return render(request, "panel/form.html", {"seccion": "usuarios", "form": form, "titulo": f"Editar usuario: {u.email}",
                                               "volver": "panel:usuarios",
                                               "nota": "El rol define los permisos: el administrador entra al panel, el jurado califica y el votante vota."})


@solo_admin
@require_POST
def usuario_estado(request, pk):
    """Activa o desactiva una cuenta. No se borra para no perder sus votos ni la auditoría."""
    u = get_object_or_404(Usuario, pk=pk)
    if u.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
    elif u.is_active and _es_ultimo_admin(u):
        messages.error(request, "Es el único administrador activo; no se puede desactivar.")
    else:
        u.is_active = not u.is_active
        u.save(update_fields=["is_active"])
        registrar(request, "usuario_activado" if u.is_active else "usuario_desactivado", u.email)
        messages.success(request, f"Cuenta {u.email} {'activada' if u.is_active else 'desactivada'}.")
    return redirect("panel:usuarios")


# ---------------------------------------------------------------- 14. Resultados
@solo_admin
def resultados(request, pk=None):
    edicion = _edicion(request)
    todas = Votacion.objects.filter(categoria__edicion=edicion, publicada=True).select_related("categoria")
    v = get_object_or_404(todas, pk=pk) if pk else todas.first()
    contexto = {"seccion": "resultados", "todas": todas, "votacion": v}
    if v:
        contexto["filas"], contexto["total"] = v.resultados_ponderados()
        contexto["ranking_publico"] = v.ranking_publico(contexto["filas"])
        contexto["ganadores"] = v.ganadores(contexto["filas"])
        contexto["n_calif"] = Calificacion.objects.filter(votacion=v).values("jurado").distinct().count()
        contexto["n_jurados"] = v.jurados.count()
        contexto["faltan"] = max(contexto["n_jurados"] - contexto["n_calif"], 0)
        contexto["rechazados"] = Registro.objects.filter(accion="voto_rechazado", detalle__startswith=v.nombre).count()
        registrar(request, "resultados_consultados", v.nombre)
    return render(request, "panel/resultados.html", contexto)


@solo_admin
def resultados_excel(request):
    """Excel con quién gana o va ganando en cada votación publicada de la edición activa."""
    edicion = _edicion(request)
    todas = list(Votacion.objects.filter(categoria__edicion=edicion, publicada=True)
                 .select_related("categoria").order_by("categoria__orden", "categoria__nombre", "pk"))
    contenido = libro_resultados(edicion, todas)
    registrar(request, "resultados_exportados", f"{edicion.nombre} (Excel, {len(todas)} votaciones)")
    respuesta = HttpResponse(contenido,
                             content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    nombre = f"resultados-{edicion.anio}-{timezone.localtime().strftime('%Y%m%d-%H%M')}.xlsx"
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta


@solo_admin
def resultados_csv(request, pk):
    v = get_object_or_404(Votacion, pk=pk)
    filas, total = v.resultados_ponderados()
    registrar(request, "resultados_exportados", f"{v.nombre} (CSV)")
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="resultados-votacion-{v.pk}.csv"'
    respuesta.write("﻿")  # BOM para que Excel abra bien las tildes
    w = csv.writer(respuesta, delimiter=";")
    w.writerow(["Votación", v.nombre])
    w.writerow(["Estado", v.estado_etiqueta])
    w.writerow(["Generado", timezone.localtime().strftime("%Y-%m-%d %H:%M")])
    w.writerow(["Modo de resultado", f"{v.modalidad} (pendiente de validación, P-06)"])
    w.writerow([])
    c = lambda x: f"{x:.1f}".replace(".", ",")
    final = "Resultado final %" if not v.es_independiente else "Resultado final % (no aplica: modo independiente)"
    w.writerow(["Opción", "Votos del público", "% público", "Promedio jurado", "% jurado", final])
    for o in filas:
        w.writerow([o.nombre, o.n_votos, c(o.pct_publico), c(o.promedio) if o.promedio is not None else "",
                    c(o.pct_jurado), c(o.final) if o.final is not None else ""])
    w.writerow(["TOTAL", total, "100", "", "100", "100" if not v.es_independiente else ""])
    return respuesta


@solo_admin
def votos(request):
    """Consulta administrativa de votos (Entrega 3 · CP-08): lo mismo que está en la tabla votaciones_voto."""
    edicion = _edicion(request)
    lista = Voto.objects.filter(edicion=edicion).select_related("usuario", "categoria", "votacion", "opcion")
    cat_id, vot_id, buscar = request.GET.get("categoria"), request.GET.get("votacion"), request.GET.get("q", "").strip()
    if cat_id and cat_id.isdigit():
        lista = lista.filter(categoria_id=cat_id)
    if vot_id and vot_id.isdigit():
        lista = lista.filter(votacion_id=vot_id)
    if buscar:
        lista = lista.filter(Q(codigo__icontains=buscar) | Q(usuario__email__icontains=buscar))
    # Protección de datos: cada consulta de votos queda en la auditoría, con los filtros usados.
    filtros = ", ".join(f"{k}={v}" for k, v in (("categoria", cat_id), ("votacion", vot_id), ("busqueda", buscar)) if v)
    registrar(request, "consulta_votos", filtros or "sin filtros")
    por_categoria = (Voto.objects.filter(edicion=edicion).values("categoria__nombre")
                     .annotate(n=Count("id"), votantes=Count("usuario", distinct=True)).order_by("categoria__nombre"))
    return render(request, "panel/votos.html", {
        "seccion": "votos", "votos": lista[:500], "total": lista.count(), "edicion": edicion,
        "categorias": Categoria.objects.filter(edicion=edicion).order_by("orden", "nombre"),
        "votaciones": Votacion.objects.filter(categoria__edicion=edicion).order_by("categoria__orden", "nombre"),
        "por_categoria": por_categoria, "f_cat": cat_id or "", "f_vot": vot_id or "", "q": buscar,
    })


@solo_admin
def auditoria(request):
    registros = Registro.objects.select_related("usuario")[:200]
    return render(request, "panel/auditoria.html", {"seccion": "auditoria", "registros": registros})
