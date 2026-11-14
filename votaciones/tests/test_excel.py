"""Descarga de resultados en Excel desde el panel (pedido del profesor, Eje 4).

Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_excel
"""
from io import BytesIO

from django.urls import reverse
from openpyxl import load_workbook

from auditoria.models import Registro
from votaciones.models import Voto

from .test_entrega3 import Base


class DescargaExcel(Base):
    def descargar(self):
        self.client.force_login(self.admin)
        return self.client.get(reverse("panel:resultados_excel"))

    def test_descarga_un_xlsx_con_resumen_y_quien_va_ganando(self):
        Voto.objects.create(usuario=self.votante, opcion=self.a1)
        r = self.descargar()
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertIn(".xlsx", r["Content-Disposition"])
        libro = load_workbook(BytesIO(r.content))
        self.assertEqual(libro.sheetnames[0], "Resumen")
        resumen = [c for fila in libro["Resumen"].iter_rows(values_only=True) for c in fila if c]
        self.assertIn(self.aire.nombre, resumen)
        self.assertIn(self.a1.nombre, resumen)            # va ganando
        self.assertGreater(len(libro.sheetnames), 1)      # una hoja de detalle por votación

    def test_no_incluye_datos_de_votantes(self):
        Voto.objects.create(usuario=self.votante, opcion=self.a1)
        libro = load_workbook(BytesIO(self.descargar().content))
        todo = " ".join(str(c) for h in libro for fila in h.iter_rows(values_only=True) for c in fila if c)
        self.assertNotIn(self.votante.email, todo)

    def test_queda_en_la_auditoria(self):
        self.descargar()
        self.assertTrue(Registro.objects.filter(accion="resultados_exportados", detalle__contains="Excel").exists())

    def test_solo_administradores(self):
        self.client.force_login(self.votante)
        r = self.client.get(reverse("panel:resultados_excel"))
        self.assertEqual(r.status_code, 302)

    def test_boton_en_resultados_del_panel(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("panel:resultados")), "Descargar Excel")
