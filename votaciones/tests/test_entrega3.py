"""Pruebas funcionales de la Entrega 3 (CP-01 a CP-10).

Regla central: cada usuario elige una sola opción por categoría y edición. Puede votar en
otras categorías, pero no dos veces en la misma, aunque la categoría tenga varias votaciones.

Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_entrega3
"""
import json
import unittest
from datetime import timedelta
from unittest import mock

from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Usuario
from votaciones.concurrencia import votar_en_paralelo
from votaciones.models import Categoria, Edicion, Opcion, Votacion, Voto
from votaciones.servicios import VotoRechazado, emitir_voto

CLAVE = "Clave-Segura-2027"


def crear_escenario(test):
    """Edición 2027 con Música (dos votaciones = subeventos) y Rey Vallenato; ambas abiertas."""
    test.ahora = timezone.now()
    test.ed = Edicion.objects.create(anio=2027, numero=60, nombre="Festival 2027", activa=True)
    test.musica = Categoria.objects.create(edicion=test.ed, nombre="Música", orden=1)
    test.rey = Categoria.objects.create(edicion=test.ed, nombre="Rey Vallenato", orden=2)

    def votacion(cat, nombre, **kw):
        datos = dict(categoria=cat, nombre=nombre, apertura=test.ahora - timedelta(days=1),
                     cierre=test.ahora + timedelta(days=2), publicada=True, modo=Votacion.Modo.PUBLICO)
        datos.update(kw)
        return Votacion.objects.create(**datos)

    test.votacion = votacion
    test.cancion = votacion(test.musica, "Mejor canción inédita")
    test.aire = votacion(test.musica, "Tu aire favorito")            # segundo subevento de Música
    test.rey_v = votacion(test.rey, "Tu Rey Vallenato favorito")
    test.c1 = Opcion.objects.create(votacion=test.cancion, nombre="Brisa del Guatapurí", orden=1)
    test.c2 = Opcion.objects.create(votacion=test.cancion, nombre="Pilón de mi tierra", orden=2)
    test.a1 = Opcion.objects.create(votacion=test.aire, nombre="Paseo", orden=1)
    test.r1 = Opcion.objects.create(votacion=test.rey_v, nombre="Acordeonero #05", orden=1)
    test.r2 = Opcion.objects.create(votacion=test.rey_v, nombre="Acordeonero #12", orden=2)
    test.votante = Usuario.objects.create_user(username="votante@x.co", email="votante@x.co", password=CLAVE, first_name="Ana")
    test.admin = Usuario.objects.create_user(username="admin@x.co", email="admin@x.co", password=CLAVE,
                                             rol="admin", is_staff=True, is_superuser=True)


class Base(TestCase):
    def setUp(self):
        crear_escenario(self)

    def votar_web(self, votacion, opcion, cliente=None):
        """Recorre el flujo real: envía el formulario de confirmación (POST) con la opción."""
        c = cliente or self.client
        url = reverse("votaciones:confirmar", args=[votacion.pk])
        return c.post(url, {"opcion": opcion.pk, "confirmado": "on"})


class CP01_VotoValido(Base):
    def test_usuario_autenticado_registra_voto(self):
        self.client.force_login(self.votante)
        r = self.client.get(reverse("votaciones:confirmar", args=[self.cancion.pk]), {"opcion": self.c1.pk})
        self.assertContains(r, "Brisa del Guatapurí")                     # pantalla de confirmación
        self.assertContains(r, "csrfmiddlewaretoken")
        r = self.votar_web(self.cancion, self.c1)
        voto = Voto.objects.get()
        self.assertRedirects(r, reverse("votaciones:comprobante", args=[voto.codigo]))
        self.assertEqual((voto.usuario, voto.opcion, voto.categoria, voto.edicion),
                         (self.votante, self.c1, self.musica, self.ed))

    def test_sin_confirmar_no_se_registra(self):
        self.client.force_login(self.votante)
        url = reverse("votaciones:confirmar", args=[self.cancion.pk])
        r = self.client.post(url, {"opcion": self.c1.pk})
        self.assertContains(r, "Debes confirmar tu voto")
        self.assertEqual(Voto.objects.count(), 0)


class CP02_SegundoVotoMismaCategoria(Base):
    def test_otra_opcion_misma_votacion(self):
        self.client.force_login(self.votante)
        self.votar_web(self.cancion, self.c1)
        r = self.votar_web(self.cancion, self.c2)
        self.assertEqual(r.status_code, 409)
        self.assertContains(r, "Ya votaste en la categoría Música", status_code=409)
        self.assertEqual(Voto.objects.count(), 1)

    def test_otro_subevento_misma_categoria(self):
        self.client.force_login(self.votante)
        self.votar_web(self.cancion, self.c1)
        r = self.votar_web(self.aire, self.a1)                           # otra votación de Música
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Voto.objects.filter(usuario=self.votante, categoria=self.musica).count(), 1)

    def test_aviso_antes_de_votar(self):
        self.client.force_login(self.votante)
        self.votar_web(self.cancion, self.c1)
        r = self.client.get(reverse("votaciones:opciones", args=[self.aire.pk]))
        self.assertContains(r, "Ya votaste en la categoría Música")


class CP03_VotoEnOtraCategoria(Base):
    def test_se_permite_votar_en_otra_categoria(self):
        self.client.force_login(self.votante)
        self.votar_web(self.cancion, self.c1)
        r = self.votar_web(self.rey_v, self.r1)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Voto.objects.filter(usuario=self.votante).count(), 2)


class CP04_SinAutenticacion(Base):
    def test_anonimo_es_enviado_a_iniciar_sesion(self):
        r = self.votar_web(self.cancion, self.c1)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("cuentas:login")))
        self.assertEqual(Voto.objects.count(), 0)

    def test_servicio_rechaza_anonimo(self):
        from django.contrib.auth.models import AnonymousUser
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(AnonymousUser(), self.c1.pk)
        self.assertEqual(e.exception.motivo, "sin_sesion")

    def test_post_sin_csrf_es_rechazado(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.votante)
        r = self.votar_web(self.cancion, self.c1, cliente=c)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Voto.objects.count(), 0)


class CP05_CategoriaNoHabilitada(Base):
    def test_votacion_que_aun_no_abre(self):
        v = self.votacion(self.rey, "Próxima", apertura=self.ahora + timedelta(days=1), cierre=self.ahora + timedelta(days=3))
        o = Opcion.objects.create(votacion=v, nombre="X")
        self.client.force_login(self.votante)
        r = self.votar_web(v, o)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Voto.objects.count(), 0)

    def test_votacion_cerrada(self):
        v = self.votacion(self.rey, "Cerrada", apertura=self.ahora - timedelta(days=3), cierre=self.ahora - timedelta(days=1))
        o = Opcion.objects.create(votacion=v, nombre="X")
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.votante, o.pk)
        self.assertEqual(e.exception.motivo, "cerrada")

    def test_categoria_inactiva(self):
        self.rey.activa = False
        self.rey.save()
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.votante, self.r1.pk)
        self.assertEqual(e.exception.motivo, "no_habilitada")
        self.client.force_login(self.votante)
        self.assertEqual(self.votar_web(self.rey_v, self.r1).status_code, 404)
        self.assertEqual(Voto.objects.count(), 0)

    def test_edicion_inactiva(self):
        self.ed.activa = False
        self.ed.save()
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.votante, self.c1.pk)
        self.assertEqual(e.exception.motivo, "no_habilitada")


class CP06_OpcionDeOtraCategoria(Base):
    def test_formulario_manipulado(self):
        self.client.force_login(self.votante)
        r = self.votar_web(self.cancion, self.r1)                        # opción de Rey Vallenato en Música
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "no pertenece a esta votación", status_code=400)
        self.assertEqual(Voto.objects.count(), 0)

    def test_servicio_valida_la_votacion(self):
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.votante, self.r1.pk, votacion=self.cancion)
        self.assertEqual(e.exception.motivo, "opcion_invalida")

    def test_opcion_inexistente(self):
        self.client.force_login(self.votante)
        r = self.client.post(reverse("votaciones:confirmar", args=[self.cancion.pk]), {"opcion": "999999", "confirmado": "on"})
        self.assertEqual(r.status_code, 400)


class CP07_CategoriasVotadas(Base):
    def test_mis_votos_muestra_votadas_y_pendientes(self):
        self.client.force_login(self.votante)
        self.votar_web(self.cancion, self.c1)
        r = self.client.get(reverse("cuentas:mis_votos"))
        self.assertContains(r, "Votaste en 1 de 2")
        self.assertContains(r, "Brisa del Guatapurí")
        self.assertContains(r, Voto.objects.get().codigo)
        self.assertContains(r, "Pendiente")                              # Rey Vallenato


class CP08_ConsultaAdministrativa(Base):
    def test_panel_muestra_los_votos_de_mysql(self):
        emitir_voto(self.votante, self.c1.pk)
        emitir_voto(self.votante, self.r1.pk)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("panel:votos"))
        for v in Voto.objects.all():
            self.assertContains(r, v.codigo)
        self.assertContains(r, "2 votos")
        r = self.client.get(reverse("panel:votos"), {"categoria": self.musica.pk})
        self.assertContains(r, Voto.objects.get(categoria=self.musica).codigo)
        self.assertNotContains(r, Voto.objects.get(categoria=self.rey).codigo)

    def test_votante_no_entra_al_panel_de_votos(self):
        self.client.force_login(self.votante)
        r = self.client.get(reverse("panel:votos"))
        self.assertEqual(r.status_code, 302)


class CP09_SolicitudesSimultaneas(Base):
    def test_restriccion_unica_respalda_la_regla(self):
        """Simula la carrera: la verificación previa no ve el voto del otro hilo y la base de datos lo frena."""
        emitir_voto(self.votante, self.c1.pk)
        with mock.patch("votaciones.servicios.voto_en_categoria", side_effect=[None, Voto.objects.get()]):
            with self.assertRaises(VotoRechazado) as e:
                emitir_voto(self.votante, self.a1.pk)
        self.assertEqual(e.exception.motivo, "limite")
        self.assertEqual(Voto.objects.filter(usuario=self.votante, categoria=self.musica).count(), 1)


@unittest.skipUnless(connection.vendor == "mysql", "Hilos simultáneos reales solo en MySQL (SQLite bloquea la base completa).")
class CP09_HilosRealesEnMySQL(TransactionTestCase):
    """Dos y cinco solicitudes al mismo tiempo, cada una con su propia conexión a MySQL."""

    def setUp(self):
        crear_escenario(self)

    def test_dos_solicitudes_simultaneas(self):
        resultados = votar_en_paralelo(self.votante, [self.c1, self.c2])
        self.assertEqual(sorted(r[0] for r in resultados), ["aceptado", "rechazado"], resultados)
        self.assertEqual(Voto.objects.filter(usuario=self.votante, categoria=self.musica).count(), 1)

    def test_cinco_solicitudes_en_dos_subeventos(self):
        resultados = votar_en_paralelo(self.votante, [self.c1, self.c2, self.a1, self.c1, self.a1])
        self.assertEqual([r[0] for r in resultados].count("aceptado"), 1, resultados)
        self.assertEqual(Voto.objects.filter(usuario=self.votante, categoria=self.musica).count(), 1)


class CP10_ApiCategorias(Base):
    def test_json_valido_con_categorias_y_opciones(self):
        Opcion.objects.create(votacion=self.rey_v, nombre="Inactiva", activa=False)
        r = self.client.get("/api/categorias/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")
        datos = json.loads(r.content)
        self.assertEqual(datos["edicion"]["anio"], 2027)
        nombres = [c["nombre"] for c in datos["categorias"]]
        self.assertEqual(nombres, ["Música", "Rey Vallenato"])
        rey = datos["categorias"][1]
        opciones = [o["nombre"] for o in rey["votaciones"][0]["opciones"]]
        self.assertEqual(opciones, ["Acordeonero #05", "Acordeonero #12"])  # sin la inactiva

    def test_refleja_cambios_de_la_base(self):
        Opcion.objects.create(votacion=self.cancion, nombre="Canción nueva", orden=3)
        datos = self.client.get(reverse("votaciones:api_categorias")).json()
        self.assertIn("Canción nueva", json.dumps(datos, ensure_ascii=False))

    def test_otra_edicion_y_errores(self):
        e26 = Edicion.objects.create(anio=2026, nombre="Festival 2026")
        Categoria.objects.create(edicion=e26, nombre="Música 2026")
        datos = self.client.get("/api/categorias/", {"anio": 2026}).json()
        self.assertEqual([c["nombre"] for c in datos["categorias"]], ["Música 2026"])
        self.assertEqual(self.client.get("/api/categorias/", {"anio": 1990}).status_code, 404)
        self.assertEqual(self.client.get("/api/categorias/", {"anio": "abc"}).status_code, 400)

    def test_solo_get(self):
        self.assertEqual(self.client.post("/api/categorias/").status_code, 405)


class GestionDesdeElPanel(Base):
    """Todo se administra desde las pantallas de la app, sin Django Admin."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_eliminar_categoria_sin_votaciones(self):
        vacia = Categoria.objects.create(edicion=self.ed, nombre="Piqueria")
        self.client.post(reverse("panel:categoria_eliminar", args=[vacia.pk]))
        self.assertFalse(Categoria.objects.filter(pk=vacia.pk).exists())

    def test_no_elimina_categoria_con_votaciones(self):
        r = self.client.post(reverse("panel:categoria_eliminar", args=[self.rey.pk]), follow=True)
        self.assertTrue(Categoria.objects.filter(pk=self.rey.pk).exists())
        self.assertContains(r, "tiene votaciones")

    def test_eliminar_votacion_sin_votos_y_no_con_votos(self):
        self.client.post(reverse("panel:votacion_eliminar", args=[self.aire.pk]))
        self.assertFalse(Votacion.objects.filter(pk=self.aire.pk).exists())
        self.assertFalse(Opcion.objects.filter(pk=self.a1.pk).exists())
        emitir_voto(self.votante, self.c1.pk)
        self.client.post(reverse("panel:votacion_eliminar", args=[self.cancion.pk]))
        self.assertTrue(Votacion.objects.filter(pk=self.cancion.pk).exists())

    def test_eliminar_edicion_solo_si_esta_vacia_y_no_activa(self):
        e28 = Edicion.objects.create(anio=2028, nombre="Festival 2028")
        self.client.post(reverse("panel:edicion_eliminar", args=[self.ed.pk]))
        self.assertTrue(Edicion.objects.filter(pk=self.ed.pk).exists())       # activa
        self.client.post(reverse("panel:edicion_eliminar", args=[e28.pk]))
        self.assertFalse(Edicion.objects.filter(pk=e28.pk).exists())

    def test_eliminar_exige_post(self):
        self.assertEqual(self.client.get(reverse("panel:categoria_eliminar", args=[self.rey.pk])).status_code, 405)

    def test_votante_no_puede_eliminar(self):
        self.client.force_login(self.votante)
        self.client.post(reverse("panel:votacion_eliminar", args=[self.aire.pk]))
        self.assertTrue(Votacion.objects.filter(pk=self.aire.pk).exists())
