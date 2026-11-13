from django.urls import path

from . import api, views

app_name = "votaciones"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("ediciones/", views.ediciones, name="ediciones"),
    path("categorias/", views.categorias, name="categorias"),
    path("categorias/<int:pk>/", views.categoria_detalle, name="categoria"),
    path("votaciones/<int:pk>/", views.votacion_detalle, name="detalle"),
    path("votaciones/<int:pk>/opciones/", views.votacion_opciones, name="opciones"),
    path("votaciones/<int:pk>/confirmar/", views.confirmar, name="confirmar"),
    path("comprobante/<str:codigo>/", views.comprobante, name="comprobante"),
    path("resultados/", views.resultados, name="resultados"),
    # API GET de consulta (Entrega 3): categorías y opciones en JSON desde MySQL
    path("api/categorias/", api.categorias, name="api_categorias"),
]
