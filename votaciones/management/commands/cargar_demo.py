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

import os

# En el PC se usan las claves de prueba del README. En un servidor público se ponen claves propias
# con las variables DEMO_CLAVE_ADMIN, DEMO_CLAVE_VOTANTE y DEMO_CLAVE_JURADO (no se escriben en ningún archivo).
ADMIN = ("admin@festival.test", os.environ.get("DEMO_CLAVE_ADMIN") or "Festival2027!")
VOTANTE = ("votante@festival.test", os.environ.get("DEMO_CLAVE_VOTANTE") or "Vallenato2027!")
JURADO = ("jurado@festival.test", os.environ.get("DEMO_CLAVE_JURADO") or "Jurado2027!")
_CLAVES_PROPIAS = all(os.environ.get(v) for v in ("DEMO_CLAVE_ADMIN", "DEMO_CLAVE_VOTANTE", "DEMO_CLAVE_JURADO"))
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
        rey = Categoria.objects.create(edicion=ed, nombre="Rey Vallenato", descripcion="Concurso de acordeoneros profesionales", orden=4, icono="acordeon", color="#E23D32")

        V, M = Votacion.Visibilidad, Votacion.Modo
        cancion = self._votacion(musica, "Mejor canción inédita", "Escoge la canción inédita que más te llegó al corazón. Ejemplo del modo combinado: jurado 70 % + público 30 % (propuesta del equipo, pendiente de validación).",
                                 ahora - dia, ahora + 3 * dia, V.SOLO_ADMIN, [
                                     ("Brisa del Guatapurí", "Paseo", "#F4B400"), ("Pilón de mi tierra", "Merengue", "#E23D32"),
                                     ("Sabana de sol", "Son", "#35B2A1"), ("Puya pa' la plaza", "Puya", "#7A5CFF")])
        aire = self._votacion(musica, "Tu aire favorito", "¿Cuál de los cuatro aires te pone a bailar? Es solo del público. Recuerda: en la categoría Música eliges una sola votación.",
                              ahora - 2 * dia, ahora + 4 * dia, V.TIEMPO_REAL, [
                                  ("Paseo", "Aire", "#F4B400"), ("Merengue", "Aire", "#E23D32"), ("Son", "Aire", "#35B2A1"), ("Puya", "Aire", "#7A5CFF")])
        self._votacion(musica, "Mejor presentación en tarima", "Se abrirá durante las rondas finales.",
                       ahora + 5 * dia, ahora + 8 * dia, V.AL_CIERRE, [
                           ("Conjunto inscrito #03", "Tarima Francisco el Hombre", "#F4B400"), ("Conjunto inscrito #11", "Tarima Francisco el Hombre", "#E23D32"),
                           ("Conjunto inscrito #24", "Tarima Francisco el Hombre", "#35B2A1")])
        piloneras = self._votacion(pilon, "Grupo de piloneras favorito", "Votación de ejemplo ya cerrada en modo independiente: el jurado da el fallo oficial y el público un reconocimiento aparte.",
                                   ahora - 10 * dia, ahora - 2 * dia, V.AL_CIERRE, [
                                       ("Grupo Mayores A", "Categoría mayores", "#E23D32"), ("Grupo Juvenil B", "Categoría juvenil", "#F4B400"),
                                       ("Grupo Infantil C", "Categoría infantil", "#35B2A1")])
        self._votacion(rey, "Tu Rey Vallenato favorito", "Escoge al acordeonero que más te gustó en la tarima.",
                       ahora - dia, ahora + 5 * dia, V.AL_CIERRE, [
                           ("Acordeonero inscrito #05", "Paseo", "#F4B400"), ("Acordeonero inscrito #12", "Merengue", "#E23D32"),
                           ("Acordeonero inscrito #18", "Son", "#35B2A1")])
        # Categoría todavía no habilitada para votar: su votación abre más adelante (CP-05)
        vestuario = self._votacion(publico, "Vestuario más colorido", "Se habilita durante el desfile de piloneras.",
                                   ahora + 6 * dia, ahora + 9 * dia, V.AL_CIERRE, [
                                       ("Comparsa Las Marías", "Desfile", "#35B2A1"), ("Comparsa El Cardonal", "Desfile", "#F4B400")])

        # Modo de resultado (RN-11 / P-06, pendiente de validación): se muestran los dos escenarios.
        # Combinado (propuesta 70/30): canción inédita. Independiente: piloneras y tarima. Solo público: aire.
        Votacion.objects.filter(pk=cancion.pk).update(modo=M.COMBINADO, peso_jurado=70)
        Votacion.objects.filter(pk__in=[aire.pk, vestuario.pk]).update(modo=M.PUBLICO)
        for v in Votacion.objects.exclude(modo=M.PUBLICO):
            v.jurados.set(jurados)

        # Voto de ejemplo: el votante de prueba ya votó en Piloneras (votación cerrada), para que haya
        # historial. Música y Rey Vallenato quedan libres para demostrar el voto válido, el duplicado
        # y el voto en otra categoría (Entrega 3).
        self._votar(piloneras, ana, 1, piloneras.cierre - dia)

        # Calificación del jurado en la votación cerrada (bypass del servicio solo para sembrar datos).
        self._calificar(piloneras, jurados, [[8, 7, 9]], piloneras.cierre - dia)

        Registro.objects.create(usuario=admin, accion="datos_demo", detalle="Carga de datos de ejemplo")
        self.stdout.write(self.style.SUCCESS(f"Datos de ejemplo cargados: {Edicion.objects.count()} edición, {Categoria.objects.count()} categorías, {Votacion.objects.count()} votaciones, {Voto.objects.count()} voto(s), {Usuario.objects.count()} usuarios y {Calificacion.objects.count()} calificaciones."))
        self._credenciales()

    def _votacion(self, cat, nombre, desc, apertura, cierre, visibilidad, opciones):
        v = Votacion.objects.create(categoria=cat, nombre=nombre, descripcion=desc, apertura=apertura, cierre=cierre,
                                    visibilidad=visibilidad, publicada=True)
        for i, (n, d, c) in enumerate(opciones, start=1):
            Opcion.objects.create(votacion=v, nombre=n, detalle=d, color=c, orden=i)
        return v

    def _votar(self, votacion, usuario, indice, momento):
        opcion = list(votacion.opciones.order_by("orden"))[indice]
        Voto.objects.create(usuario=usuario, opcion=opcion, fecha=momento)

    def _calificar(self, votacion, jurados, tablas, momento):
        opciones = list(votacion.opciones.order_by("orden"))
        Calificacion.objects.bulk_create([
            Calificacion(jurado=j, votacion=votacion, opcion=o, puntaje=p, fecha=momento)
            for j, puntajes in zip(jurados, tablas) for o, p in zip(opciones, puntajes)
        ])

    def _credenciales(self):
        self.stdout.write("")
        if _CLAVES_PROPIAS:
            # En el servidor nunca se imprimen las claves (quedarían en los registros del servicio)
            self.stdout.write("  Usuarios de prueba creados con las claves de las variables DEMO_CLAVE_*.")
            return
        self.stdout.write("  Usuarios de prueba (no son credenciales reales):")
        self.stdout.write("  Administrador:  " + ADMIN[0] + "  /  " + ADMIN[1])
        self.stdout.write("  Votante:        " + VOTANTE[0] + "  /  " + VOTANTE[1])
        self.stdout.write("  Jurado:         " + JURADO[0] + "  /  " + JURADO[1])
        self.stdout.write("  Arranque con:   py manage.py runserver 8888")
        self.stdout.write("  Sitio: http://localhost:8888   Panel: http://localhost:8888/panel/")
