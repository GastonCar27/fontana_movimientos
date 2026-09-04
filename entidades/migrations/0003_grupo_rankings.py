# Data migration: crea el grupo (rol) "Rankings" que usa el menú de
# navegación (ver navbar.html y fontana_movimientos/context_processors.py,
# permisos_menu / GRUPOS_MENU) para la nueva sección "Rankings" del menú.
#
# Igual que el resto de los grupos de 0002_grupos_menu.py: un superusuario,
# o quien esté en el grupo "Administrador", ve la sección sin necesidad de
# estar además en este grupo puntual. Por ahora no se asigna a ningún
# usuario, así que solo el administrador la ve — se asigna desde /admin/,
# en la ficha del usuario, campo "Groups", el día que se quiera dar acceso
# a alguien más.

from django.db import migrations

GRUPOS = [
    'Rankings',
]


def crear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in GRUPOS:
        Group.objects.get_or_create(name=nombre)


def eliminar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=GRUPOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0002_grupos_menu'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, eliminar_grupos),
    ]
