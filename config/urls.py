from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),  # Admin técnico de Django (solo superusuarios)
    path("cuentas/", include("cuentas.urls")),
    path("panel/", include("votaciones.urls_panel")),  # Panel de administración de la Fundación
    path("", include("votaciones.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
