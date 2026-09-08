import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('comprobantes', '0003_seed_unidades_remitos'),
        ('entidades', '0008_grupo_remitos'),
        ('movimientos', '0002_delete_comprobanteunidaddemedida_and_more'),
        ('productos', '0002_itemtipo'),
    ]

    operations = [
        migrations.CreateModel(
            name='EstadoCuentaMovimiento',
            fields=[
                ('movimiento', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='estado_cuenta', serialize=False, to='movimientos.movimiento')),
                ('estado', models.CharField(choices=[('abierto', 'Abierto'), ('cerrado', 'Cerrado')], default='abierto', max_length=10)),
                ('cerrado_el', models.DateTimeField(blank=True, null=True)),
                ('observaciones', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'estado de cuenta de movimiento',
                'verbose_name_plural': 'estados de cuenta de movimientos',
                'db_table': 'cta_cte_estado_movimiento',
            },
        ),
        migrations.CreateModel(
            name='LiquidacionProducto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(blank=True, max_length=145)),
                ('fecha', models.DateField()),
                ('debe_pesos', models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ('haber_pesos', models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ('observaciones', models.TextField(blank=True)),
                ('guardado_el', models.DateTimeField(auto_now_add=True)),
                ('modificado_el', models.DateTimeField(auto_now=True, verbose_name='fecha de edición')),
                ('entidad', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='liquidaciones_producto', to='entidades.entidad')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='liquidaciones_producto', to='productos.productodetalle')),
            ],
            options={
                'verbose_name': 'liquidación de producto',
                'verbose_name_plural': 'liquidaciones de producto',
                'db_table': 'cta_cte_liquidacion_producto',
                'ordering': ['-fecha', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ComprobanteRenglonMovimiento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('observaciones', models.CharField(blank=True, max_length=255)),
                ('guardado_el', models.DateTimeField(auto_now_add=True)),
                ('movimiento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vinculos_comprobante', to='movimientos.movimiento')),
                ('renglon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vinculos_movimiento', to='comprobantes.comprobanterenglon')),
            ],
            options={
                'verbose_name': 'vínculo renglón-movimiento',
                'verbose_name_plural': 'vínculos renglón-movimiento',
                'db_table': 'cta_cte_comprobante_renglon_movimiento',
                'ordering': ['-guardado_el'],
            },
        ),
        migrations.CreateModel(
            name='LiquidacionProductoComprobanteRenglon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('debe', 'Debe'), ('haber', 'Haber')], max_length=10)),
                ('liquidacion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='renglones', to='cuenta_corriente_productos.liquidacionproducto')),
                ('renglon', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='liquidacion_producto', to='comprobantes.comprobanterenglon')),
            ],
            options={
                'verbose_name': 'renglón de liquidación de producto',
                'verbose_name_plural': 'renglones de liquidación de producto',
                'db_table': 'cta_cte_liquidacion_producto_comprobante_renglon',
            },
        ),
        migrations.AddConstraint(
            model_name='comprobanterenglonmovimiento',
            constraint=models.UniqueConstraint(fields=('renglon', 'movimiento'), name='cta_cte_renglon_movimiento_unico'),
        ),
    ]
