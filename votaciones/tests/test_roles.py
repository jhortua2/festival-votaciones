"""Permisos por rol en la votación (Eje 4).

- RN-16 (propuesta): el administrador gestiona las votaciones y no vota.
- Una votación solo de público no lleva jurado: el formulario del panel no deja asignarlo
  y la pantalla del jurado no la muestra.

Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_roles
"""
from django.urls import reverse

from cuentas.models import Usuario
from votaciones.models import Votacion, Voto
from votaciones.servicios import VotoRechazado, emitir_voto

from .test_entrega3 import CLAVE, Base


class AdministradorNoVota(Base):
    def test_servicio_rechaza_al_administrador(self):
        with self.assertRaises(VotoRechazado) as e:
            emitir_voto(self.admin, self.a1.pk)
        self.assertEqual(e.exception.motivo, "admin_no_vota")
        self.assertFalse(Voto.objects.filter(usuario=self.admin).exists())

    def test_formulario_web_rechaza_al_administrador(self):
        self.client.force_login(self.admin)
        r = self.votar_web(self.aire, self.a1)
        self.assertEqual(r.status_code, 409)
        self.assertContains(r, "Los administradores no votan", status_code=409)
        self.assertFalse(Voto.objects.exists())

    def test_detalle_muestra_aviso_y_no_el_boton(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("votaciones:detalle", args=[self.aire.pk]))
        self.assertContains(r, "Eres administrador")
        self.assertNotContains(r, reverse("votaciones:opciones", args=[self.aire.pk]) + '">Ver las')

    def test_votante_si_puede_votar(self):
        voto = emitir_voto(self.votante, self.a1.pk)
        self.assertEqual(voto.usuario, self.votante)


class JuradoSoloEnVotacionesConJurado(Base):
    def setUp(self):
        super().setUp()
        self.jurado = Usuario.objects.create_user(username="j@x.co", email="j@x.co", password=CLAVE,
                                                  first_name="Rafael", rol=Usuario.Rol.JURADO)

    def datos_formulario(self, votacion, **cambios):
        datos = {
            "categoria": votacion.categoria_id, "nombre": votacion.nombre, "descripcion": "",
            "apertura": votacion.apertura.strftime("%Y-%m-%dT%H:%M"),
            "cierre": votacion.cierre.strftime("%Y-%m-%dT%H:%M"),
            "visibilidad": votacion.visibilidad, "modo": votacion.modo,
            "peso_jurado": votacion.peso_jurado, "escala_maxima": votacion.escala_maxima,
            "jurados": [self.jurado.pk],
        }
        datos.update(cambios)
        return datos

    def test_no_se_asigna_jurado_a_votacion_solo_de_publico(self):
        self.client.force_login(self.admin)
        url = reverse("panel:votacion_editar", args=[self.aire.pk])
        r = self.client.post(url, self.datos_formulario(self.aire))
        self.assertContains(r, "no llevan jurado")
        self.assertFalse(self.aire.jurados.exists())

    def test_si_se_asigna_en_votacion_combinada(self):
        self.client.force_login(self.admin)
        url = reverse("panel:votacion_editar", args=[self.aire.pk])
        self.client.post(url, self.datos_formulario(self.aire, modo=Votacion.Modo.COMBINADO, peso_jurado=70))
        self.assertTrue(self.aire.jurados.filter(pk=self.jurado.pk).exists())

    def test_pantalla_del_jurado_oculta_votaciones_solo_de_publico(self):
        self.aire.jurados.add(self.jurado)                    # asignación vieja o hecha por fuera
        self.cancion.modo = Votacion.Modo.COMBINADO
        self.cancion.save()
        self.cancion.jurados.add(self.jurado)
        self.client.force_login(self.jurado)
        r = self.client.get(reverse("jurado:inicio"))
        self.assertContains(r, "Mejor canción inédita")
        self.assertNotContains(r, "Tu aire favorito")
