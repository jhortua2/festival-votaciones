"""Modo de resultado configurable (observación de la Entrega 1).

Antes, el peso del jurado definía todo (0 = solo público, 100 = solo jurado).
Ahora cada votación tiene un modo: solo público, solo jurado, independiente o combinado,
porque la Fundación todavía no decide si el voto del público se mezcla con el del jurado (P-06).
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def pasar_peso_a_modo(apps, schema_editor):
    Votacion = apps.get_model("votaciones", "Votacion")
    for v in Votacion.objects.all():
        if v.peso_jurado == 0:
            v.modo, v.peso_jurado = "publico", 70
        elif v.peso_jurado >= 100:
            v.modo, v.peso_jurado = "jurado", 70
        else:
            v.modo = "combinado"
        v.save(update_fields=["modo", "peso_jurado"])


def volver_a_peso(apps, schema_editor):
    Votacion = apps.get_model("votaciones", "Votacion")
    for v in Votacion.objects.all():
        if v.modo == "publico":
            v.peso_jurado = 0
        elif v.modo == "jurado":
            v.peso_jurado = 100
        v.save(update_fields=["peso_jurado"])


class Migration(migrations.Migration):
    dependencies = [("votaciones", "0002_jurado_y_ponderacion")]

    operations = [
        migrations.RemoveConstraint(model_name="votacion", name="peso_jurado_hasta_100"),
        migrations.AddField(
            model_name="votacion",
            name="modo",
            field=models.CharField(
                "modo de resultado", max_length=14, default="independiente",
                choices=[("publico", "Solo público"), ("jurado", "Solo jurado"),
                         ("independiente", "Independiente: fallo del jurado y premio del público por separado"),
                         ("combinado", "Combinado: jurado y público en un solo resultado")],
                help_text="Pendiente de validación (P-06). Independiente no mezcla el voto del público con el fallo del jurado.",
            ),
        ),
        migrations.RunPython(pasar_peso_a_modo, volver_a_peso),
        migrations.AlterField(
            model_name="votacion",
            name="peso_jurado",
            field=models.PositiveSmallIntegerField(
                "peso del jurado (%)", default=70, validators=[MinValueValidator(1), MaxValueValidator(99)],
                help_text="Solo en modo combinado. El público tiene el resto. Propuesta del equipo 70/30, pendiente de validación (P-06).",
            ),
        ),
        migrations.AddConstraint(
            model_name="votacion",
            constraint=models.CheckConstraint(condition=models.Q(peso_jurado__gte=1, peso_jurado__lte=99), name="peso_jurado_entre_1_y_99"),
        ),
    ]
