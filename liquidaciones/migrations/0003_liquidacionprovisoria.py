# Escrita a mano (02/10/2026): crea SÓLO la tabla nueva
# liquidacion_provisoria (liquidaciones provisorias / englobadas). No toca
# la tabla legacy 'liquidacion'. Ver LiquidacionProvisoria en models.py.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('liquidaciones', '0002_liquidacion_tipo'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiquidacionProvisoria',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('fecha_marcada', models.DateTimeField(auto_now_add=True)),
                ('fecha_englobada', models.DateTimeField(blank=True, null=True)),
                ('usuario', models.CharField(blank=True, default='', max_length=150)),
                ('liquidacion', models.OneToOneField(
                    db_column='id_liquidacion',
                    db_constraint=False,
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='provisoria',
                    to='liquidaciones.liquidacion',
                )),
                ('englobada_en', models.ForeignKey(
                    blank=True,
                    db_column='id_liquidacion_definitiva',
                    db_constraint=False,
                    null=True,
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='provisorias_englobadas',
                    to='liquidaciones.liquidacion',
                )),
            ],
            options={
                'db_table': 'liquidacion_provisoria',
                'managed': True,
            },
        ),
    ]
