"""Pruebas del jurado y del resultado ponderado (CU-09, CU-10, RF-15, RF-16, RN-11 a RN-15)."""
from django.db import IntegrityError, transaction
from django.urls import reverse

from cuentas.models import Usuario
from votaciones.models import Calificacion, Votacion
from votaciones.servicios import CalificacionRechazada, VotoRechazado, calificar, emitir_voto

from .test_reglas import Base


class JuradoBase(Base):
    def setUp(self):
        super().setUp()
        self.j1 = Usuario.objects.create_user(username="j1@x.co", email="j1@x.co", password="Clave-Segura-2027", rol="jurado")
        self.j2 = Usuario.objects.create_user(username="j2@x.co", email="j2@x.co", password="Clave-Segura-2027", rol="jurado")
        self.v.jurados.set([self.j1, self.j2])
        # Estas pruebas usan el modo combinado con la propuesta 70/30 (pendiente de validación, P-06)
        self.v.modo, self.v.peso_jurado = Votacion.Modo.COMBINADO, 70
        self.v.save()


class ReglasDelJurado(JuradoBase):
    def test_jurado_califica_todas_las_opciones(self):  # RF-15
        calificar(self.j1, self.v, {self.a.pk: 8, self.b.pk: 6})
        self.assertEqual(Calificacion.objects.filter(jurado=self.j1).count(), 2)

    def test_no_califica_dos_veces(self):  # RN-14
        calificar(self.j1, self.v, {self.a.pk: 8, self.b.pk: 6})
        with self.assertRaises(CalificacionRechazada) as e:
            calificar(self.j1, self.v, {self.a.pk: 1, self.b.pk: 1})
        self.assertEqual(e.exception.motivo, "ya_califico")

    def test_la_base_de_datos_impide_doble_calificacion(self):  # RN-14 en la base de datos
        Calificacion.objects.create(jurado=self.j1, votacion=self.v, opcion=self.a, puntaje=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Calificacion.objects.create(jurado=self.j1, votacion=self.v, opcion=self.a, puntaje=9)

    def test_jurado_no_asignado(self):  # RN-13
        otro = Usuario.objects.create_user(username="j3@x.co", email="j3@x.co", password="x" * 12, rol="jurado")
        with self.assertRaises(CalificacionRechazada) as e:
            calificar(otro, self.v, {self.a.pk: 8, self.b.pk: 6})
        self.assertEqual(e.exception.motivo, "no_asignado")

    def test_votante_no_califica(self):
        with self.assertRaises(CalificacionRechazada):
            calificar(self.ana, self.v, {self.a.pk: 8, self.b.pk: 6})

    def test_puntaje_fuera_de_escala_o_incompleto(self):
        with self.assertRaises(CalificacionRechazada) as e:
            calificar(self.j1, self.v, {self.a.pk: 11, self.b.pk: 6})
        self.assertEqual(e.exception.motivo, "fuera_de_escala")
        with self.assertRaises(CalificacionRechazada) as e:
            calificar(self.j1, self.v, {self.a.pk: 8})
        self.assertEqual(e.exception.motivo, "incompleta")
        self.assertFalse(Calificacion.objects.exists())  # todo o nada

    def test_jurado_no_vota_como_publico(self):  # RN-15
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.j1, self.a.pk)
        self.assertEqual(e.exception.motivo, "conflicto_jurado")

    def test_solo_jurado_no_recibe_votos_del_publico(self):  # RN-11
        self.v.modo = Votacion.Modo.JURADO
        self.v.save()
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.ana, self.a.pk)
        self.assertEqual(e.exception.motivo, "solo_jurado")

    def test_resultado_ponderado_70_30(self):  # RN-11
        # Público: A 3 votos, B 1 voto -> A 75 %, B 25 %
        for i in range(3):
            u = Usuario.objects.create_user(username=f"p{i}@x.co", email=f"p{i}@x.co", password="x" * 12)
            emitir_voto(u, self.a.pk)
        emitir_voto(self.ana, self.b.pk)
        # Jurado: A 4 + 6 = 10, B 8 + 10 = 18 -> A 35.7 %, B 64.3 %
        calificar(self.j1, self.v, {self.a.pk: 4, self.b.pk: 8})
        calificar(self.j2, self.v, {self.a.pk: 6, self.b.pk: 10})
        filas, total = self.v.resultados_ponderados()
        r = {o.pk: o for o in filas}
        self.assertEqual(total, 4)
        self.assertAlmostEqual(r[self.a.pk].pct_publico, 75)
        self.assertAlmostEqual(r[self.a.pk].pct_jurado, 10 * 100 / 28)
        esperado_b = 0.7 * (18 * 100 / 28) + 0.3 * 25
        self.assertAlmostEqual(r[self.b.pk].final, esperado_b)
        self.assertEqual(filas[0].pk, self.b.pk)  # el jurado le da la vuelta al público
        self.assertAlmostEqual(sum(o.final for o in filas), 100)

    def test_peso_fuera_de_1_a_99_rechazado_por_la_base_de_datos(self):
        for malo in (0, 100, 120):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Votacion.objects.filter(pk=self.v.pk).update(peso_jurado=malo)

    def test_publicar_con_jurado_exige_jurados(self):  # RN-13
        v = self.crear_votacion(nombre="Sin jurados", publicada=False)
        v.opciones.create(nombre="X")
        v.opciones.create(nombre="Y")
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:votacion_publicar", args=[v.pk]))
        v.refresh_from_db()
        self.assertFalse(v.publicada)


class PantallasDelJurado(JuradoBase):
    def test_login_lleva_al_panel_del_jurado(self):
        r = self.client.post(reverse("cuentas:login"), {"username": "j1@x.co", "password": "Clave-Segura-2027"})
        self.assertRedirects(r, "/jurado/", fetch_redirect_response=False)

    def test_flujo_de_calificacion_web(self):  # CU-09
        self.client.force_login(self.j1)
        self.assertContains(self.client.get(reverse("jurado:inicio")), self.v.nombre)
        url = reverse("jurado:calificar", args=[self.v.pk])
        self.assertContains(self.client.get(url), "Enviar calificación")
        r = self.client.post(url, {f"puntaje_{self.a.pk}": "9", f"puntaje_{self.b.pk}": "7"})
        self.assertRedirects(r, reverse("jurado:inicio"))
        self.assertEqual(Calificacion.objects.filter(jurado=self.j1).count(), 2)
        self.assertNotContains(self.client.get(url), "Enviar calificación")

    def test_solo_jurados_entran(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse("jurado:inicio")).status_code, 302)

    def test_admin_crea_jurado_y_ve_resultados(self):  # CU-10
        self.client.force_login(self.admin)
        r = self.client.post(reverse("panel:jurados"), {"first_name": "Rosa", "last_name": "Ochoa",
                                                         "email": "rosa@x.co", "password": "Clave-Segura-2027"})
        self.assertRedirects(r, reverse("panel:jurados"))
        self.assertTrue(Usuario.objects.filter(email="rosa@x.co", rol="jurado").exists())
        self.assertContains(self.client.get(reverse("panel:resultados_votacion", args=[self.v.pk])), "Cómo se calcula")
