"""python manage.py cargar_demo [--reiniciar]

Carga datos de EJEMPLO ILUSTRATIVO para probar el sistema. Las categorías,
votaciones y opciones NO están aprobadas por el cliente (Entrega 1).
Las fechas se calculan a partir de hoy para que siempre haya votaciones
abiertas, próximas y cerradas.
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from auditoria.models import Registro
from cuentas.models import Usuario
from votaciones.models import Calificacion, Categoria, Edicion, Opcion, Votacion, Voto

ADMIN = ("admin@festival.test", "Festival2027!")
VOTANTE = ("ana@festival.test", "Vallenato2027!")
JURADOS = [("jurado1@festival.test", "Rafael", "Calderón"), ("jurado2@festival.test", "Leandro", "Mejía"),
           ("jurado3@festival.test", "Rosa", "Ochoa")]
CLAVE_JURADO = "Jurado2027!"


class Command(BaseCommand):
    help = "Carga datos de ejemplo (ediciones 2026 y 2027, categorías, votaciones, opciones, usuarios y votos)."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true", help="Borra los datos de votaciones antes de cargar.")
        parser.add_argument("--votantes", type=int, default=60, help="Cantidad de votantes de prueba con votos (defecto 60).")

    @transaction.atomic
    def handle(self, *args, reiniciar=False, votantes=60, **opts):
        if reiniciar:
            Calificacion.objects.all().delete()
            Voto.objects.all().delete()
            Opcion.objects.all().delete()
            Votacion.objects.all().delete()
            Categoria.objects.all().delete()
            Edicion.objects.all().delete()
            Registro.objects.all().delete()
            Usuario.objects.filter(email__endswith="@festival.test").delete()
            self.stdout.write("Datos anteriores borrados.")

        if Edicion.objects.filter(anio=2027).exists():
            self.stdout.write(self.style.WARNING("Ya hay datos de la edición 2027. Use --reiniciar para volver a cargarlos."))
            self._credenciales()
            return

        random.seed(2027)
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

        jurados = []
        for correo, nombre, apellido in JURADOS:
            j, _ = Usuario.objects.get_or_create(email=correo, defaults={
                "username": correo, "first_name": nombre, "last_name": apellido, "rol": Usuario.Rol.JURADO,
                "acepto_tratamiento_datos": True,
            })
            j.set_password(CLAVE_JURADO); j.save()
            jurados.append(j)

        # Dos ediciones para mostrar que el sistema maneja varios años: la 2026 ya pasó y la 2027 es la activa.
        ed26 = Edicion.objects.create(anio=2026, numero=59, nombre="Festival de la Leyenda Vallenata 2026", activa=False)
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

        # Edición 2026 (ya pasada), con una votación cerrada del público para consultar el histórico.
        musica26 = Categoria.objects.create(edicion=ed26, nombre="Música", descripcion="Votaciones de la edición 59", orden=1, icono="acordeon", color="#F4B400")
        aire26 = self._votacion(musica26, "Tu aire favorito 2026", "Votación de ejemplo de la edición anterior. Solo del público.",
                                ahora - 180 * dia, ahora - 175 * dia, F.UNA_VEZ, V.AL_CIERRE, [
                                    ("Paseo", "Aire", "#F4B400"), ("Merengue", "Aire", "#E23D32"), ("Son", "Aire", "#35B2A1"), ("Puya", "Aire", "#7A5CFF")])
        Votacion.objects.filter(pk=aire26.pk).update(modo=M.PUBLICO)
        Opcion.objects.create(votacion=borrador, nombre="Comparsa de ejemplo", detalle="Desfile", color="#35B2A1")

        # Votantes de prueba y votos (bypass del servicio solo para sembrar datos)
        usuarios = [Usuario(username=f"votante{i:03d}@festival.test", email=f"votante{i:03d}@festival.test",
                            first_name=f"Votante {i}", acepto_tratamiento_datos=True) for i in range(1, votantes + 1)]
        for u in usuarios:
            u.set_unusable_password()
        Usuario.objects.bulk_create(usuarios)
        usuarios = list(Usuario.objects.filter(email__startswith="votante"))

        self._sembrar(cancion, usuarios, [5, 4, 2.5, 1.5], ahora)
        self._sembrar(aire, usuarios, [4, 3, 2, 3], ahora)
        self._sembrar(piloneras, usuarios, [3, 5, 2], piloneras.cierre - dia)
        self._sembrar(aire26, usuarios, [5, 2, 2, 3], aire26.cierre - dia)

        # Calificaciones del jurado (bypass del servicio solo para sembrar datos).
        # En "Canción favorita" falta un jurado por calificar, para mostrar resultados parciales.
        self._calificar(cancion, jurados[:2], [[7, 9, 8, 6], [6, 9, 7, 5]], ahora)
        self._calificar(piloneras, jurados, [[8, 7, 9], [9, 6, 9], [8, 7, 10]], piloneras.cierre - dia)

        Registro.objects.create(usuario=admin, accion="datos_demo", detalle="Carga de datos de ejemplo")
        self.stdout.write(self.style.SUCCESS(f"Datos de ejemplo cargados: 2 ediciones, {Categoria.objects.count()} categorías, {Votacion.objects.count()} votaciones, {Voto.objects.count()} votos, {len(jurados)} jurados y {Calificacion.objects.count()} calificaciones."))
        self._credenciales()

    def _votacion(self, cat, nombre, desc, apertura, cierre, frecuencia, visibilidad, opciones):
        v = Votacion.objects.create(categoria=cat, nombre=nombre, descripcion=desc, apertura=apertura, cierre=cierre,
                                    frecuencia=frecuencia, visibilidad=visibilidad, publicada=True)
        for i, (n, d, c) in enumerate(opciones, start=1):
            Opcion.objects.create(votacion=v, nombre=n, detalle=d, color=c, orden=i)
        return v

    def _sembrar(self, votacion, usuarios, pesos, momento):
        opciones = list(votacion.opciones.order_by("orden"))
        clave = timezone.localtime(momento).date().isoformat() if votacion.frecuencia == Votacion.Frecuencia.DIARIA else "unica"
        votantes = random.sample(usuarios, k=int(len(usuarios) * 0.85))
        Voto.objects.bulk_create([
            Voto(usuario=u, votacion=votacion, opcion=random.choices(opciones, weights=pesos)[0],
                 clave_frecuencia=clave, fecha=momento - timedelta(minutes=random.randint(0, 600)))
            for u in votantes
        ])

    def _calificar(self, votacion, jurados, tablas, momento):
        opciones = list(votacion.opciones.order_by("orden"))
        Calificacion.objects.bulk_create([
            Calificacion(jurado=j, votacion=votacion, opcion=o, puntaje=p, fecha=momento)
            for j, puntajes in zip(jurados, tablas) for o, p in zip(opciones, puntajes)
        ])

    def _credenciales(self):
        self.stdout.write("")
        self.stdout.write("  Administrador:  " + ADMIN[0] + "  /  " + ADMIN[1])
        self.stdout.write("  Votante:        " + VOTANTE[0] + "  /  " + VOTANTE[1])
        self.stdout.write("  Jurados:        jurado1@ · jurado2@ · jurado3@festival.test  /  " + CLAVE_JURADO)
        self.stdout.write("  Arranque con:   py manage.py runserver 8888")
        self.stdout.write("  Sitio: http://localhost:8888   Panel: http://localhost:8888/panel/")
