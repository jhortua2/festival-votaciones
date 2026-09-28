from django.contrib import admin

from .models import Categoria, Edicion, Opcion, Votacion, Voto


@admin.register(Edicion)
class EdicionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "anio", "numero", "activa")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "edicion", "orden", "activa")
    list_filter = ("edicion", "activa")


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 0


@admin.register(Votacion)
class VotacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "apertura", "cierre", "publicada", "frecuencia", "visibilidad")
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
