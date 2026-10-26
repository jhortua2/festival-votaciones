from django.contrib import admin

from .models import Calificacion, Categoria, Edicion, Opcion, Votacion, Voto


@admin.register(Edicion)
class EdicionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "anio_sin_punto", "numero", "activa")

    @admin.display(description="año", ordering="anio")
    def anio_sin_punto(self, obj):
        return str(obj.anio)  # evita que el año se vea como "2.027"


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "edicion", "orden", "activa")
    list_filter = ("edicion", "activa")


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 0
    # Solo los campos principales, para que la tabla de opciones quepa en pantalla.
    fields = ("nombre", "detalle", "orden", "activa")


@admin.register(Votacion)
class VotacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "apertura", "cierre", "publicada", "frecuencia", "visibilidad", "modo")
    filter_horizontal = ("jurados",)
    list_filter = ("categoria", "publicada")
    inlines = [OpcionInline]


@admin.register(Voto)
class VotoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "votacion", "opcion", "usuario", "fecha")
    list_filter = ("votacion",)

    # RN-05 / RNF-02: los votos no se editan ni se borran
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    """Solo lectura: las calificaciones del jurado no se modifican (RN-14)."""
    list_display = ("votacion", "opcion", "jurado", "puntaje", "fecha")
    list_filter = ("votacion",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
