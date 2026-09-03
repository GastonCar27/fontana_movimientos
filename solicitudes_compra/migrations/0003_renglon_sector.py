# Generado a mano (sin acceso a `manage.py makemigrations` en este entorno),
# siguiendo el mismo estilo que las migraciones anteriores de esta app.
# Agrega 'sector' a cada renglón de una solicitud de compra, como FK
# opcional a comprobantes.SectorTipo (tabla existente sector_tipo, ya
# usada por comprobante_renglon_detalle).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("solicitudes_compra", "0002_prioridad_renglon"),
        ("comprobantes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudcomprarenglon",
            name="sector",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="renglones_solicitud_compra",
                to="comprobantes.sectortipo",
                verbose_name="Sector",
            ),
        ),
    ]
