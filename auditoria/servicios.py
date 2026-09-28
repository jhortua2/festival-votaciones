from .models import Registro


def ip_de(request):
    """IP del cliente. Detrás de un proxy habría que leer X-Forwarded-For de forma segura."""
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR")


def registrar(request, accion, detalle="", usuario=None):
    """Guarda una acción en la bitácora. Si no se pasa usuario, se toma el de la sesión."""
    if usuario is None and request is not None and request.user.is_authenticated:
        usuario = request.user
    return Registro.objects.create(usuario=usuario, accion=accion, detalle=detalle, ip=ip_de(request))
