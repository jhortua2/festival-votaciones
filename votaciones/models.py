"""Modelo de datos: Edición → Categoría → Votación → Opción → Voto / Calificación (+ Usuario en la app cuentas).

Cada clase corresponde a una entidad del modelo conceptual de la Entrega 1.
Las reglas de negocio que dependen del cliente se dejan como opciones
configurables por votación (frecuencia, visibilidad, peso del jurado), no fijas en el código.

Resultado de una votación (RN-11): todavía no está definido si el voto del público
es independiente del jurado o se combina con él (P-06). Por eso cada votación tiene
un modo configurable: solo público, solo jurado, independiente o combinado. El
70 % jurado / 30 % público del modo combinado es una propuesta del equipo.
"""
import secrets
import string

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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

    class Modo(models.TextChoices):
        # RN-11 / P-06: pendiente de validación. La Fundación debe decidir el modo.
        PUBLICO = "publico", "Solo público"
        JURADO = "jurado", "Solo jurado"
        INDEPENDIENTE = "independiente", "Independiente: fallo del jurado y premio del público por separado"
        COMBINADO = "combinado", "Combinado: jurado y público en un solo resultado"

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
    # RN-11: cómo se define el resultado. Pendiente de validación (P-06).
    modo = models.CharField(
        "modo de resultado", max_length=14, choices=Modo.choices, default=Modo.INDEPENDIENTE,
        help_text="Pendiente de validación (P-06). Independiente no mezcla el voto del público con el fallo del jurado.",
    )
    # Solo aplica al modo combinado: peso del jurado en el resultado final.
    peso_jurado = models.PositiveSmallIntegerField(
        "peso del jurado (%)", default=70, validators=[MinValueValidator(1), MaxValueValidator(99)],
        help_text="Solo en modo combinado. El público tiene el resto. Propuesta del equipo 70/30, pendiente de validación (P-06).",
    )
    escala_maxima = models.PositiveSmallIntegerField(
        "puntaje máximo del jurado", default=10, validators=[MinValueValidator(2), MaxValueValidator(100)],
        help_text="Cada jurado califica de 1 a este valor. Pendiente de validación (P-16).",
    )
    jurados = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="votaciones_como_jurado",
        limit_choices_to={"rol": "jurado"}, help_text="Solo los jurados asignados pueden calificar esta votación (RN-13).",
    )
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
            models.CheckConstraint(condition=models.Q(peso_jurado__gte=1, peso_jurado__lte=99), name="peso_jurado_entre_1_y_99"),
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

    # --- Modo de resultado: jurado y público (RN-11 / P-06) ---
    @property
    def peso_publico(self):
        return 100 - self.peso_jurado

    @property
    def tiene_jurado(self):
        return self.modo != self.Modo.PUBLICO

    @property
    def tiene_publico(self):
        return self.modo != self.Modo.JURADO

    @property
    def es_combinado(self):
        return self.modo == self.Modo.COMBINADO

    @property
    def es_independiente(self):
        return self.modo == self.Modo.INDEPENDIENTE

    @property
    def modalidad(self):
        if self.es_combinado:
            return f"Jurado {self.peso_jurado} % + público {self.peso_publico} %"
        if self.es_independiente:
            return "Jurado y público por separado"
        return self.get_modo_display()

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

    def resultados_ponderados(self):
        """Resultados por opción según el modo (RN-11).

        - % del público: votos de la opción / total de votos de la votación.
        - % del jurado: suma de puntajes de la opción / suma de todos los puntajes.
        - Combinado: final = peso_jurado × % del jurado + peso_público × % del público.
        - Independiente: no hay un resultado final mezclado (final = None); el orden es el del jurado
          y el público tiene su propio orden por votos.
        """
        # Se consultan por separado: unir votos y calificaciones en una sola consulta multiplicaría las sumas.
        opciones = list(self.opciones.annotate(n_votos=models.Count("votos")).order_by("orden"))
        jurado = {f["opcion"]: f for f in Calificacion.objects.filter(votacion=self).values("opcion").annotate(
            suma=models.Sum("puntaje"), n=models.Count("id"))}
        for o in opciones:
            o.suma_puntaje = jurado.get(o.pk, {}).get("suma") or 0
            o.n_calif = jurado.get(o.pk, {}).get("n") or 0
        total_votos = sum(o.n_votos for o in opciones)
        total_puntaje = sum(o.suma_puntaje or 0 for o in opciones)
        for o in opciones:
            o.promedio = (o.suma_puntaje / o.n_calif) if o.n_calif else None
            o.pct_publico = (o.n_votos * 100 / total_votos) if total_votos else 0
            o.pct_jurado = (o.suma_puntaje * 100 / total_puntaje) if total_puntaje else 0
            if self.es_combinado:
                o.aporte_jurado = self.peso_jurado * o.pct_jurado / 100
                o.aporte_publico = self.peso_publico * o.pct_publico / 100
                o.final = o.aporte_jurado + o.aporte_publico
            elif self.modo == self.Modo.JURADO:
                o.aporte_jurado, o.aporte_publico, o.final = o.pct_jurado, 0, o.pct_jurado
            elif self.modo == self.Modo.PUBLICO:
                o.aporte_jurado, o.aporte_publico, o.final = 0, o.pct_publico, o.pct_publico
            else:  # Independiente: cada uno por su lado
                o.aporte_jurado = o.aporte_publico = o.final = None
        if self.es_independiente:
            opciones.sort(key=lambda o: (-o.pct_jurado, o.orden))
        else:
            opciones.sort(key=lambda o: (-o.final, o.orden))
        return opciones, total_votos

    def ranking_publico(self, opciones=None):
        """Orden por votos del público (para el modo independiente)."""
        opciones = opciones if opciones is not None else self.resultados_ponderados()[0]
        return sorted(opciones, key=lambda o: (-o.n_votos, o.orden))

    def calificaciones_esperadas(self):
        """Jurados asignados × opciones activas."""
        return self.jurados.count() * self.opciones_activas().count()


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


class Calificacion(models.Model):
    """Puntaje que un jurado le da a una opción (RF-15). No se modifica después de enviarla (RN-14).

    Igual que en Voto, se guarda `votacion` para consultar rápido y para que la base
    de datos impida que un jurado califique dos veces la misma opción.
    """

    jurado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="calificaciones")
    votacion = models.ForeignKey(Votacion, on_delete=models.PROTECT, related_name="calificaciones")
    opcion = models.ForeignKey(Opcion, on_delete=models.PROTECT, related_name="calificaciones")
    puntaje = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    comentario = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "calificación"
        verbose_name_plural = "calificaciones"
        constraints = [
            models.UniqueConstraint(fields=["jurado", "opcion"], name="una_calificacion_por_jurado_y_opcion"),
            models.CheckConstraint(condition=models.Q(puntaje__gte=1), name="puntaje_minimo_1"),
        ]

    def __str__(self):
        return f"{self.opcion} · {self.puntaje}"
