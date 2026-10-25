"""Pruebas de los cambios de la Entrega 2 y de las observaciones de la Entrega 1.

- Modo de resultado configurable: independiente o combinado (RN-11, pendiente de validación P-06).
- Origen de las reglas: enunciado del cliente vs. propuesta del equipo.
- Ediciones: registrar y consultar varias ediciones anuales.
"""
from datetime import timedelta

from django.urls import reverse

from cuentas.models import Usuario
from votaciones.models import Categoria, Edicion, Votacion
from votaciones.reglas import ENUNCIADO, PROPUESTA, origen
from votaciones.servicios import calificar, emitir_voto
from votaciones.templatetags.festival import regla

from .test_jurado import JuradoBase


class ModoDeResultado(JuradoBase):
    def _votos_y_puntajes(self):
        # Público: A 3 votos, B 1 voto. Jurado: A 10 puntos, B 18 puntos.
        for i in range(3):
            u = Usuario.objects.create_user(username=f"p{i}@x.co", email=f"p{i}@x.co", password="x" * 12)
            emitir_voto(u, self.a.pk)
        emitir_voto(self.ana, self.b.pk)
        calificar(self.j1, self.v, {self.a.pk: 4, self.b.pk: 8})
        calificar(self.j2, self.v, {self.a.pk: 6, self.b.pk: 10})

    def test_modo_por_defecto_es_independiente(self):
        v = self.crear_votacion(nombre="Nueva")
        self.assertEqual(v.modo, Votacion.Modo.INDEPENDIENTE)

    def test_independiente_no_mezcla_jurado_y_publico(self):
        self.v.modo = Votacion.Modo.INDEPENDIENTE
        self.v.save()
        self._votos_y_puntajes()
        filas, _ = self.v.resultados_ponderados()
        self.assertTrue(all(o.final is None for o in filas))
        self.assertEqual(filas[0].pk, self.b.pk)  # fallo del jurado: gana B
        self.assertEqual(self.v.ranking_publico(filas)[0].pk, self.a.pk)  # público: gana A

    def test_combinado_aplica_el_peso(self):
        self._votos_y_puntajes()
        filas, _ = self.v.resultados_ponderados()
        self.assertAlmostEqual(sum(o.final for o in filas), 100)

    def test_detalle_marca_el_70_30_como_propuesta(self):
        r = self.client.get(reverse("votaciones:detalle", args=[self.v.pk]))
        self.assertContains(r, "Propuesta, no decisión oficial")
        self.assertContains(r, "origen-propuesta")

    def test_detalle_independiente_explica_que_va_aparte(self):
        self.v.modo = Votacion.Modo.INDEPENDIENTE
        self.v.save()
        r = self.client.get(reverse("votaciones:detalle", args=[self.v.pk]))
        self.assertContains(r, "no cambia el fallo del jurado")

    def test_resultados_independiente_muestra_dos_rankings(self):
        self.v.modo = Votacion.Modo.INDEPENDIENTE
        self.v.save()
        self._votos_y_puntajes()
        self.client.force_login(self.admin)
        r = self.client.get(reverse("panel:resultados_votacion", args=[self.v.pk]))
        self.assertContains(r, "Fallo del jurado")
        self.assertContains(r, "Reconocimiento del público")


class OrigenDeLasReglas(JuradoBase):
    def test_regla_del_enunciado(self):
        self.assertEqual(origen("RN-01"), ENUNCIADO)
        self.assertIn("Enunciado · RN-01", regla("RN-01"))

    def test_propuestas_y_preguntas(self):
        self.assertEqual(origen("RN-11"), PROPUESTA)
        self.assertEqual(origen("P-06"), PROPUESTA)
        self.assertIn("Propuesta · RN-11 · P-06", regla("RN-11", "P-06"))


class Ediciones(JuradoBase):
    def test_pagina_publica_lista_varias_ediciones(self):
        e26 = Edicion.objects.create(anio=2026, numero=59, nombre="Festival 2026")
        Categoria.objects.create(edicion=e26, nombre="Música 2026")
        r = self.client.get(reverse("votaciones:ediciones"))
        self.assertContains(r, "Festival 2026")
        self.assertContains(r, "Festival 2027")
        self.assertContains(r, "Música 2026")

    def test_panel_crea_y_activa_ediciones(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:ediciones"), {"anio": 2028, "numero": 61, "nombre": "Festival 2028"})
        e28 = Edicion.objects.get(anio=2028)
        self.assertFalse(e28.activa)
        self.client.post(reverse("panel:edicion_activar", args=[e28.pk]))
        self.assertEqual(list(Edicion.objects.filter(activa=True)), [e28])  # solo una activa

    def test_anio_repetido_rechazado(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("panel:ediciones"), {"anio": 2027, "nombre": "Repetida"})
        self.assertEqual(Edicion.objects.filter(anio=2027).count(), 1)
        self.assertEqual(r.status_code, 200)

    def test_votante_no_entra_al_panel_de_ediciones(self):
        self.client.force_login(self.ana)
        r = self.client.get(reverse("panel:ediciones"))
        self.assertRedirects(r, reverse("votaciones:inicio"))

    def test_fechas_de_la_edicion_en_orden(self):
        self.client.force_login(self.admin)
        hoy = self.ahora.date()
        self.client.post(reverse("panel:ediciones"), {"anio": 2029, "nombre": "Festival 2029",
                                                      "fecha_inicio": hoy, "fecha_fin": hoy - timedelta(days=3)})
        self.assertFalse(Edicion.objects.filter(anio=2029).exists())
