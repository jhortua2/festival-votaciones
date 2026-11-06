"""Formulario del voto (Entrega 3).

Se envía por POST con token CSRF desde la pantalla de confirmación. El campo `opcion`
solo acepta opciones de la votación que se está mostrando: si alguien manipula el
formulario y manda una opción de otra votación o categoría, el formulario no es válido (CP-06).
Las demás reglas (votación abierta, un voto por categoría y edición) se validan en
`servicios.emitir_voto` y en la base de datos.
"""
from django import forms

from .models import Opcion


class VotoForm(forms.Form):
    opcion = forms.ModelChoiceField(
        queryset=Opcion.objects.none(),
        error_messages={
            "required": "Elige una opción antes de votar.",
            "invalid_choice": "La opción enviada no pertenece a esta votación ni a su categoría.",
        },
    )
    confirmado = forms.BooleanField(
        required=False,
        error_messages={"required": "Debes confirmar tu voto."},
    )

    def __init__(self, votacion, *args, exigir_confirmacion=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.votacion = votacion
        self.fields["opcion"].queryset = Opcion.objects.filter(votacion=votacion)
        self.fields["confirmado"].required = exigir_confirmacion
