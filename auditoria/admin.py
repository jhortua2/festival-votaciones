from django.contrib import admin

from .models import Registro


@admin.register(Registro)
class RegistroAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "detalle", "ip")
    list_filter = ("accion",)
    search_fields = ("detalle", "usuario__email")

    # La auditoría es de solo lectura
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
