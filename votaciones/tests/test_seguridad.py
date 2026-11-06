"""Seguridad de formularios y de Django (Entrega 3 · criterio 3.2).

- Token CSRF en los formularios POST y página propia cuando falta (403).
- Límite de intentos de inicio de sesión.
- Cabeceras de seguridad y cookies protegidas.
"""
from django.conf import settings
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from auditoria.models import Registro
from cuentas.models import Usuario

from .test_entrega3 import Base

CLAVE = "Clave-Segura-2027"


class TokenCSRF(Base):
    def test_los_formularios_traen_el_token(self):
        self.client.force_login(self.votante)
        r = self.client.get(reverse("votaciones:confirmar", args=[self.cancion.pk]), {"opcion": self.c1.pk})
        self.assertContains(r, 'name="csrfmiddlewaretoken"')
        self.client.logout()
        for url in (reverse("cuentas:login"), reverse("cuentas:registro")):
            self.assertContains(self.client.get(url), 'name="csrfmiddlewaretoken"')

    def test_sin_token_se_rechaza_con_pagina_propia_y_queda_en_auditoria(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.votante)
        r = c.post(reverse("votaciones:confirmar", args=[self.cancion.pk]), {"opcion": self.c1.pk, "confirmado": "on"})
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "No pudimos verificar el formulario", status_code=403)
        self.assertTrue(Registro.objects.filter(accion="csrf_rechazado").exists())

    def test_con_token_si_funciona(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.votante)
        url = reverse("votaciones:confirmar", args=[self.cancion.pk])
        c.get(url, {"opcion": self.c1.pk})
        token = c.cookies[settings.CSRF_COOKIE_NAME].value
        r = c.post(url, {"opcion": self.c1.pk, "confirmado": "on", "csrfmiddlewaretoken": token})
        self.assertEqual(r.status_code, 302)

    def test_panel_tambien_exige_token(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.admin)
        r = c.post(reverse("panel:categoria_eliminar", args=[self.rey.pk]))
        self.assertEqual(r.status_code, 403)


@override_settings(LOGIN_MAX_INTENTOS=3, LOGIN_BLOQUEO_MINUTOS=15)
class LimiteDeIntentos(TestCase):
    def setUp(self):
        cache.clear()
        self.u = Usuario.objects.create_user(username="ana@x.co", email="ana@x.co", password=CLAVE)

    def entrar(self, clave):
        return self.client.post(reverse("cuentas:login"), {"username": "ana@x.co", "password": clave})

    def test_bloquea_despues_de_varios_fallos(self):
        for _ in range(3):
            self.assertContains(self.entrar("mala-clave"), "Correo o contraseña incorrectos")
        r = self.entrar(CLAVE)                       # aunque ahora la clave sea correcta
        self.assertContains(r, "Demasiados intentos fallidos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_un_ingreso_correcto_reinicia_el_contador(self):
        self.entrar("mala-clave")
        self.entrar("mala-clave")
        self.assertEqual(self.entrar(CLAVE).status_code, 302)
        self.client.logout()
        self.entrar("mala-clave")
        self.assertEqual(self.entrar(CLAVE).status_code, 302)


class CabecerasYCookies(TestCase):
    def test_cabeceras_de_seguridad(self):
        r = self.client.get(reverse("cuentas:login"))
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r["Referrer-Policy"], "same-origin")

    def test_cookies_protegidas(self):
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertLessEqual(settings.SESSION_COOKIE_AGE, 2 * 60 * 60)

    def test_contrasenas_con_hash(self):
        u = Usuario.objects.create_user(username="b@x.co", email="b@x.co", password=CLAVE)
        self.assertNotEqual(u.password, CLAVE)
        self.assertTrue(u.password.startswith("pbkdf2_sha256$"))
