# Data migration: elimina el grupo "Empleados" del menú de navegación (ver
# navbar.html y fontana_movimientos/context_processors.py, permisos_menu),
# que quedó sin uso porque la app 'empleados' se decomisiona: ahora los
# empleados se gestionan como Entidad con los roles creados en
# 0009_seed_tipos_entidad_empleado.py, dentro del menú de Entidades (que ya
# usa el grupo "Entidades" para sus permisos).
#
# No se borra ningún usuario ni se les cambia el grupo asignado en otras
# secciones: sólo se elimina esta fila de auth_group, que ya no gatea nada
# en el código (se quita puede_ver_empleados de permisos_menu en el mismo
# cambio). Si algún usuario tenía sólo este grupo asignado, simplemente deja
# de tener un grupo -- se le puede asignar "Entidades" desde /admin/ si
# corresponde que vea esa sección.

from django.db import migrations

GRUPOS = ['Empleados']


def eliminar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=GRUPOS).delete()


def recrear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in GRUPOS:
        Group.objects.get_or_create(name=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0009_seed_tipos_entidad_empleado'),
    ]

    operations = [
        migrations.RunPython(eliminar_grupos, recrear_grupos),
    ]
