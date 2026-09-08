from django.db import migrations

# Unidades que no vienen del padrón de AFIP (comprobante_unidad_de_medida es
# la tabla legada con los códigos oficiales), agregadas a pedido para poder
# usarlas en el renglón de Remito (remitos.models.RemitoRenglon.unidad_de_medida
# apunta a esta misma tabla, igual que Movimiento.unidad_de_medida -- ver
# remitos.views._sincronizar_movimiento_renglon). Se usan ids con letras
# (en vez de números) a propósito, para que nunca puedan llegar a coincidir
# con un código numérico real de AFIP.
#
# OJO: estos dos ids se excluyen a propósito del desplegable de unidad de
# medida de ComprobanteRenglonDetalle (ver comprobantes.forms y
# comprobantes.models.IDS_UNIDADES_SOLO_REMITOS) para que nunca terminen
# usadas en un comprobante fiscal real. Si se cambian estos ids acá, hay que
# actualizar esa lista también.
UNIDADES_SOLO_REMITOS = [
    ('BN', 'Bolsón'),
    ('BS', 'Bolsa'),
]


def crear_unidades(apps, schema_editor):
    ComprobanteUnidadDeMedida = apps.get_model('comprobantes', 'ComprobanteUnidadDeMedida')
    for id_unidad, nombre in UNIDADES_SOLO_REMITOS:
        ComprobanteUnidadDeMedida.objects.get_or_create(id=id_unidad, defaults={'nombre': nombre})


def eliminar_unidades(apps, schema_editor):
    ComprobanteUnidadDeMedida = apps.get_model('comprobantes', 'ComprobanteUnidadDeMedida')
    ComprobanteUnidadDeMedida.objects.filter(
        id__in=[id_unidad for id_unidad, _nombre in UNIDADES_SOLO_REMITOS],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('comprobantes', '0002_comprobantetipodecambio'),
    ]

    operations = [
        migrations.RunPython(crear_unidades, eliminar_unidades),
    ]
