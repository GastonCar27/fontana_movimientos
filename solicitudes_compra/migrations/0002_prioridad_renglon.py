# Generado a mano (sin acceso a `manage.py makemigrations` en este entorno),
# siguiendo el mismo estilo que 0001_initial.py:
#   * AlterField: renombra el verbose_name de unidad_medida ("Formato" ->
#     "U. de Medida"). No cambia tipo/columna, así que es un no-op a nivel
#     de datos existentes.
#   * AddField: agrega 'prioridad' (Urgente/Media/Baja, default 'media') a
#     cada renglón de una solicitud de compra.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("solicitudes_compra", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solicitudcomprarenglon",
            name="unidad_medida",
            field=models.CharField(
                blank=True,
                default="Unidad",
                max_length=45,
                verbose_name="U. de Medida",
            ),
        ),
        migrations.AddField(
            model_name="solicitudcomprarenglon",
            name="prioridad",
            field=models.CharField(
                choices=[
                    ("urgente", "Urgente"),
                    ("media", "Media"),
                    ("baja", "Baja"),
                ],
                default="media",
                max_length=10,
                verbose_name="Prioridad",
            ),
        ),
    ]
