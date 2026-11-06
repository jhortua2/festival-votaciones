"""Demuestra el control de duplicados ante solicitudes simultáneas (Entrega 3 · CP-09).

Uso:  py manage.py probar_concurrencia
      py manage.py probar_concurrencia --hilos 5

Crea un usuario temporal, envía varios votos al mismo tiempo en una misma categoría
(cada uno desde un hilo con su propia conexión a MySQL) y muestra cuántos quedaron
guardados. Al final borra el usuario temporal y sus votos, para no ensuciar los datos.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count

from auditoria.models import Registro
from cuentas.models import Usuario
from votaciones.concurrencia import votar_en_paralelo
from votaciones.models import Votacion, Voto

CORREO = "concurrencia@festival.test"


class Command(BaseCommand):
    help = "Envía votos simultáneos en una misma categoría y comprueba que solo queda uno (CP-09)."

    def add_arguments(self, parser):
        parser.add_argument("--hilos", type=int, default=2, help="Solicitudes simultáneas (defecto 2).")
        parser.add_argument("--conservar", action="store_true", help="No borrar el usuario temporal al final.")

    def handle(self, *args, hilos=2, conservar=False, **opts):
        votacion = next((v for v in Votacion.objects.filter(publicada=True, categoria__activa=True,
                                                            categoria__edicion__activa=True)
                         .exclude(modo=Votacion.Modo.JURADO).select_related("categoria")
                         if v.esta_abierta and v.opciones_activas().exists()), None)
        if votacion is None:
            raise CommandError("No hay votaciones abiertas. Corra primero: py manage.py cargar_demo --reiniciar")
        opciones = list(votacion.opciones_activas())
        opciones = [opciones[i % len(opciones)] for i in range(max(2, hilos))]

        Voto.objects.filter(usuario__email=CORREO).delete()
        Usuario.objects.filter(email=CORREO).delete()
        usuario = Usuario.objects.create_user(username=CORREO, email=CORREO, password=None,
                                              first_name="Prueba", last_name="Concurrencia")

        self.stdout.write(f"Motor de base de datos: {connection.vendor} ({connection.settings_dict['NAME']})")
        self.stdout.write(f"Categoría: {votacion.categoria.nombre} · votación: {votacion.nombre}")
        self.stdout.write(f"Enviando {len(opciones)} votos AL MISMO TIEMPO con el usuario {CORREO}...\n")
        for i, (estado, detalle) in enumerate(votar_en_paralelo(usuario, opciones), start=1):
            self.stdout.write(f"  Solicitud {i} ({opciones[i - 1].nombre}): {estado.upper()} · {detalle}")

        guardados = Voto.objects.filter(usuario=usuario, categoria=votacion.categoria).count()
        repetidos = (Voto.objects.values("usuario", "categoria", "edicion").annotate(n=Count("id")).filter(n__gt=1).count())
        self.stdout.write("")
        self.stdout.write(f"Votos guardados en la base para ese usuario y categoría: {guardados}")
        self.stdout.write(f"Combinaciones usuario-categoría-edición repetidas en toda la tabla: {repetidos}")
        if guardados == 1 and repetidos == 0:
            self.stdout.write(self.style.SUCCESS("CP-09 APROBADO: solo quedó un voto válido."))
        else:
            self.stdout.write(self.style.ERROR("CP-09 FALLIDO: revise la restricción única."))

        if not conservar:
            Voto.objects.filter(usuario=usuario).delete()
            Registro.objects.filter(usuario=usuario).delete()
            usuario.delete()
            self.stdout.write("Usuario temporal y sus votos eliminados.")
