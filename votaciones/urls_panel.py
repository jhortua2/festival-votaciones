from django.urls import path

from . import views_panel as v

app_name = "panel"

urlpatterns = [
    path("", v.panel, name="panel"),
    path("ediciones/", v.ediciones, name="ediciones"),
    path("ediciones/<int:pk>/editar/", v.edicion_editar, name="edicion_editar"),
    path("ediciones/<int:pk>/activar/", v.edicion_activar, name="edicion_activar"),
    path("categorias/", v.categorias, name="categorias"),
    path("categorias/<int:pk>/editar/", v.categoria_editar, name="categoria_editar"),
    path("categorias/<int:pk>/estado/", v.categoria_estado, name="categoria_estado"),
    path("votaciones/", v.votaciones, name="votaciones"),
    path("votaciones/nueva/", v.votacion_form, name="votacion_nueva"),
    path("votaciones/<int:pk>/editar/", v.votacion_form, name="votacion_editar"),
    path("votaciones/<int:pk>/publicar/", v.votacion_publicar, name="votacion_publicar"),
    path("votaciones/<int:pk>/cerrar/", v.votacion_cerrar, name="votacion_cerrar"),
    path("votaciones/<int:pk>/opciones/", v.opciones, name="opciones"),
    path("opciones/<int:pk>/editar/", v.opcion_editar, name="opcion_editar"),
    path("opciones/<int:pk>/estado/", v.opcion_estado, name="opcion_estado"),
    path("opciones/<int:pk>/eliminar/", v.opcion_eliminar, name="opcion_eliminar"),
    path("jurados/", v.jurados, name="jurados"),
    path("resultados/", v.resultados, name="resultados"),
    path("resultados/<int:pk>/", v.resultados, name="resultados_votacion"),
    path("resultados/<int:pk>/csv/", v.resultados_csv, name="resultados_csv"),
    path("auditoria/", v.auditoria, name="auditoria"),
]
