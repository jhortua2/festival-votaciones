from django.urls import path

from . import views

app_name = "votaciones"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("categorias/", views.categorias, name="categorias"),
    path("categorias/<int:pk>/", views.categoria_detalle, name="categoria"),
    path("votaciones/<int:pk>/", views.votacion_detalle, name="detalle"),
    path("votaciones/<int:pk>/opciones/", views.votacion_opciones, name="opciones"),
    path("votaciones/<int:pk>/confirmar/", views.confirmar, name="confirmar"),
    path("comprobante/<str:codigo>/", views.comprobante, name="comprobante"),
]
