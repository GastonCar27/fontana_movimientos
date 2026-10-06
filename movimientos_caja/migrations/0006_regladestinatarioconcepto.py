# Escrita a mano (2026-10-06): tabla NUEVA movimiento_caja_regla_destinatario
# (ReglaDestinatarioConcepto). No toca ninguna tabla heredada; los FK no
# crean restricciones en la base (db_constraint=False).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0010_eliminar_grupo_empleados'),
        ('movimientos_caja', '0005_cargar_cantidad_renglones_libros'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReglaDestinatarioConcepto',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('monto_maximo', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=20, null=True,
                    help_text='Opcional. Ej.: Comercio exterior sólo si es menor a 100.000.',
                    verbose_name='Sólo si el monto es menor a')),
                ('activa', models.BooleanField(default=True)),
                ('caja', models.ForeignKey(
                    db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='reglas_destinatario', to='movimientos_caja.caja',
                    verbose_name='Cuenta (banco / caja)')),
                ('concepto', models.ForeignKey(
                    db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='reglas_destinatario', to='movimientos_caja.movimientocajaconceptotipo',
                    verbose_name='Concepto')),
                ('entidad', models.ForeignKey(
                    db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='reglas_destinatario_caja', to='entidades.entidad',
                    verbose_name='Destinatario')),
            ],
            options={
                'verbose_name': 'regla de destinatario por concepto',
                'verbose_name_plural': 'reglas de destinatario por concepto',
                'db_table': 'movimiento_caja_regla_destinatario',
            },
        ),
        migrations.AddConstraint(
            model_name='regladestinatarioconcepto',
            constraint=models.UniqueConstraint(fields=('caja', 'concepto'), name='regla_destinatario_unica_caja_concepto'),
        ),
    ]
