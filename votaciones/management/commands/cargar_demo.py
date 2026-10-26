"""python manage.py cargar_demo [--reiniciar]

Carga datos de EJEMPLO ILUSTRATIVO para probar el sistema. Las categorías,
votaciones y opciones NO están aprobadas por el cliente (Entrega 1).
Las fechas se calculan a partir de hoy para que siempre haya votaciones
abiertas, próximas y cerradas.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from auditoria.models import Registro
from cuentas.models import Usuario
from votaciones.models import Calificacion, Categoria, Edicion, Opcion, Votacion, Voto

ADMIN = ("admin@festival.test", "Festival2027!")
VOTANTE = ("votante@festival.test", "Vallenato2027!")
JURADO = ("jurado@festival.test", "Jurado2027!")
# Datos de prueba: la base queda solo con tres usuarios, uno por rol.


class Command(BaseCommand):
    help = "Carga datos de ejemplo (edición 2027, categorías, votaciones, opciones, usuarios y votos)."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true", help="Borra los datos de votaciones antes de cargar.")

    @transaction.atomic
    def handle(self, *args, reiniciar=False, **opts):
        if reiniciar:
            Calificacion.objects.all().delete()
            Voto.objects.all().delete()
            Opcion.objects.all().delete()
            Votacion.objects.all().delete()
            Categoria.objects.all().delete()
            Edicion.objects.all().delete()
            Registro.objects.all().delete()
            Usuario.objects.all().delete()  # la base queda solo con los tres usuarios de prueba
            self.stdout.write("Datos anteriores borrados (también todos los usuarios).")

        if Edicion.objects.filter(anio=2027).exists():
            self.stdout.write(self.style.WARNING("Ya hay datos de la edición 2027. Use --reiniciar para volver a cargarlos."))
            self._credenciales()
            return

        ahora = timezone.now()
        dia = timedelta(days=1)

        admin, _ = Usuario.objects.get_or_create(email=ADMIN[0], defaults={
            "username": ADMIN[0], "first_name": "Admin", "last_name": "Fundación",
            "rol": Usuario.Rol.ADMIN, "is_staff": True, "is_superuser": True, "acepto_tratamiento_datos": True,
        })
        admin.set_password(ADMIN[1]); admin.save()
        ana, _ = Usuario.objects.get_or_create(email=VOTANTE[0], defaults={
            "username": VOTANTE[0], "first_name": "Ana María", "last_name": "Pérez", "acepto_tratamiento_datos": True,
            "fecha_aceptacion_datos": ahora,
        })
        ana.set_password(VOTANTE[1]); ana.save()

        jurado, _ = Usuario.objects.get_or_create(email=JURADO[0], defaults={
            "username": JURADO[0], "first_name": "Rafael", "last_name": "Calderón", "rol": Usuario.Rol.JURADO,
            "acepto_tratamiento_datos": True,
        })
        jurado.set_password(JURADO[1]); jurado.save()
        jurados = [jurado]

        # Solo la edición activa. Otras ediciones se registran desde el Admin o el panel (RF-03).
        ed = Edicion.objects.create(anio=2027, numero=60, nombre="Festival de la Leyenda Vallenata 2027", activa=True)

        musica = Categoria.objects.create(edicion=ed, nombre="Música", descripcion="Canciones y presentaciones en tarima", orden=1, icono="acordeon", color="#F4B400")
        pilon = Categoria.objects.create(edicion=ed, nombre="Piloneras", descripcion="Grupos del desfile de apertura", orden=2, icono="pollera", color="#E23D32")
        publico = Categoria.objects.create(edicion=ed, nombre="Reconocimientos del público", descripcion="Vestuario, ambiente y otros", orden=3, icono="sombrero", color="#35B2A1")

        V, F, M = Votacion.Visibilidad, Votacion.Frecuencia, Votacion.Modo
        cancion = self._votacion(musica, "Mejor canción inédita", "Escoge la canción inédita que más te llegó al corazón. Ejemplo del modo combinado: jurado 70 % + público 30 % (propuesta del equipo, pendiente de validación).",
                                 ahora - dia, ahora + 3 * dia, F.UNA_VEZ, V.SOLO_ADMIN, [
                                     ("Brisa del Guatapurí", "Paseo", "#F4B400"), ("Pilón de mi tierra", "Merengue", "#E23D32"),
                                     ("Sabana de sol", "Son", "#35B2A1"), ("Puya pa' la plaza", "Puya", "#7A5CFF")])
        aire = self._votacion(musica, "Tu aire favorito", "¿Cuál de los cuatro aires te pone a bailar? Puedes votar una vez al día. Es solo del público.",
                              ahora - 2 * dia, ahora + 4 * dia, F.DIARIA, V.TIEMPO_REAL, [
                                  ("Paseo", "Aire", "#F4B400"), ("Merengue", "Aire", "#E23D32"), ("Son", "Aire", "#35B2A1"), ("Puya", "Aire", "#7A5CFF")])
        self._votacion(musica, "Mejor presentación en tarima", "Se abrirá durante las rondas finales.",
                       ahora + 5 * dia, ahora + 8 * dia, F.UNA_VEZ, V.AL_CIERRE, [
                           ("Conjunto inscrito #03", "Tarima Francisco el Hombre", "#F4B400"), ("Conjunto inscrito #11", "Tarima Francisco el Hombre", "#E23D32"),
                           ("Conjunto inscrito #24", "Tarima Francisco el Hombre", "#35B2A1")])
        piloneras = self._votacion(pilon, "Grupo de piloneras favorito", "Votación de ejemplo ya cerrada en modo independiente: el jurado da el fallo oficial y el público un reconocimiento aparte.",
                                   ahora - 10 * dia, ahora - 2 * dia, F.UNA_VEZ, V.AL_CIERRE, [
                                       ("Grupo Mayores A", "Categoría mayores", "#E23D32"), ("Grupo Juvenil B", "Categoría juvenil", "#F4B400"),
                                       ("Grupo Infantil C", "Categoría infantil", "#35B2A1")])
        borrador = Votacion.objects.create(categoria=publico, nombre="Vestuario más colorido", descripcion="Borrador: falta agregar opciones.",
                                           apertura=ahora + 6 * dia, cierre=ahora + 9 * dia, modo=M.PUBLICO)

        # Modo de resultado (RN-11 / P-06, pendiente de validación): se muestran los dos escenarios.
        # Combinado (propuesta 70/30): canción inédita. Independiente: piloneras y tarima. Solo público: aire.
        Votacion.objects.filter(pk=cancion.pk).update(modo=M.COMBINADO, peso_jurado=70)
        Votacion.objects.filter(pk=aire.pk).update(modo=M.PUBLICO)
        for v in Votacion.objects.exclude(modo=M.PUBLICO):
            v.jurados.set(jurados)

        Opcion.objects.create(votacion=borrador, nombre="Comparsa de ejemplo", detalle="Desfile", color="#35B2A1")

        # Votos de ejemplo: solo los del votante de prueba en la votación ya cerrada, para que haya
        # algo que consultar en el histórico. Las votaciones abiertas quedan libres para votar en la demo.
        self._votar(piloneras, ana, 1, piloneras.cierre - dia)

        # Calificación del jurado en la votación cerrada (bypass del servicio solo para sembrar datos).
        self._calificar(piloneras, jurados, [[8, 7, 9]], piloneras.cierre - dia)

        Registro.objects.create(usuario=admin, accion="datos_demo", detalle="Carga de datos de ejemplo")
        self.stdout.write(self.style.SUCCESS(f"Datos de ejemplo cargados: {Edicion.objects.count()} edición, {Categoria.objects.count()} categorías, {Votacion.objects.count()} votaciones, {Voto.objects.count()} voto(s), {Usuario.objects.count()} usuarios y {Calificacion.objects.count()} calificaciones."))
        self._credenciales()

    def _votacion(self, cat, nombre, desc, apertura, cierre, frecuencia, visibilidad, opciones):
        v = Votacion.objects.create(categoria=cat, nombre=nombre, descripcion=desc, apertura=apertura, cierre=cierre,
                                    frecuencia=frecuencia, visibilidad=visibilidad, publicada=True)
        for i, (n, d, c) in enumerate(opciones, start=1):
            Opcion.objects.create(votacion=v, nombre=n, detalle=d, color=c, orden=i)
        return v

    def _votar(self, votacion, usuario, indice, momento):
        opcion = list(votacion.opciones.order_by("orden"))[indice]
        Voto.objects.create(usuario=usuario, votacion=votacion, opcion=opcion, clave_frecuencia="unica", fecha=momento)

    def _calificar(self, votacion, jurados, tablas, momento):
        opciones = list(votacion.opciones.order_by("orden"))
        Calificacion.objects.bulk_create([
            Calificacion(jurado=j, votacion=votacion, opcion=o, puntaje=p, fecha=momento)
            for j, puntajes in zip(jurados, tablas) for o, p in zip(opciones, puntajes)
        ])

    def _credenciales(self):
        self.stdout.write("")
        self.stdout.write("  Usuarios de prueba (no son credenciales reales):")
        self.stdout.write("  Administrador:  " + ADMIN[0] + "  /  " + ADMIN[1])
        self.stdout.write("  Votante:        " + VOTANTE[0] + "  /  " + VOTANTE[1])
        self.stdout.write("  Jurado:         " + JURADO[0] + "  /  " + JURADO[1])
        self.stdout.write("  Arranque con:   py manage.py runserver 8888")
        self.stdout.write("  Sitio: http://localhost:8888   Panel: http://localhost:8888/panel/")
