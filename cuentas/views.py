from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from auditoria.servicios import registrar
from votaciones.models import Categoria, Edicion, Voto

from . import intentos
from .forms import IngresoForm, NuevaContrasenaForm, RecuperarForm, RegistroForm


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
    """Participación del votante (Entrega 3 · CP-07): categorías votadas y pendientes de la edición activa."""
    votos = Voto.objects.filter(usuario=request.user).select_related("opcion", "votacion", "categoria", "edicion")
    edicion = Edicion.actual()
    votadas = {v.categoria_id: v for v in votos if edicion and v.edicion_id == edicion.pk}
    filas = []
    if edicion:
        for c in Categoria.objects.filter(edicion=edicion, activa=True).order_by("orden", "nombre"):
            filas.append({"categoria": c, "voto": votadas.get(c.pk)})
    return render(request, "cuentas/mis_votos.html", {
        "votos": votos, "edicion": edicion, "filas": filas,
        "n_votadas": len(votadas), "n_categorias": len(filas),
    })


def csrf_fallo(request, reason=""):
    """Formulario sin token CSRF válido (falta, expiró o viene de otro sitio): no se procesa nada."""
    registrar(request, "csrf_rechazado", f"{request.method} {request.path} · {reason}"[:250])
    return render(request, "403_csrf.html", {"motivo": reason}, status=403)


# --- ¿Olvidaste tu contraseña? (RF-02) ---------------------------------------------------------
# Se usan las vistas de Django, que ya traen la seguridad: el enlace lleva un código que vence en
# 1 hora (PASSWORD_RESET_TIMEOUT), sirve una sola vez y no revela si el correo está registrado.

class RecuperarContrasena(auth_views.PasswordResetView):
    template_name = "cuentas/recuperar.html"
    form_class = RecuperarForm
    email_template_name = "cuentas/correo_recuperar.txt"
    html_email_template_name = "cuentas/correo_recuperar.html"
    subject_template_name = "cuentas/correo_recuperar_asunto.txt"
    success_url = reverse_lazy("cuentas:recuperar_enviado")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        correo = form.cleaned_data["email"].strip().lower()
        registrar(self.request, "recuperacion_solicitada", correo)
        if form.envio_fallido:
            # Queda para el administrador; a la persona se le muestra la pantalla de siempre
            registrar(self.request, "correo_fallido", f"No se pudo enviar la recuperación a {correo}")
        return respuesta


class RecuperarEnviado(auth_views.PasswordResetDoneView):
    template_name = "cuentas/recuperar_enviado.html"


class NuevaContrasena(auth_views.PasswordResetConfirmView):
    template_name = "cuentas/recuperar_nueva.html"
    form_class = NuevaContrasenaForm
    success_url = reverse_lazy("cuentas:recuperar_listo")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        intentos.limpiar(form.user.email)          # si estaba bloqueado por intentos fallidos, se desbloquea
        registrar(self.request, "contrasena_restablecida", form.user.email, usuario=form.user)
        return respuesta


class ContrasenaCambiada(auth_views.PasswordResetCompleteView):
    template_name = "cuentas/recuperar_listo.html"
