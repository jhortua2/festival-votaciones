"""Gestión de usuarios desde el panel de la aplicación (Eje 4).

El administrador crea cuentas de administrador o jurado, cambia el rol de cualquier usuario y
las activa o desactiva sin usar Django Admin ni la terminal. Los votantes se registran solos.

Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_usuarios_panel
"""
from django.test import TestCase
from django.urls import reverse

from auditoria.models import Registro
from cuentas.models import Usuario

CLAVE = "Clave-Segura-2027"


class GestionDeUsuarios(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username="admin@x.co", email="admin@x.co", password=CLAVE,
                                                 rol=Usuario.Rol.ADMIN, is_staff=True)
        self.votante = Usuario.objects.create_user(username="ana@x.co", email="ana@x.co", password=CLAVE, first_name="Ana")
        self.client.force_login(self.admin)

    def crear(self, rol, email="nuevo@x.co", **extra):
        datos = {"first_name": "Nuevo", "last_name": "Usuario", "email": email, "rol": rol,
                 "password1": CLAVE, "password2": CLAVE}
        datos.update(extra)
        return self.client.post(reverse("panel:usuarios"), datos, follow=True)

    def test_lista_de_usuarios(self):
        r = self.client.get(reverse("panel:usuarios"))
        self.assertContains(r, "ana@x.co")
        self.assertContains(r, "csrfmiddlewaretoken")

    def test_crear_administrador_que_entra_al_panel(self):
        self.crear(Usuario.Rol.ADMIN)
        u = Usuario.objects.get(email="nuevo@x.co")
        self.assertEqual(u.rol, Usuario.Rol.ADMIN)
        self.assertTrue(u.is_staff)
        self.assertFalse(u.is_superuser)
        self.client.logout()
        self.assertTrue(self.client.login(username="nuevo@x.co", password=CLAVE))
        self.assertEqual(self.client.get(reverse("panel:panel")).status_code, 200)
        self.assertTrue(Registro.objects.filter(accion="usuario_creado").exists())

    def test_crear_jurado(self):
        self.crear(Usuario.Rol.JURADO, email="jurado2@x.co")
        self.assertEqual(Usuario.objects.get(email="jurado2@x.co").rol, Usuario.Rol.JURADO)

    def test_votante_no_se_crea_desde_el_panel(self):
        r = self.crear(Usuario.Rol.VOTANTE, email="votante2@x.co")
        self.assertFalse(Usuario.objects.filter(email="votante2@x.co").exists())
        self.assertContains(r, "Escoja una opción válida")

    def test_la_contrasena_se_guarda_cifrada(self):
        self.crear(Usuario.Rol.JURADO)
        u = Usuario.objects.get(email="nuevo@x.co")
        self.assertNotEqual(u.password, CLAVE)
        self.assertTrue(u.check_password(CLAVE))

    def test_correo_repetido_y_claves_distintas(self):
        r = self.crear(Usuario.Rol.JURADO, email="ana@x.co")
        self.assertContains(r, "Ya existe una cuenta")
        r = self.crear(Usuario.Rol.JURADO, password2="Otra-Clave-2027")
        self.assertContains(r, "no coinciden")
        self.assertFalse(Usuario.objects.filter(email="nuevo@x.co").exists())

    def test_cambiar_rol_de_votante_a_administrador(self):
        url = reverse("panel:usuario_editar", args=[self.votante.pk])
        self.client.post(url, {"first_name": "Ana", "last_name": "", "email": "ana@x.co", "rol": Usuario.Rol.ADMIN})
        self.votante.refresh_from_db()
        self.assertEqual(self.votante.rol, Usuario.Rol.ADMIN)
        self.assertTrue(self.votante.is_staff)

    def test_quitar_rol_admin_tambien_quita_superusuario(self):
        otro = Usuario.objects.create_user(username="su@x.co", email="su@x.co", password=CLAVE,
                                           rol=Usuario.Rol.ADMIN, is_staff=True, is_superuser=True)
        url = reverse("panel:usuario_editar", args=[otro.pk])
        self.client.post(url, {"first_name": "", "last_name": "", "email": "su@x.co", "rol": Usuario.Rol.VOTANTE})
        otro.refresh_from_db()
        self.assertFalse(otro.es_admin)

    def test_no_puede_cambiar_su_propio_rol(self):
        url = reverse("panel:usuario_editar", args=[self.admin.pk])
        r = self.client.post(url, {"first_name": "", "last_name": "", "email": "admin@x.co", "rol": Usuario.Rol.VOTANTE})
        self.assertContains(r, "No puedes cambiar tu propio rol")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, Usuario.Rol.ADMIN)

    def test_cambiar_contrasena_desde_el_panel(self):
        url = reverse("panel:usuario_editar", args=[self.votante.pk])
        self.client.post(url, {"first_name": "Ana", "last_name": "", "email": "ana@x.co", "rol": Usuario.Rol.VOTANTE,
                               "password1": "Nueva-Clave-2028", "password2": "Nueva-Clave-2028"})
        self.votante.refresh_from_db()
        self.assertTrue(self.votante.check_password("Nueva-Clave-2028"))

    def test_desactivar_impide_iniciar_sesion(self):
        self.client.post(reverse("panel:usuario_estado", args=[self.votante.pk]))
        self.votante.refresh_from_db()
        self.assertFalse(self.votante.is_active)
        self.client.logout()
        self.assertFalse(self.client.login(username="ana@x.co", password=CLAVE))

    def test_no_puede_desactivarse_a_si_mismo(self):
        self.client.post(reverse("panel:usuario_estado", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_estado_exige_post(self):
        self.assertEqual(self.client.get(reverse("panel:usuario_estado", args=[self.votante.pk])).status_code, 405)

    def test_votante_y_jurado_no_entran_a_usuarios(self):
        jurado = Usuario.objects.create_user(username="j@x.co", email="j@x.co", password=CLAVE, rol=Usuario.Rol.JURADO)
        for u in (self.votante, jurado):
            self.client.force_login(u)
            r = self.client.post(reverse("panel:usuarios"), {"first_name": "X", "email": "hack@x.co", "rol": "admin",
                                                             "password1": CLAVE, "password2": CLAVE})
            self.assertEqual(r.status_code, 302)
        self.assertFalse(Usuario.objects.filter(email="hack@x.co").exists())
