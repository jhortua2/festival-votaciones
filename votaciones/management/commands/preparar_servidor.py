"""Prepara la base de datos del servidor público (Vercel lo corre al construir).

Uso:  python manage.py preparar_servidor

1. Aplica las migraciones pendientes y crea la tabla de caché si se usa (DJANGO_CACHE_DB=1).
2. Carga los datos de prueba si todavía no existen, pero solo si se definieron claves propias en
   DEMO_CLAVE_ADMIN, DEMO_CLAVE_VOTANTE y DEMO_CLAVE_JURADO. En un servidor público nunca se crean
   usuarios con las claves del README, que son públicas.
"""
import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

CLAVES = ("DEMO_CLAVE_ADMIN", "DEMO_CLAVE_VOTANTE", "DEMO_CLAVE_JURADO")


class Command(BaseCommand):
    help = "Migraciones y datos de prueba (con claves propias) para el servidor público."

    def handle(self, *args, **opts):
        call_command("migrate", interactive=False, verbosity=1)
        call_command("createcachetable", verbosity=0)   # solo crea algo si la caché está en la base (DJANGO_CACHE_DB=1)
        if not settings.DEBUG and not all(os.environ.get(c) for c in CLAVES):
            self.stdout.write(self.style.WARNING(
                "No se cargaron datos de prueba: defina DEMO_CLAVE_ADMIN, DEMO_CLAVE_VOTANTE y DEMO_CLAVE_JURADO "
                "con claves propias (las del README son públicas)."))
            return
        call_command("cargar_demo", stdout=self.stdout)
