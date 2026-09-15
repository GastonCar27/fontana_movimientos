# Generado a mano (no con makemigrations) el 2026-09-15.
#
# Como RetencionInym tiene managed=False, esta migración SOLO actualiza el
# estado interno de Django (para que el ORM sepa que el campo existe) -- NO
# ejecuta ningún ALTER TABLE real. La columna hay que crearla a mano en MySQL
# con sql/2026-09-15_agregar_id_certificado_inym.sql, en cada base (primero en
# la de pruebas, después en producción) ANTES de correr `migrate` con esta
# migración -- si no, el ORM va a intentar leer/escribir una columna que
# todavía no existe y va a fallar.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retenciones_inym', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='retencioninym',
            name='id_certificado_inym',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
