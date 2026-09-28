"""Modelo de datos: Edición → Categoría → Votación → Opción → Voto (+ Usuario en la app cuentas).

Cada clase corresponde a una entidad del modelo conceptual de la Entrega 1.
Las reglas de negocio que dependen del cliente se dejan como opciones
configurables por votación (frecuencia, visibilidad), no fijas en el código.
"""
import secrets
import string

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Edicion(models.Model):
    anio = models.PositiveIntegerField("año", unique=True)
    nombre = models.CharField(max_length=150)
    numero = models.PositiveIntegerField("número de edición", null=True, blank=True)
    fecha_inicio = models.DateField(null=True, blank=True, help_text="Pendiente de validación")
    fecha_fin = models.DateField(null=True, blank=True, help_text="Pendiente de validación")
    activa = models.BooleanField(default=False, help_text="Solo una edición activa se muestra al público.")

    class Meta:
        ordering = ["-anio"]
        verbose_name = "edición"
        verbose_name_plural = "ediciones"

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.activa:  # Mantener una única edición activa
            Edicion.objects.exclude(pk=self.pk).filter(activa=True).update(activa=False)

    @classmethod
    def actual(cls):
        return cls.objects.filter(activa=True).first()


class Categoria(models.Model):
    class Icono(models.TextChoices):
        ACORDEON = "acordeon", "Acordeón"
        POLLERA = "pollera", "Pollera / piloneras"
        SOMBRERO = "sombrero", "Sombrero"
        CAJA = "caja", "Caja vallenata"

    edicion = models.ForeignKey(Edicion, on_delete=models.PROTECT, related_name="categorias")
    nombre = models.CharField(max_length=120)
    descripcion = models.CharField("descripción", max_length=255, blank=True)
    orden = models.PositiveIntegerField(default=1)
    icono = models.CharField(max_length=20, choices=Icono.choices, default=Icono.ACORDEON)
    color = models.CharField(max_length=7, default="#F4B400", help_text="Color principal de la tarjeta (hex)")
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        constraints = [
            models.UniqueConstraint(fields=["edicion", "nombre"], name="categoria_nombre_unico_por_edicion"),
        ]

    def __str__(self):
        return self.nombre

    def votaciones_publicas(self):
        return self.votaciones.filter(publicada=True)


class Votacion(models.Model):
    class Frecuencia(models.TextChoices):
        # RN-06: pendiente de validación. Se deja configurable por votación.
        UNA_VEZ = "una_vez", "Un voto por persona en toda la votación"
        DIARIA = "diaria", "Un voto por persona por día"

    class Visibilidad(models.TextChoices):
        # RN-10: pendiente de validación. Se deja configurable por votación.
        SOLO_ADMIN = "solo_admin", "Solo administradores"
        AL_CIERRE = "al_cierre", "Públicos al cierre"
        TIEMPO_REAL = "tiempo_real", "Públicos en tiempo real"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PROXIMA = "proxima", "Próxima"
        ABIERTA = "abierta", "Abierta"
        CERRADA = "cerrada", "Cerrada"

    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="votaciones")
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField("descripción", blank=True)
    apertura = models.DateTimeField()
    cierre = models.DateTimeField()
    frecuencia = models.CharField(max_length=12, choices=Frecuencia.choices, default=Frecuencia.UNA_VEZ)
    visibilidad = models.CharField(max_length=12, choices=Visibilidad.choices, default=Visibilidad.SOLO_ADMIN)
    publicada = models.BooleanField(default=False)
    cerrada_manualmente = models.DateTimeField(null=True, blank=True)
    justificacion_cierre = models.CharField(max_length=255, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["apertura", "nombre"]
        verbose_name = "votación"
        verbose_name_plural = "votaciones"
        constraints = [
            models.CheckConstraint(condition=models.Q(cierre__gt=models.F("apertura")), name="cierre_posterior_apertura"),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.apertura and self.cierre and self.cierre <= self.apertura:
            raise ValidationError({"cierre": "El cierre debe ser posterior a la apertura."})

    # --- Estado calculado: el sistema "abre" y "cierra" según las fechas (actor Sistema) ---
    @property
    def estado(self):
        ahora = timezone.now()
        if not self.publicada:
            return self.Estado.BORRADOR
        if self.cerrada_manualmente or ahora >= self.cierre:
            return self.Estado.CERRADA
        if ahora < self.apertura:
            return self.Estado.PROXIMA
        return self.Estado.ABIERTA

    @property
    def estado_etiqueta(self):
        return self.Estado(self.estado).label

    @property
    def esta_abierta(self):
        return self.estado == self.Estado.ABIERTA

    def opciones_activas(self):
        return self.opciones.filter(activa=True)

    def puede_publicarse(self):
        """RN-07: se necesitan mínimo dos opciones activas."""
        return self.opciones_activas().count() >= 2

    def resultados_publicos(self):
        """RN-10: ¿un visitante puede ver resultados según la visibilidad configurada?"""
        if self.visibilidad == self.Visibilidad.TIEMPO_REAL:
            return self.estado in (self.Estado.ABIERTA, self.Estado.CERRADA)
        if self.visibilidad == self.Visibilidad.AL_CIERRE:
            return self.estado == self.Estado.CERRADA
        return False

    def conteo(self):
        """Votos por opción, ordenados de mayor a menor, con porcentaje."""
        opciones = list(self.opciones.annotate(total=models.Count("votos")).order_by("-total", "orden"))
        total = sum(o.total for o in opciones)
        for o in opciones:
            o.porcentaje = (o.total * 100 / total) if total else 0
        return opciones, total


def _color_por_defecto():
    return "#E23D32"


class Opcion(models.Model):
    votacion = models.ForeignKey(Votacion, on_delete=models.CASCADE, related_name="opciones")
    nombre = models.CharField(max_length=150)
    detalle = models.CharField(max_length=150, blank=True, help_text="Ej.: aire (paseo, merengue...) o autor")
    descripcion = models.TextField("descripción", blank=True)
    imagen = models.ImageField(upload_to="opciones/", blank=True)
    color = models.CharField(max_length=7, default=_color_por_defecto, help_text="Se usa si no hay imagen")
    orden = models.PositiveIntegerField(default=1)
    activa = models.BooleanField(default=True)
    justificacion_inactivacion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "opción"
        verbose_name_plural = "opciones"

    def __str__(self):
        return self.nombre

    @property
    def inicial(self):
        return (self.nombre[:1] or "?").upper()

    def tiene_votos(self):
        return self.votos.exists()


def generar_codigo():
    alfabeto = string.ascii_uppercase + string.digits
    return "VLL-" + "".join(secrets.choice(alfabeto) for _ in range(4)) + "-" + "".join(secrets.choice(string.digits) for _ in range(4))


class Voto(models.Model):
    """Un voto emitido. No se modifica ni se borra desde la aplicación (RN-05, RNF-02).

    `votacion` se guarda aunque se pueda deducir de la opción, para que la base de
    datos haga cumplir la regla de frecuencia con una restricción única:
    (usuario, votacion, clave_frecuencia). Si la votación es de un voto en total,
    la clave es "unica"; si es diaria, la clave es la fecha (AAAA-MM-DD).
    """

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="votos")
    votacion = models.ForeignKey(Votacion, on_delete=models.PROTECT, related_name="votos")
    opcion = models.ForeignKey(Opcion, on_delete=models.PROTECT, related_name="votos")
    clave_frecuencia = models.CharField(max_length=10)
    codigo = models.CharField("código de comprobante", max_length=20, unique=True, default=generar_codigo)
    fecha = models.DateTimeField(default=timezone.now)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "voto"
        verbose_name_plural = "votos"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "votacion", "clave_frecuencia"], name="un_voto_segun_frecuencia",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} · {self.opcion}"
