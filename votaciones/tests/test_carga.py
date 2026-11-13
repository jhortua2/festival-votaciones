"""Prueba de carga con varios votantes simultáneos (Eje 4).

Corre una versión pequeña del comando `prueba_carga` (40 votantes, 2 votos casi a la vez cada
uno, 10 en paralelo) y comprueba que cada votante queda con un solo voto y que no hay
duplicados. Solo en MySQL: SQLite no admite escrituras simultáneas.

La prueba grande se corre a mano:  py manage.py prueba_carga --usuarios 1000 --hilos 50
"""
import unittest
from io import StringIO

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase

from cuentas.models import Usuario
from votaciones.models import Voto

from .test_entrega3 import crear_escenario


@unittest.skipUnless(connection.vendor == "mysql", "Escrituras simultáneas reales solo en MySQL.")
class PruebaDeCargaEnMySQL(TransactionTestCase):
    def setUp(self):
        crear_escenario(self)

    def test_cuarenta_votantes_simultaneos(self):
        salida = StringIO()
        call_command("prueba_carga", usuarios=40, hilos=10, stdout=salida)
        texto = salida.getvalue()
        self.assertIn("PRUEBA DE CARGA APROBADA", texto, texto)
        self.assertIn("Solicitudes aceptadas:  40", texto)
        self.assertIn("Combinaciones repetidas en toda la tabla: 0", texto)
        # Deja la base limpia
        self.assertFalse(Usuario.objects.filter(email__startswith="carga-").exists())
        self.assertFalse(Voto.objects.filter(usuario__email__startswith="carga-").exists())


@unittest.skipUnless(connection.vendor == "sqlite", "Solo aplica con SQLite.")
class PruebaDeCargaExigeMySQL(TestCase):
    def test_avisa_que_necesita_mysql(self):
        with self.assertRaises(CommandError):
            call_command("prueba_carga", usuarios=5, hilos=2, stdout=StringIO())
