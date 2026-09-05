from django.db import migrations
from django.utils.text import slugify

# Tipos de entidad iniciales pedidos. Se puede seguir agregando más después
# (por ahora, desde /admin/ -> Entidades -> Roles; el nombre en el admin es
# "Roles" por el modelo, pero de cara al usuario son "tipos de entidad").
TIPOS_INICIALES = [
    'Transportista',
    'Chofer de Transporte',
    'Productor de H.V. de Té',
]


def crear_tipos(apps, schema_editor):
    Rol = apps.get_model('entidades', 'Rol')
    for nombre in TIPOS_INICIALES:
        Rol.objects.get_or_create(nombre=nombre, defaults={'slug': slugify(nombre)})


def eliminar_tipos(apps, schema_editor):
    Rol = apps.get_model('entidades', 'Rol')
    Rol.objects.filter(nombre__in=TIPOS_INICIALES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0005_rol_entidades'),
    ]

    operations = [
        migrations.RunPython(crear_tipos, eliminar_tipos),
    ]
