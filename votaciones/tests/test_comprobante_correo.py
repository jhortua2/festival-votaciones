"""Comprobante del voto por correo (RF-10).

- Al votar, al votante le llega un correo con su código de comprobante.
- Si el correo falla, el voto igual queda guardado y se anota en la auditoría.
- Un voto rechazado (por ejemplo, el segundo en la misma categoría) no envía correo.

Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_comprobante_correo
"""
from smtplib import SMTPException
from unittest import mock

from django.core import mail
from django.urls import reverse

from auditoria.models import Registro
from votaciones.models import Voto

from .test_entrega3 import Base


class ComprobantePorCorreo(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.votante)

    def test_al_votar_llega_el_comprobante(self):
        r = self.votar_web(self.cancion, self.c1)
        voto = Voto.objects.get(usuario=self.votante)
        self.assertRedirects(r, reverse("votaciones:comprobante", args=[voto.codigo]), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, [self.votante.email])
        self.assertIn(voto.codigo, correo.subject)
        self.assertIn(voto.codigo, correo.body)
        self.assertIn(self.c1.nombre, correo.body)
        self.assertIn(self.cancion.nombre, correo.body)
        html = correo.alternatives[0][0]
        self.assertIn(voto.codigo, html)

    def test_si_el_correo_falla_el_voto_queda_guardado(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=SMTPException("caido")):
            r = self.votar_web(self.cancion, self.c1)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Voto.objects.filter(usuario=self.votante, opcion=self.c1).exists())
        self.assertTrue(Registro.objects.filter(accion="correo_fallido", detalle__startswith="Comprobante").exists())

    def test_voto_rechazado_no_envia_correo(self):
        self.votar_web(self.cancion, self.c1)
        mail.outbox.clear()
        self.votar_web(self.aire, self.a1)            # misma categoría (Música): se rechaza
        self.assertEqual(len(mail.outbox), 0)

    def test_la_pantalla_avisa_que_se_envio_copia(self):
        r = self.votar_web(self.cancion, self.c1)
        r = self.client.get(r["Location"])
        self.assertContains(r, "También te enviamos una copia a tu correo")
