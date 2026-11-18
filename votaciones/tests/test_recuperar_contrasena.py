"""¿Olvidaste tu contraseña? (RF-02).

- Llega un correo con un enlace a la dirección con la que la persona se registró.
- Con el enlace se crea una contraseña nueva y se puede iniciar sesión con ella.
- El enlace sirve una sola vez.
- Si el correo no existe, la pantalla dice lo mismo (no revela quién está registrado) y no se envía nada.
- Si el servidor de correo falla, no se muestra un error: queda anotado en la auditoría para el administrador.

En las pruebas Django no envía correos de verdad: los guarda en mail.outbox.
Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_recuperar_contrasena
"""
import re
from smtplib import SMTPException
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from auditoria.models import Registro
from cuentas import intentos
from cuentas.models import Usuario

CLAVE_VIEJA = "Clave-Vieja-2027"
CLAVE_NUEVA = "Nueva-Clave-Segura-2028"


class RecuperarContrasena(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(username="ana@hotmail.com", email="ana@hotmail.com",
                                                   password=CLAVE_VIEJA, first_name="Ana")

    def pedir(self, correo):
        return self.client.post(reverse("cuentas:recuperar"), {"email": correo})

    def enlace(self):
        return re.search(r"https?://[^/\s]+(/cuentas/recuperar/[^\s\"]+/)", mail.outbox[-1].body).group(1)

    def test_el_login_tiene_el_enlace(self):
        self.assertContains(self.client.get(reverse("cuentas:login")), reverse("cuentas:recuperar"))

    def test_envia_el_correo_a_la_direccion_registrada(self):
        r = self.pedir("ana@hotmail.com")
        self.assertRedirects(r, reverse("cuentas:recuperar_enviado"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@hotmail.com"])
        self.assertIn("Recupera tu contraseña", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].extra_headers.get("Content-Language"), "es")
        self.assertTrue(Registro.objects.filter(accion="recuperacion_solicitada").exists())

    def test_con_el_enlace_cambia_la_contrasena_y_puede_entrar(self):
        self.pedir("ana@hotmail.com")
        r = self.client.get(self.enlace(), follow=True)              # Django cambia el código por una sesión
        self.assertContains(r, "Crea tu nueva contraseña")
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": CLAVE_NUEVA, "new_password2": CLAVE_NUEVA})
        self.assertRedirects(r, reverse("cuentas:recuperar_listo"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_NUEVA))
        self.assertFalse(self.usuario.check_password(CLAVE_VIEJA))
        self.assertTrue(Registro.objects.filter(accion="contrasena_restablecida", usuario=self.usuario).exists())
        self.assertTrue(self.client.login(username="ana@hotmail.com", password=CLAVE_NUEVA))

    def test_el_enlace_sirve_una_sola_vez(self):
        self.pedir("ana@hotmail.com")
        enlace = self.enlace()
        r = self.client.get(enlace, follow=True)
        self.client.post(r.redirect_chain[-1][0], {"new_password1": CLAVE_NUEVA, "new_password2": CLAVE_NUEVA})
        self.client.logout()
        self.assertContains(self.client.get(enlace, follow=True), "Este enlace ya no sirve")

    def test_enlace_inventado_no_sirve(self):
        r = self.client.get(reverse("cuentas:recuperar_confirmar", args=["MQ", "codigo-falso"]), follow=True)
        self.assertContains(r, "Este enlace ya no sirve")

    def test_correo_no_registrado_no_revela_nada(self):
        r = self.pedir("nadie@gmail.com")
        self.assertRedirects(r, reverse("cuentas:recuperar_enviado"))   # misma pantalla que si existiera
        self.assertEqual(len(mail.outbox), 0)

    def test_cuenta_inactiva_no_recibe_correo(self):
        self.usuario.is_active = False
        self.usuario.save()
        self.pedir("ana@hotmail.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_aplica_las_reglas_de_contrasena(self):
        self.pedir("ana@hotmail.com")
        r = self.client.get(self.enlace(), follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "123", "new_password2": "123"})
        self.assertEqual(r.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_VIEJA))

    def test_desbloquea_la_cuenta_bloqueada_por_intentos(self):
        for _ in range(10):
            intentos.fallo("ana@hotmail.com")
        self.assertTrue(intentos.bloqueado("ana@hotmail.com"))
        self.pedir("ana@hotmail.com")
        r = self.client.get(self.enlace(), follow=True)
        self.client.post(r.redirect_chain[-1][0], {"new_password1": CLAVE_NUEVA, "new_password2": CLAVE_NUEVA})
        self.assertFalse(intentos.bloqueado("ana@hotmail.com"))

    def test_si_el_correo_falla_queda_en_la_auditoria(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=SMTPException("caido")):
            r = self.pedir("ana@hotmail.com")
        self.assertRedirects(r, reverse("cuentas:recuperar_enviado"))   # sin pantalla de error
        self.assertTrue(Registro.objects.filter(accion="correo_fallido").exists())
