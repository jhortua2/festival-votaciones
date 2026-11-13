"""Publicación de resultados y cálculo de ganadores (Eje 4).

- El ganador se calcula según el modo de cada votación (RN-11): solo público, solo jurado,
  combinado (peso del jurado + peso del público) o independiente (fallo del jurado y
  reconocimiento del público por separado).
- Mientras la votación no cierra, el ganador es provisional ("va ganando").
- Un empate se detecta y se informa; el criterio de desempate está pendiente (RN-12).
- La página pública /resultados/ respeta la visibilidad de cada votación (RN-10) y no muestra
  datos de los votantes.

Ejecutar solo estas pruebas:  py manage.py test votaciones.tests.test_resultados
"""
from datetime import timedelta

from django.urls import reverse

from cuentas.models import Usuario
from votaciones.models import Calificacion, Opcion, Votacion, Voto

from .test_entrega3 import CLAVE, Base


class Ganadores(Base):
    def votantes(self, n):
        return [Usuario.objects.create_user(username=f"v{i}@x.co", email=f"v{i}@x.co", password=CLAVE) for i in range(n)]

    def votar(self, usuario, opcion):
        Voto.objects.create(usuario=usuario, opcion=opcion)

    def calificar(self, jurado, votacion, puntajes):
        for opcion, puntaje in puntajes.items():
            Calificacion.objects.create(jurado=jurado, votacion=votacion, opcion=opcion, puntaje=puntaje)

    def cerrar(self, votacion):
        votacion.cierre = self.ahora - timedelta(minutes=1)
        votacion.save()

    def test_solo_publico_gana_el_mas_votado(self):
        paseo, merengue = self.a1, Opcion.objects.create(votacion=self.aire, nombre="Merengue", orden=2)
        a, b, c = self.votantes(3)
        self.votar(a, paseo); self.votar(b, paseo); self.votar(c, merengue)
        g = self.aire.ganadores()
        self.assertEqual(g["oficial"]["opciones"], [paseo])
        self.assertFalse(g["oficial"]["empate"])
        self.assertFalse(g["definitivo"])                    # sigue abierta: va ganando
        self.cerrar(self.aire)
        self.assertTrue(self.aire.ganadores()["definitivo"])

    def test_empate_se_detecta_y_no_se_resuelve(self):
        merengue = Opcion.objects.create(votacion=self.aire, nombre="Merengue", orden=2)
        a, b = self.votantes(2)
        self.votar(a, self.a1); self.votar(b, merengue)
        g = self.aire.ganadores()
        self.assertTrue(g["oficial"]["empate"])
        self.assertEqual(set(g["oficial"]["opciones"]), {self.a1, merengue})

    def test_sin_votos_no_hay_ganador(self):
        self.assertEqual(self.aire.ganadores()["oficial"]["opciones"], [])

    def test_combinado_el_jurado_pesa_mas(self):
        # Público: c1 gana 2 a 1. Jurado: c2 gana 9 a 3. Con 70 % jurado, gana c2.
        self.cancion.modo, self.cancion.peso_jurado = Votacion.Modo.COMBINADO, 70
        self.cancion.save()
        a, b, c = self.votantes(3)
        self.votar(a, self.c1); self.votar(b, self.c1); self.votar(c, self.c2)
        jurado = Usuario.objects.create_user(username="j@x.co", email="j@x.co", password=CLAVE, rol="jurado")
        self.calificar(jurado, self.cancion, {self.c1: 3, self.c2: 9})
        self.assertEqual(self.cancion.ganadores()["oficial"]["opciones"], [self.c2])

    def test_independiente_dos_ganadores(self):
        self.rey_v.modo = Votacion.Modo.INDEPENDIENTE
        self.rey_v.save()
        a, b = self.votantes(2)
        self.votar(a, self.r1); self.votar(b, self.r1)       # el público prefiere #05
        jurado = Usuario.objects.create_user(username="j@x.co", email="j@x.co", password=CLAVE, rol="jurado")
        self.calificar(jurado, self.rey_v, {self.r1: 4, self.r2: 8})   # el jurado prefiere #12
        g = self.rey_v.ganadores()
        self.assertEqual(g["oficial"]["opciones"], [self.r2])
        self.assertEqual(g["publico"]["opciones"], [self.r1])

    def test_panel_muestra_el_ganador(self):
        a, = self.votantes(1)
        self.votar(a, self.a1)
        self.cerrar(self.aire)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("panel:resultados_votacion", args=[self.aire.pk]))
        self.assertContains(r, "Ganador")
        self.assertContains(r, "Paseo")


class PublicacionDeResultados(Base):
    def setUp(self):
        super().setUp()
        Voto.objects.create(usuario=self.votante, opcion=self.a1)

    def test_tiempo_real_se_publica_mientras_esta_abierta(self):
        self.aire.visibilidad = Votacion.Visibilidad.TIEMPO_REAL
        self.aire.save()
        r = self.client.get(reverse("votaciones:resultados"))
        self.assertContains(r, "Tu aire favorito")
        self.assertContains(r, "Va ganando")

    def test_al_cierre_no_se_publica_antes_de_cerrar(self):
        self.aire.visibilidad = Votacion.Visibilidad.AL_CIERRE
        self.aire.save()
        self.assertNotContains(self.client.get(reverse("votaciones:resultados")), "Tu aire favorito")
        self.aire.cierre = self.ahora - timedelta(minutes=1)
        self.aire.save()
        r = self.client.get(reverse("votaciones:resultados"))
        self.assertContains(r, "Tu aire favorito")
        self.assertContains(r, "Ganador")

    def test_solo_administradores_nunca_se_publica(self):
        self.aire.visibilidad = Votacion.Visibilidad.SOLO_ADMIN
        self.aire.cierre = self.ahora - timedelta(minutes=1)
        self.aire.save()
        self.assertNotContains(self.client.get(reverse("votaciones:resultados")), "Tu aire favorito")

    def test_no_muestra_datos_de_votantes(self):
        self.aire.visibilidad = Votacion.Visibilidad.TIEMPO_REAL
        self.aire.save()
        r = self.client.get(reverse("votaciones:resultados"))
        self.assertNotContains(r, self.votante.email)


class ResultadosEnElInicio(Base):
    def test_inicio_muestra_quien_va_ganando(self):
        self.aire.visibilidad = Votacion.Visibilidad.TIEMPO_REAL
        self.aire.save()
        Voto.objects.create(usuario=self.votante, opcion=self.a1)
        r = self.client.get(reverse("votaciones:inicio"))
        self.assertContains(r, "Va ganando")
        self.assertContains(r, "Paseo")
        self.assertContains(r, "Ver todos los resultados")
        self.assertNotContains(r, self.votante.email)

    def test_sin_resultados_publicables_no_aparece_la_seccion(self):
        for v in Votacion.objects.all():
            v.visibilidad = Votacion.Visibilidad.SOLO_ADMIN
            v.save()
        r = self.client.get(reverse("votaciones:inicio"))
        self.assertNotContains(r, "Ver todos los resultados")


    def test_independiente_muestra_publico_aunque_el_jurado_no_haya_calificado(self):
        self.rey_v.modo = Votacion.Modo.INDEPENDIENTE
        self.rey_v.visibilidad = Votacion.Visibilidad.TIEMPO_REAL
        self.rey_v.save()
        Voto.objects.create(usuario=self.votante, opcion=self.r1)
        r = self.client.get(reverse("votaciones:inicio"))
        self.assertContains(r, "Jurado: aún sin calificar")
        self.assertContains(r, "Va ganando público")
        self.assertContains(r, self.r1.nombre)
