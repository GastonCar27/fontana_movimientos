# Escrita a mano (02/10/2026): tablas nuevas para los certificados de no
# aplicación de INYM y su vínculo con las retenciones INYM. No toca
# `retencion_inym` (legacy, managed=False). Ver models.py.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retenciones_inym', '0004_retencioninym_fechas_agregado_modificado'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificadoNoAplicacionInym',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('numero', models.IntegerField(unique=True)),
                ('id_operador_emisor', models.IntegerField(blank=True, null=True)),
                ('cuit_emisor', models.CharField(blank=True, default='', max_length=20)),
                ('tipo_oper_emisor', models.CharField(blank=True, default='', max_length=100)),
                ('fecha', models.DateField(blank=True, null=True)),
                ('periodo', models.DateField(blank=True, null=True)),
                ('vencimiento', models.DateField(blank=True, null=True)),
                ('total', models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ('tipo', models.CharField(blank=True, default='', max_length=150)),
                ('tarifa', models.DecimalField(blank=True, decimal_places=6, max_digits=20, null=True)),
                ('kgs', models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ('id_operador_valida', models.IntegerField(blank=True, null=True)),
                ('tipo_oper_valida', models.CharField(blank=True, default='', max_length=100)),
                ('nombre_valida', models.CharField(blank=True, default='', max_length=200)),
                ('fecha_validacion', models.DateField(blank=True, null=True)),
                ('fecha_eliminacion', models.DateField(blank=True, null=True)),
                ('agregado_desde', models.CharField(blank=True, default='', max_length=45)),
                ('fecha_agregado', models.DateTimeField(auto_now_add=True)),
                ('fecha_modificado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'certificado_no_aplicacion_inym',
                'ordering': ['-fecha', '-numero'],
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='RetencionInymNoAplicacionVinculo',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('importe', models.DecimalField(decimal_places=2, max_digits=20)),
                ('agregado_desde', models.CharField(blank=True, default='', max_length=45)),
                ('fecha_agregado', models.DateTimeField(auto_now_add=True)),
                ('certificado', models.ForeignKey(
                    db_column='id_certificado',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='aplicaciones',
                    to='retenciones_inym.certificadonoaplicacioninym',
                )),
                ('retencion', models.ForeignKey(
                    db_column='id_retencion_inym',
                    db_constraint=False,
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='no_aplicaciones',
                    to='retenciones_inym.retencioninym',
                )),
            ],
            options={
                'db_table': 'retencion_inym_cert_no_aplicacion',
                'managed': True,
                'constraints': [
                    models.UniqueConstraint(fields=('retencion', 'certificado'), name='unico_retencion_cert_no_aplicacion'),
                ],
            },
        ),
    ]
