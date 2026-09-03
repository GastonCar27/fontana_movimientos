# Data migration: crea los grupos (roles) que usa el menú de navegación
# (ver navbar.html y fontana_movimientos/context_processors.py,
# permisos_menu) para mostrarle a cada usuario solo las secciones que le
# corresponden.
#
# "Administrador" ve todas las secciones restringidas (además de que
# cualquier superusuario de Django siempre ve todo, tenga o no este grupo
# asignado). El resto de los grupos corresponden cada uno a una sección
# puntual del menú. "Ingreso", "Salida" y "Reportes" no tienen grupo:
# quedan visibles para cualquier usuario logueado.
#
# Se asignan usuarios a estos grupos desde /admin/, en la ficha de cada
# usuario, campo "Groups" — no hace falta tocar código para eso.

from django.db import migrations

GRUPOS = [
    'Administrador',
    'Movimientos de Productos',
    'Movimientos de Caja',
    'Comprobantes',
    'Liquidaciones',
    'Retenciones',
    'Tipos',
    'Solicitudes de Compra',
    'Empleados',
    'Otros',
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
        ('entidades', '0001_initial'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, eliminar_grupos),
    ]
