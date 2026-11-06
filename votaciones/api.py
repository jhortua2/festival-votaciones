"""API GET de consulta (Entrega 3 · CP-10).

GET /api/categorias/          → categorías de la edición activa con sus votaciones y opciones
GET /api/categorias/?anio=2027 → lo mismo para otra edición

Solo lectura y pública (no expone datos de usuarios ni votos). Todo sale de MySQL con el ORM
de Django y se responde con JsonResponse.
"""
from django.db.models import Prefetch
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Categoria, Edicion, Opcion, Votacion


def _fecha(valor):
    return timezone.localtime(valor).isoformat() if valor else None


@require_GET
def categorias(request):
    anio = request.GET.get("anio")
    if anio:
        if not anio.isdigit():
            return JsonResponse({"error": "El parámetro anio debe ser un número, por ejemplo ?anio=2027."}, status=400)
        edicion = Edicion.objects.filter(anio=int(anio)).first()
    else:
        edicion = Edicion.actual()
    if edicion is None:
        return JsonResponse({"error": "No hay una edición con ese año."}, status=404)

    opciones = Prefetch("opciones", queryset=Opcion.objects.filter(activa=True).order_by("orden", "nombre"))
    votaciones = Prefetch(
        "votaciones",
        queryset=Votacion.objects.filter(publicada=True).order_by("apertura", "nombre").prefetch_related(opciones),
    )
    cats = Categoria.objects.filter(edicion=edicion, activa=True).order_by("orden", "nombre").prefetch_related(votaciones)

    datos = {
        "edicion": {"id": edicion.pk, "anio": edicion.anio, "numero": edicion.numero,
                    "nombre": edicion.nombre, "activa": edicion.activa},
        "regla": "Un voto por usuario, categoría y edición.",
        "total_categorias": len(cats),
        "categorias": [
            {
                "id": c.pk,
                "nombre": c.nombre,
                "descripcion": c.descripcion,
                "orden": c.orden,
                "votaciones": [
                    {
                        "id": v.pk,
                        "nombre": v.nombre,
                        "estado": v.estado,
                        "apertura": _fecha(v.apertura),
                        "cierre": _fecha(v.cierre),
                        "opciones": [
                            {"id": o.pk, "nombre": o.nombre, "detalle": o.detalle, "orden": o.orden}
                            for o in v.opciones.all()
                        ],
                    }
                    for v in c.votaciones.all()
                ],
            }
            for c in cats
        ],
    }
    return JsonResponse(datos, json_dumps_params={"ensure_ascii": False, "indent": 2})
