"""Pruebas de las reglas de negocio del voto. Ejecutar:  python manage.py test"""
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Usuario
from votaciones.models import Categoria, Edicion, Opcion, Votacion, Voto
from votaciones.servicios import VotoRechazado, emitir_voto


class Base(TestCase):
    def setUp(self):
        self.ahora = timezone.now()
        self.ed = Edicion.objects.create(anio=2027, nombre="Festival 2027", activa=True)
        self.cat = Categoria.objects.create(edicion=self.ed, nombre="Música")
        self.v = self.crear_votacion()
        self.a = Opcion.objects.create(votacion=self.v, nombre="Canción A", orden=1)
        self.b = Opcion.objects.create(votacion=self.v, nombre="Canción B", orden=2)
        self.ana = Usuario.objects.create_user(username="ana@x.co", email="ana@x.co", password="Clave-Segura-2027")
        self.admin = Usuario.objects.create_user(username="adm@x.co", email="adm@x.co", password="Clave-Segura-2027", rol="admin")

    def crear_votacion(self, **kw):
        datos = dict(categoria=self.cat, nombre="Canción favorita", apertura=self.ahora - timedelta(days=1),
                     cierre=self.ahora + timedelta(days=1), publicada=True)
        datos.update(kw)
        return Votacion.objects.create(**datos)


class ReglasDelVoto(Base):
    def test_voto_valido_genera_comprobante(self):
        voto = emitir_voto(self.ana, self.a.pk)
        self.assertTrue(voto.codigo.startswith("VLL-"))
        self.assertEqual(Voto.objects.count(), 1)

    def test_un_voto_por_votacion(self):  # RN-06 (valor propuesto)
        emitir_voto(self.ana, self.a.pk)
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.ana, self.b.pk)
        self.assertEqual(e.exception.motivo, "limite")
        self.assertEqual(Voto.objects.count(), 1)

    def test_frecuencia_diaria(self):  # RN-06 alternativa configurable
        self.v.frecuencia = Votacion.Frecuencia.DIARIA
        self.v.save()
        emitir_voto(self.ana, self.a.pk)
        with self.assertRaises(VotoRechazado):
            emitir_voto(self.ana, self.a.pk)
        manana = timezone.now() + timedelta(hours=25)
        self.v.cierre = manana + timedelta(days=1)
        self.v.save()
        with mock.patch("django.utils.timezone.now", return_value=manana):
            emitir_voto(self.ana, self.a.pk)
        self.assertEqual(Voto.objects.count(), 2)

    def test_votacion_cerrada(self):  # RN-02
        v = self.crear_votacion(nombre="Vieja", apertura=self.ahora - timedelta(days=3), cierre=self.ahora - timedelta(days=1))
        o = Opcion.objects.create(votacion=v, nombre="X")
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.ana, o.pk)
        self.assertEqual(e.exception.motivo, "cerrada")

    def test_votacion_proxima_y_borrador(self):  # RN-02
        v = self.crear_votacion(nombre="Futura", apertura=self.ahora + timedelta(days=1), cierre=self.ahora + timedelta(days=2))
        o = Opcion.objects.create(votacion=v, nombre="X")
        with self.assertRaises(VotoRechazado):
            emitir_voto(self.ana, o.pk)
        self.v.publicada = False
        self.v.save()
        with self.assertRaises(VotoRechazado):
            emitir_voto(self.ana, self.a.pk)

    def test_cierre_manual(self):
        self.v.cerrada_manualmente = timezone.now()
        self.v.save()
        with self.assertRaises(VotoRechazado):
            emitir_voto(self.ana, self.a.pk)

    def test_opcion_inactiva(self):
        self.a.activa = False
        self.a.save()
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.ana, self.a.pk)
        self.assertEqual(e.exception.motivo, "opcion_inactiva")

    def test_la_base_de_datos_impide_duplicados(self):  # RNF-02: no depende solo de la interfaz
        Voto.objects.create(usuario=self.ana, votacion=self.v, opcion=self.a, clave_frecuencia="unica")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Voto.objects.create(usuario=self.ana, votacion=self.v, opcion=self.b, clave_frecuencia="unica")

    def test_publicar_requiere_dos_opciones(self):  # RN-07
        v = self.crear_votacion(nombre="Nueva", publicada=False)
        Opcion.objects.create(votacion=v, nombre="Sola")
        self.assertFalse(v.puede_publicarse())
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:votacion_publicar", args=[v.pk]))
        v.refresh_from_db()
        self.assertFalse(v.publicada)

    def test_estados_calculados(self):
        self.assertEqual(self.v.estado, "abierta")
        self.assertEqual(self.crear_votacion(nombre="B", publicada=False).estado, "borrador")


class FlujoWeb(Base):
    def test_flujo_completo_de_voto(self):  # CU-04
        r = self.client.get(reverse("votaciones:opciones", args=[self.v.pk]))
        self.assertContains(r, "Canción A")
        url = reverse("votaciones:confirmar", args=[self.v.pk])
        r = self.client.get(url, {"opcion": self.a.pk})
        self.assertEqual(r.status_code, 302)  # pide iniciar sesión (RN-04)
        self.client.force_login(self.ana)
        r = self.client.get(url, {"opcion": self.a.pk})
        self.assertContains(r, "¿Confirmas tu voto?")
        r = self.client.post(url, {"opcion": self.a.pk, "confirmado": "1"})
        voto = Voto.objects.get()
        self.assertRedirects(r, reverse("votaciones:comprobante", args=[voto.codigo]))
        r = self.client.post(url, {"opcion": self.b.pk, "confirmado": "1"})
        self.assertEqual(r.status_code, 409)
        self.assertContains(r, "Ya votaste", status_code=409)

    def test_registro(self):  # CU-01
        r = self.client.post(reverse("cuentas:registro"), {
            "first_name": "Luis", "last_name": "Díaz", "email": "luis@x.co",
            "password1": "Acordeon-2027", "password2": "Acordeon-2027", "acepto": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Usuario.objects.filter(email="luis@x.co", acepto_tratamiento_datos=True).exists())

    def test_registro_sin_autorizar_datos(self):
        r = self.client.post(reverse("cuentas:registro"), {
            "first_name": "Luis", "email": "luis@x.co", "password1": "Acordeon-2027", "password2": "Acordeon-2027"})
        self.assertContains(r, "Debes autorizar")

    def test_login_con_correo(self):  # CU-02
        r = self.client.post(reverse("cuentas:login"), {"username": "ana@x.co", "password": "Clave-Segura-2027"})
        self.assertEqual(r.status_code, 302)

    def test_panel_solo_admin(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse("panel:panel")).status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("panel:panel")).status_code, 200)

    def test_pantallas_del_panel(self):
        self.client.force_login(self.admin)
        for nombre, args in [("panel:categorias", []), ("panel:votaciones", []), ("panel:votacion_nueva", []),
                             ("panel:opciones", [self.v.pk]), ("panel:resultados", []), ("panel:auditoria", [])]:
            self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 200, nombre)

    def test_opcion_con_votos_no_se_elimina(self):  # RN-08
        emitir_voto(self.ana, self.a.pk)
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:opcion_eliminar", args=[self.a.pk]))
        self.assertTrue(Opcion.objects.filter(pk=self.a.pk).exists())
        self.client.post(reverse("panel:opcion_estado", args=[self.a.pk]), {"justificacion": "Participante retirado"})
        self.a.refresh_from_db()
        self.assertFalse(self.a.activa)

    def test_exportar_csv(self):
        emitir_voto(self.ana, self.a.pk)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("panel:resultados_csv", args=[self.v.pk]))
        self.assertIn("Canción A;1", r.content.decode("utf-8"))

    def test_paginas_publicas(self):
        for url in [reverse("votaciones:inicio"), reverse("votaciones:categorias"),
                    reverse("votaciones:categoria", args=[self.cat.pk]), reverse("votaciones:detalle", args=[self.v.pk])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
