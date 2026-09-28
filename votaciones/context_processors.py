from .models import Edicion


def festival(request):
    """Datos disponibles en todas las plantillas."""
    return {"edicion_actual": Edicion.actual()}
