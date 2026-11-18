from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils import timezone

from . import intentos
from .models import Usuario


def _estilo(form):
    """Clases de Bootstrap para cada campo."""
    for campo in form.fields.values():
        if isinstance(campo.widget, forms.CheckboxInput):
            campo.widget.attrs.setdefault("class", "form-check-input")
        else:
            campo.widget.attrs.setdefault("class", "form-control")


class RegistroForm(forms.ModelForm):
    """CU-01 Registrarse. Datos mínimos (P-08 pendiente de validación)."""

    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    acepto = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales según la política de la Fundación (Ley 1581 de 2012).",
        error_messages={"required": "Debes autorizar el tratamiento de datos para crear la cuenta."},
    )

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email"]
        labels = {"first_name": "Nombres", "last_name": "Apellidos", "email": "Correo electrónico"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["email"].help_text = "Dato de identificación del votante. Pendiente de validación (P-01)."
        _estilo(self)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo. Inicia sesión.")
        return email

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if p1:
            usuario_tmp = Usuario(email=datos.get("email"), first_name=datos.get("first_name", ""))
            try:
                password_validation.validate_password(p1, usuario_tmp)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.username = self.cleaned_data["email"]
        usuario.set_password(self.cleaned_data["password1"])
        usuario.rol = Usuario.Rol.VOTANTE
        usuario.acepto_tratamiento_datos = True
        usuario.fecha_aceptacion_datos = timezone.now()
        if commit:
            usuario.save()
        return usuario


class IngresoForm(AuthenticationForm):
    """CU-02 Iniciar sesión con correo. Mensaje genérico ante errores (no revela qué dato falló)."""

    username = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}))
    error_messages = {
        "invalid_login": "Correo o contraseña incorrectos.",
        "inactive": "Esta cuenta está inactiva.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilo(self)

    def clean(self):
        correo = (self.cleaned_data.get("username") or "").lower()
        if correo and intentos.bloqueado(correo):
            raise forms.ValidationError(
                f"Demasiados intentos fallidos. Por seguridad, espera {settings.LOGIN_BLOQUEO_MINUTOS} minutos e inténtalo de nuevo.",
                code="bloqueado",
            )
        if correo:
            u = Usuario.objects.filter(email__iexact=correo).first()
            self.cleaned_data["username"] = u.username if u else correo
        try:
            datos = super().clean()
        except forms.ValidationError:
            if correo:
                intentos.fallo(correo)
            raise
        if correo:
            intentos.limpiar(correo)
        return datos


class RecuperarForm(PasswordResetForm):
    """RF-02 ¿Olvidaste tu contraseña? Pide el correo y envía un enlace para crear una nueva.

    Django no avisa si el correo existe o no (así nadie puede averiguar quién está registrado),
    y solo envía a cuentas activas.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Correo electrónico"
        self.fields["email"].help_text = "El correo con el que te registraste."
        self.fields["email"].widget.attrs["autofocus"] = True
        self.envio_fallido = False
        _estilo(self)

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email,
                  html_email_template_name=None):
        """Igual que el de Django, pero recuerda si el envío falló para dejarlo en la auditoría.

        A la persona se le muestra la misma pantalla de siempre: si se le avisara del fallo,
        sabría que ese correo sí está registrado.
        """
        asunto = "".join(loader.render_to_string(subject_template_name, context).splitlines())
        mensaje = EmailMultiAlternatives(asunto, loader.render_to_string(email_template_name, context),
                                         from_email, [to_email])
        if html_email_template_name:
            mensaje.attach_alternative(loader.render_to_string(html_email_template_name, context), "text/html")
        try:
            mensaje.send()
        except Exception:  # noqa: BLE001 - servidor caído, clave de aplicación mala, sin internet...
            self.envio_fallido = True


class NuevaContrasenaForm(SetPasswordForm):
    """RF-02 Crear la nueva contraseña desde el enlace del correo (mismas reglas que en el registro)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Repite la nueva contraseña"
        _estilo(self)
