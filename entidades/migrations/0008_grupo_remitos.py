# Data migration: crea el grupo "Remitos" del menú de navegación (ver
# navbar.html y fontana_movimientos/context_processors.py, permisos_menu),
# para la nueva sección de Alta/Modificación/Reportes de Remito y sus
# catálogos (vehículos, acoplados, condiciones de venta, observaciones
# estándar). Mismo patrón que 0002_grupos_menu.py y 0007_grupo_entidades.py.

from django.db import migrations

GRUPOS = ['Remitos']


def crear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in GRUPOS:
        Group.objects.get_or_create(name=nombre)


def eliminar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=GRUPOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0007_grupo_entidades'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, eliminar_grupos),
    ]
