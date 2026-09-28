from django.conf import settings
from django.db import models


class Registro(models.Model):
    """Bitácora de auditoría (RF-13, RNF-09): quién hizo qué, cuándo y desde qué IP."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="registros_auditoria",
    )
    accion = models.CharField(max_length=60)
    detalle = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} · {self.accion}"
