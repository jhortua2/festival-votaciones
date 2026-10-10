from django import forms
from django.conf import settings

from .models import Categoria, Opcion, Votacion


class _Estilo:
    """Aplica clases de Bootstrap a todos los campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            w = campo.widget
            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, forms.Select):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")


class CategoriaForm(_Estilo, forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion", "orden", "icono", "color"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, edicion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.edicion = edicion or getattr(self.instance, "edicion", None)
        self.fields["color"].widget.attrs["class"] = "form-control form-control-color"

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        repetida = Categoria.objects.filter(edicion=self.edicion, nombre__iexact=nombre).exclude(pk=self.instance.pk)
        if repetida.exists():
            raise forms.ValidationError("Ya existe una categoría con ese nombre en esta edición.")
        return nombre


class VotacionForm(_Estilo, forms.ModelForm):
    class Meta:
        model = Votacion
        fields = ["categoria", "nombre", "descripcion", "apertura", "cierre", "frecuencia", "visibilidad",
                  "peso_jurado", "escala_maxima", "jurados"]
        widgets = {
            "peso_jurado": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 5}),
            "escala_maxima": forms.NumberInput(attrs={"min": 2, "max": 100}),
            "jurados": forms.CheckboxSelectMultiple,
            "apertura": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "cierre": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "frecuencia": "Pendiente de validación con el cliente (RN-06 / P-03).",
            "visibilidad": "Pendiente de validación con el cliente (RN-10 / P-05).",
            "peso_jurado": "0 = solo público · 100 = solo jurado. Propuesta 70 (jurado 70 % + público 30 %), pendiente de validación (RN-11 / P-06).",
            "jurados": "Solo los jurados marcados pueden calificar esta votación (RN-13). Se crean en «Jurados».",
        }

    def __init__(self, *args, edicion=None, **kwargs):
        super().__init__(*args, **kwargs)
        if edicion:
            self.fields["categoria"].queryset = Categoria.objects.filter(edicion=edicion)
        for f in ("apertura", "cierre"):
            self.fields[f].input_formats = ["%Y-%m-%dT%H:%M"]
        if self.instance.pk and (self.instance.votos.exists() or self.instance.calificaciones.exists()):
            # Con votos o calificaciones no se cambian las reglas del juego
            for f in ("frecuencia", "categoria", "apertura", "peso_jurado", "escala_maxima"):
                self.fields[f].disabled = True


class JuradoForm(_Estilo, forms.Form):
    """Crea una cuenta con rol de jurado (la Fundación entrega la contraseña al jurado)."""
    first_name = forms.CharField(label="Nombres", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150, required=False)
    email = forms.EmailField(label="Correo electrónico")
    password = forms.CharField(label="Contraseña inicial", min_length=8, widget=forms.PasswordInput(render_value=False))

    def clean_email(self):
        from cuentas.models import Usuario
        email = self.cleaned_data["email"].lower().strip()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo.")
        return email


class OpcionForm(_Estilo, forms.ModelForm):
    class Meta:
        model = Opcion
        fields = ["nombre", "detalle", "descripcion", "imagen", "color", "orden"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 2}), "color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].widget.attrs["class"] = "form-control form-control-color"
        self.fields["imagen"].help_text = f"JPG, PNG o WEBP · máximo {settings.MAX_IMAGEN_OPCION_MB} MB (propuesto)."

    def clean_imagen(self):
        img = self.cleaned_data.get("imagen")
        if img and hasattr(img, "size") and img.size > settings.MAX_IMAGEN_OPCION_MB * 1024 * 1024:
            raise forms.ValidationError(f"La imagen supera {settings.MAX_IMAGEN_OPCION_MB} MB.")
        return img


class JustificacionForm(forms.Form):
    justificacion = forms.CharField(
        label="Justificación", max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Explica por qué (queda en auditoría)"}),
        error_messages={"required": "La justificación es obligatoria."},
    )
