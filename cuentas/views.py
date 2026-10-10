from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from auditoria.servicios import registrar
from votaciones.models import Voto

from .forms import IngresoForm, RegistroForm


def registro(request):
    if request.user.is_authenticated:
        return redirect("votaciones:inicio")
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        login(request, usuario)
        registrar(request, "registro", f"Nueva cuenta de votante: {usuario.email}")
        messages.success(request, "Cuenta creada. ¡Ya puedes votar!")
        return redirect(request.GET.get("next") or "votaciones:inicio")
    return render(request, "cuentas/registro.html", {"form": form})


class Ingreso(auth_views.LoginView):
    template_name = "cuentas/login.html"
    authentication_form = IngresoForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        registrar(self.request, "inicio_sesion", self.request.user.email)
        return respuesta

    def get_success_url(self):
        destino = self.get_redirect_url()
        if destino:
            return destino
        if self.request.user.es_admin:
            return "/panel/"
        if self.request.user.es_jurado:
            return "/jurado/"
        return "/"


@login_required
def mis_votos(request):
    votos = Voto.objects.filter(usuario=request.user).select_related("opcion", "votacion__categoria")
    return render(request, "cuentas/mis_votos.html", {"votos": votos})
