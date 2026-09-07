# Data migration: crea el grupo "Entidades" del menú de navegación (ver
# navbar.html y fontana_movimientos/context_processors.py, permisos_menu),
# para la nueva sección propia de Alta/Modificación/Reportes de Entidad y
# de Alta/Modificación/Listado de tipos de entidad (antes vivían sueltas
# dentro de "Otros"). Mismo patrón que 0002_grupos_menu.py.

from django.db import migrations

GRUPOS = ['Entidades']


def crear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in GRUPOS:
        Group.objects.get_or_create(name=nombre)


def eliminar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=GRUPOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0006_seed_tipos_entidad'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, eliminar_grupos),
    ]
