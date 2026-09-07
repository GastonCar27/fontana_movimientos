# Data migration: precarga las condiciones de venta iniciales pedidas,
# además de lo que ya figura en el remito de ejemplo. Se puede seguir
# agregando más con el tiempo desde su propia pantalla de Alta
# (remitos:condicion_venta_alta), no hace falta tocar código para eso.

from django.db import migrations

CONDICIONES_INICIALES = [
    'Consignado Exportación',
    'Contado',
    'Transferencia a 30 días',
    'Cheque',
    'Cuenta Corriente',
]


def crear_condiciones(apps, schema_editor):
    CondicionVenta = apps.get_model('remitos', 'CondicionVenta')
    for nombre in CONDICIONES_INICIALES:
        CondicionVenta.objects.get_or_create(nombre=nombre)


def eliminar_condiciones(apps, schema_editor):
    CondicionVenta = apps.get_model('remitos', 'CondicionVenta')
    CondicionVenta.objects.filter(nombre__in=CONDICIONES_INICIALES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('remitos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_condiciones, eliminar_condiciones),
    ]
