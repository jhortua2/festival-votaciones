from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuario del sistema: votante o administrador (entidad Usuario del modelo conceptual).

    El dato de identificación del votante (correo, cédula, celular...) está
    PENDIENTE DE VALIDACIÓN con el cliente (P-01). Por ahora se usa el correo,
    que es único. El campo `documento` queda listo por si el cliente lo exige.
    """

    class Rol(models.TextChoices):
        VOTANTE = "votante", "Votante"
        ADMIN = "admin", "Administrador"

    email = models.EmailField("correo electrónico", unique=True)
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.VOTANTE)
    documento = models.CharField(
        "documento de identidad", max_length=20, blank=True,
        help_text="Pendiente de validación (P-01): aún no se sabe si se pedirá.",
    )
    acepto_tratamiento_datos = models.BooleanField(default=False)
    fecha_aceptacion_datos = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    @property
    def es_admin(self) -> bool:
        return self.rol == self.Rol.ADMIN or self.is_superuser

    def __str__(self):
        return self.get_full_name() or self.email or self.username
