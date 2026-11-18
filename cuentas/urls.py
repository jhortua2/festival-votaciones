from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("registro/", views.registro, name="registro"),
    path("ingresar/", views.Ingreso.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("mis-votos/", views.mis_votos, name="mis_votos"),
    # ¿Olvidaste tu contraseña? (RF-02)
    path("recuperar/", views.RecuperarContrasena.as_view(), name="recuperar"),
    path("recuperar/enviado/", views.RecuperarEnviado.as_view(), name="recuperar_enviado"),
    path("recuperar/<uidb64>/<token>/", views.NuevaContrasena.as_view(), name="recuperar_confirmar"),
    path("recuperar/listo/", views.ContrasenaCambiada.as_view(), name="recuperar_listo"),
]
