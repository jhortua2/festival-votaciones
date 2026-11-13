"""Permisos de consulta administrativa y protección de datos personales (Eje 4).

- Solo el administrador consulta los votos; el votante y el jurado no entran.
- En la consulta de votos el correo de quien votó se muestra parcialmente.
- Cada consulta de votos queda registrada en la auditoría.
- Un votante solo ve sus propios comprobantes.
- La API, el CSV de resultados y la página pública de resultados no exponen datos de votantes.
- En la auditoría la IP se muestra recortada.

Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_datos_personales
"""
from django.urls import reverse

from auditoria.models import Registro
from cuentas.models import Usuario
from votaciones.models import Votacion
from votaciones.servicios import emitir_voto
from votaciones.templatetags.festival import ocultar_correo, ocultar_ip

from .test_entrega3 import CLAVE, Base


class DatosPersonales(Base):
    def setUp(self):
        super().setUp()
        self.voto = emitir_voto(self.votante, self.a1.pk)

    def test_ocultar_correo_e_ip(self):
        self.assertEqual(ocultar_correo("votante@festival.test"), "vo*****@festival.test")
        self.assertEqual(ocultar_correo("ab@x.co"), "a***@x.co")
        self.assertEqual(ocultar_ip("190.25.33.14"), "190.25.*.*")

    def test_consulta_de_votos_oculta_el_correo(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("panel:votos"))
        self.assertContains(r, self.voto.codigo)
        self.assertContains(r, ocultar_correo(self.votante.email))
        self.assertNotContains(r, f"<td>{self.votante.email}</td>", html=False)

    def test_cada_consulta_queda_en_auditoria(self):
        self.client.force_login(self.admin)
        self.client.get(reverse("panel:votos"), {"q": "VLL"})
        registro = Registro.objects.filter(accion="consulta_votos").latest("fecha")
        self.assertEqual(registro.usuario, self.admin)
        self.assertIn("busqueda=VLL", registro.detalle)

    def test_votante_y_jurado_no_consultan_votos_ni_resultados(self):
        jurado = Usuario.objects.create_user(username="j@x.co", email="j@x.co", password=CLAVE, rol=Usuario.Rol.JURADO)
        for u in (self.votante, jurado):
            self.client.force_login(u)
            for nombre in ("panel:votos", "panel:resultados", "panel:auditoria", "panel:usuarios"):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 302, (u.email, nombre))
            self.assertEqual(self.client.get(reverse("panel:resultados_csv", args=[self.aire.pk])).status_code, 302)

    def test_votante_no_ve_el_comprobante_de_otro(self):
        otro = Usuario.objects.create_user(username="otro@x.co", email="otro@x.co", password=CLAVE)
        self.client.force_login(otro)
        self.assertEqual(self.client.get(reverse("votaciones:comprobante", args=[self.voto.codigo])).status_code, 404)

    def test_csv_api_y_resultados_publicos_sin_datos_de_votantes(self):
        self.aire.visibilidad = Votacion.Visibilidad.TIEMPO_REAL
        self.aire.save()
        self.client.force_login(self.admin)
        csv = self.client.get(reverse("panel:resultados_csv", args=[self.aire.pk])).content.decode("utf-8")
        self.assertNotIn(self.votante.email, csv)
        self.client.logout()
        for url in (reverse("votaciones:api_categorias"), reverse("votaciones:resultados")):
            r = self.client.get(url)
            self.assertNotContains(r, self.votante.email)
            self.assertNotContains(r, self.voto.codigo)
