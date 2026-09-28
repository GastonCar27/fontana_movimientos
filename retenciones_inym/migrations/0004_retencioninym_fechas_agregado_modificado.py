# Generated manually (sin acceso a `manage.py makemigrations` en este
# entorno) -- Gastón corre `python manage.py makemigrations retenciones_inym`
# él mismo para confirmar que coincide exactamente con esto, y después
# `python manage.py migrate` (managed=False: esto sólo actualiza el estado
# del ORM, la columna real se agrega con
# sql/2026-09-28_agregar_fechas_retencion_inym.sql, ANTES de correr migrate).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retenciones_inym', '0003_retencioninymhistorico'),
    ]

    operations = [
        migrations.AddField(
            model_name='retencioninym',
            name='fecha_agregado',
            field=models.DateTimeField(auto_now_add=True, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='retencioninym',
            name='fecha_modificado',
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
    ]
