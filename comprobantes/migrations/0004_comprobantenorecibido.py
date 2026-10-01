# Escrita a mano (2026-10-01): sólo crea la tabla nueva comprobante_no_recibido
# (ver comprobantes.models.ComprobanteNoRecibido). No toca ninguna tabla legada.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comprobantes', '0003_seed_unidades_remitos'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComprobanteNoRecibido',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('fecha_marcado', models.DateTimeField(auto_now_add=True, verbose_name='Marcado el')),
                ('motivo', models.CharField(blank=True, max_length=255, verbose_name='Motivo')),
                ('usuario', models.CharField(blank=True, max_length=150, verbose_name='Marcado por')),
                ('comprobante', models.OneToOneField(
                    db_constraint=False,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='no_recibido',
                    to='comprobantes.comprobante',
                )),
            ],
            options={
                'verbose_name': 'comprobante no recibido',
                'verbose_name_plural': 'comprobantes no recibidos',
                'db_table': 'comprobante_no_recibido',
                'managed': True,
            },
        ),
    ]
