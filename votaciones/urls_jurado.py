from django.urls import path

from . import views_jurado as v

app_name = "jurado"

urlpatterns = [
    path("", v.inicio, name="inicio"),
    path("votaciones/<int:pk>/", v.calificar_votacion, name="calificar"),
]
