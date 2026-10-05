import re

from django.db import migrations


def cargar(apps, schema_editor):
    """Carga inicial de renglones por hoja (pedido de Gastón, 05/10/2026):
      - último libro del Nación: 25
      - último libro del Macro: 35
      - libro 2 del Macro: 25
    Busca los bancos por nombre ('nacion'/'nación' y 'macro'). Si algo no
    se puede identificar sin ambigüedad, NO lo toca y lo avisa por consola:
    en ese caso se completa a mano en el admin (Libros de caja).

    Se hace con SQL directo (y no con apps.get_model) porque en el estado
    histórico de las migraciones LibroCaja no tiene registrado el FK a la
    caja (las tablas son unmanaged y nunca se migró ese campo)."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('SELECT id, nombre FROM bancocuenta')
        cajas = cursor.fetchall()

        def cajas_con(*textos):
            return [c for c in cajas if any(t in (c[1] or '').lower() for t in textos)]

        def libros_de(caja_id):
            # Orden = mismo criterio que views._ultimo_libro_de_caja: el
            # primero es el último libro (fecha_creacion más reciente,
            # nulos al final, id como desempate).
            cursor.execute(
                'SELECT id, nombre FROM banco_cuenta_libro WHERE id_bancocuenta = %s '
                'ORDER BY fecha_creacion IS NULL, fecha_creacion DESC, id DESC',
                [caja_id],
            )
            return cursor.fetchall()

        def poner(libro, cantidad, descripcion):
            cursor.execute(
                'UPDATE banco_cuenta_libro SET cantidad_renglones = %s WHERE id = %s', [cantidad, libro[0]],
            )
            print(f'\n  {descripcion}: libro {libro[0]} "{libro[1]}" -> {cantidad} renglones')

        nacion = cajas_con('nacion', 'nación')
        if len(nacion) == 1:
            libros = libros_de(nacion[0][0])
            if libros:
                poner(libros[0], 25, 'Nación (último libro)')
        else:
            print(f'\n  AVISO: no se identificó un único banco Nación ({len(nacion)} encontrados); completarlo en el admin.')

        macro = cajas_con('macro')
        if len(macro) == 1:
            libros = libros_de(macro[0][0])
            if libros:
                ultimo = libros[0]
                libros_2 = [l for l in libros[1:] if re.search(r'(^|\D)2(\D|$)', l[1] or '')]
                if len(libros_2) == 1:
                    poner(libros_2[0], 25, 'Macro (libro 2)')
                else:
                    print(f'\n  AVISO: no se identificó un único "libro 2" del Macro ({len(libros_2)} encontrados); completarlo en el admin.')
                poner(ultimo, 35, 'Macro (último libro)')
        else:
            print(f'\n  AVISO: no se identificó un único banco Macro ({len(macro)} encontrados); completarlo en el admin.')


class Migration(migrations.Migration):

    dependencies = [
        ('movimientos_caja', '0004_libro_cantidad_renglones'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
