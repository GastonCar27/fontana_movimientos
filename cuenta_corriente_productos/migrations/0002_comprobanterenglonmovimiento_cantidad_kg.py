from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cuenta_corriente_productos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='comprobanterenglonmovimiento',
            name='cantidad_kg',
            field=models.DecimalField(
                blank=True, null=True, max_digits=14, decimal_places=2,
                verbose_name='cantidad (Kg u otra unidad) cubierta por este vínculo',
            ),
        ),
    ]
