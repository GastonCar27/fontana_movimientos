# Generado a mano (sin acceso a `manage.py makemigrations` en este entorno),
# siguiendo el mismo estilo que las migraciones anteriores de esta app.
# Agrega 'creado_por' a SolicitudCompra: qué usuario (login de Django) creó
# la solicitud. 'creado' (fecha/hora de alta) y 'modificado' (fecha/hora de
# la última edición) ya existían desde 0001_initial, con auto_now_add /
# auto_now respectivamente — no hace falta tocarlos.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("solicitudes_compra", "0003_renglon_sector"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudcompra",
            name="creado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="solicitudes_compra_creadas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Creado por",
            ),
        ),
    ]
