from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "rol", "is_active", "date_joined")
    list_filter = ("rol", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Festival", {"fields": ("rol", "documento", "acepto_tratamiento_datos", "fecha_aceptacion_datos")}),
    )
