from django.db import migrations, models


def backfill_productos_genericos(apps, schema_editor):
    """Completa ProductoGenerico con las descripciones que ya estaban
    cargadas en renglones de Solicitud de Compra antes de que existiera
    este catálogo, para no obligar a Gastón a volver a tipearlas para que
    aparezcan en el autocompletado. Deduplica sin importar mayúsculas
    (se queda con la primera variante que encuentra, por id de renglón)."""
    SolicitudCompraRenglon = apps.get_model('solicitudes_compra', 'SolicitudCompraRenglon')
    ProductoGenerico = apps.get_model('solicitudes_compra', 'ProductoGenerico')

    vistos = {}  # nombre en minúsculas -> nombre tal cual se guardó primero
    descripciones = (
        SolicitudCompraRenglon.objects
        .exclude(descripcion__isnull=True)
        .exclude(descripcion='')
        .order_by('id')
        .values_list('descripcion', flat=True)
    )
    for descripcion in descripciones:
        texto = descripcion.strip()
        if not texto:
            continue
        clave = texto.lower()
        if clave not in vistos:
            vistos[clave] = texto

    ProductoGenerico.objects.bulk_create(
        [ProductoGenerico(nombre=nombre) for nombre in vistos.values()],
        ignore_conflicts=True,
    )


def no_revertir(apps, schema_editor):
    # No se borra nada al revertir: no se puede distinguir con certeza qué
    # filas vinieron del backfill de cuáles se cargaron después a mano
    # (mismo criterio, inofensivo, que ya se usa en otras migraciones de
    # datos de este proyecto).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes_compra', '0005_alter_solicitudcompra_responsable_retiro_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductoGenerico',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=255, unique=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'solicitud_compra_producto_generico',
                'ordering': ['nombre'],
            },
        ),
        migrations.RunPython(backfill_productos_genericos, no_revertir),
    ]
