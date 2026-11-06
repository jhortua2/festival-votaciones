"""Entrega 3 · un voto por usuario, categoría y edición (RN-06, regla del cliente).

1. Agrega `edicion` y `categoria` al voto y las llena a partir de la votación.
2. Si ya existían dos o más votos del mismo usuario en la misma categoría y edición
   (permitidos por la regla anterior, que era por votación), se conserva el primero.
3. Crea la restricción única (usuario, categoría, edición) en MySQL y quita la anterior.
4. Quita la frecuencia de voto por votación, que ya no aplica.
"""
import django.db.models.deletion
from django.db import migrations, models


def llenar_categoria_y_edicion(apps, schema_editor):
    Voto = apps.get_model("votaciones", "Voto")
    vistos = set()
    sobrantes = []
    for voto in Voto.objects.select_related("votacion__categoria").order_by("fecha", "id"):
        categoria = voto.votacion.categoria
        clave = (voto.usuario_id, categoria.id, categoria.edicion_id)
        if clave in vistos:
            sobrantes.append(voto.id)
            continue
        vistos.add(clave)
        Voto.objects.filter(pk=voto.pk).update(categoria_id=categoria.id, edicion_id=categoria.edicion_id)
    if sobrantes:
        Voto.objects.filter(pk__in=sobrantes).delete()
        print(f"\n  Se quitaron {len(sobrantes)} voto(s) repetidos en la misma categoría (regla nueva de la Entrega 3).")


class Migration(migrations.Migration):

    dependencies = [
        ("votaciones", "0003_modo_resultado"),
    ]

    operations = [
        migrations.AddField(
            model_name="voto",
            name="edicion",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="votaciones.edicion", verbose_name="edición"),
        ),
        migrations.AddField(
            model_name="voto",
            name="categoria",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="votaciones.categoria", verbose_name="categoría"),
        ),
        migrations.RunPython(llenar_categoria_y_edicion, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="voto",
            name="edicion",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="votaciones.edicion", verbose_name="edición"),
        ),
        migrations.AlterField(
            model_name="voto",
            name="categoria",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="votaciones.categoria", verbose_name="categoría"),
        ),
        migrations.AlterField(
            model_name="voto",
            name="votacion",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="votaciones.votacion", verbose_name="votación"),
        ),
        migrations.AlterField(
            model_name="voto",
            name="opcion",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="votos",
                                    to="votaciones.opcion", verbose_name="opción"),
        ),
        # Primero la restricción nueva (empieza por usuario, así la llave foránea de MySQL
        # sigue teniendo un índice) y luego se quita la anterior.
        migrations.AddConstraint(
            model_name="voto",
            constraint=models.UniqueConstraint(fields=("usuario", "categoria", "edicion"),
                                               name="un_voto_por_usuario_categoria_edicion"),
        ),
        migrations.RemoveConstraint(model_name="voto", name="un_voto_segun_frecuencia"),
        migrations.RemoveField(model_name="voto", name="clave_frecuencia"),
        migrations.RemoveField(model_name="votacion", name="frecuencia"),
    ]
