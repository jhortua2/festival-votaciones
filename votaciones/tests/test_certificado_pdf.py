"""Certificado de resultados en PDF (P-12).

- Si alguna votación sigue abierta, el PDF es un REPORTE PARCIAL (no certificado).
- Si todas están cerradas, es un CERTIFICADO.
- La huella (SHA-256) es la misma con los mismos datos y cambia si cambian los votos.
- Solo lo descargan los administradores, queda en la auditoría y no trae datos de votantes.

Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_certificado_pdf
"""
from datetime import timedelta

from django.urls import reverse
from reportlab import rl_config

from auditoria.models import Registro
from cuentas.models import Usuario
from votaciones.certificado import pdf_resultados
from votaciones.models import Votacion, Voto

from .test_entrega3 import CLAVE, Base


def texto(contenido):
    """Texto del PDF. En las pruebas el PDF se genera sin comprimir, así las frases se pueden buscar."""
    return contenido.decode("latin-1")


class CertificadoPDF(Base):
    def setUp(self):
        super().setUp()
        self._compresion = rl_config.pageCompression
        rl_config.pageCompression = 0
        self.addCleanup(setattr, rl_config, "pageCompression", self._compresion)

    def votaciones(self):
        return list(Votacion.objects.filter(categoria__edicion=self.ed, publicada=True).select_related("categoria"))

    def cerrar_todas(self):
        Votacion.objects.update(cierre=self.ahora - timedelta(minutes=1))

    def test_descarga_desde_el_panel(self):
        Voto.objects.create(usuario=self.votante, opcion=self.a1)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("panel:resultados_pdf"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn(".pdf", r["Content-Disposition"])
        t = texto(r.content)
        self.assertIn("Tu aire favorito", t)
        self.assertIn("Paseo", t)
        self.assertNotIn(self.votante.email, t)                          # sin datos de votantes
        self.assertTrue(Registro.objects.filter(accion="resultados_exportados", detalle__contains="huella").exists())

    def test_con_votaciones_abiertas_es_reporte_parcial(self):
        contenido, _, es_certificado = pdf_resultados(self.ed, self.votaciones(), "Admin")
        self.assertFalse(es_certificado)
        self.assertIn("NO ES UN CERTIFICADO", texto(contenido))

    def test_todas_cerradas_es_certificado(self):
        Voto.objects.create(usuario=self.votante, opcion=self.a1)
        self.cerrar_todas()
        contenido, _, es_certificado = pdf_resultados(self.ed, self.votaciones(), "Admin")
        self.assertTrue(es_certificado)
        t = texto(contenido)
        self.assertIn("Certificado de resultados", t)
        self.assertIn("Ganador", t)

    def test_la_huella_cambia_si_cambian_los_votos(self):
        _, h1, _ = pdf_resultados(self.ed, self.votaciones(), "Admin")
        _, h2, _ = pdf_resultados(self.ed, self.votaciones(), "Admin")
        self.assertEqual(h1, h2)                                          # mismos datos → misma huella
        Voto.objects.create(usuario=self.votante, opcion=self.a1)
        _, h3, _ = pdf_resultados(self.ed, self.votaciones(), "Admin")
        self.assertNotEqual(h1, h3)

    def test_solo_administradores(self):
        jurado = Usuario.objects.create_user(username="j@x.co", email="j@x.co", password=CLAVE, rol="jurado")
        for u in (self.votante, jurado):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("panel:resultados_pdf")).status_code, 302)

    def test_boton_en_resultados_del_panel(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("panel:resultados")), "Certificado PDF")
