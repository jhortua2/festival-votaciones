from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

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
        correo = self.cleaned_data.get("username")
        if correo:
            u = Usuario.objects.filter(email__iexact=correo).first()
            self.cleaned_data["username"] = u.username if u else correo
        return super().clean()
