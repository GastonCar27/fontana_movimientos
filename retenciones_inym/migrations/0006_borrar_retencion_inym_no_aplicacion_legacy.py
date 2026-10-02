# Escrita a mano (02/10/2026, pedido de Gastón): la tabla legacy
# `retencion_inym_no_aplicacion` quedó reemplazada por
# certificado_no_aplicacion_inym + retencion_inym_cert_no_aplicacion (0005).
#
# Se borra de la base SÓLO si:
#   - está vacía (0 filas), y
#   - ninguna otra tabla tiene una clave foránea que la referencie.
# Si no se cumple alguna de las dos, NO se borra (migrate sigue igual) y se
# avisa por consola con el motivo, para revisarlo a mano.
# En el ORM el modelo se saca siempre (era managed=False y ningún código lo
# usaba: ni este sistema ni fontana_escritorio).

from django.db import migrations

TABLA = 'retencion_inym_no_aplicacion'


def borrar_si_vacia(apps, schema_editor):
    conexion = schema_editor.connection
    with conexion.cursor() as cursor:
        if TABLA not in conexion.introspection.table_names(cursor):
            print(f'\n  [0006] La tabla {TABLA} no existe -- nada que borrar.')
            return
        cursor.execute(f'SELECT COUNT(*) FROM `{TABLA}`')
        filas = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT TABLE_NAME, CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
            WHERE REFERENCED_TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME = %s
            """,
            [TABLA],
        )
        referencias = cursor.fetchall()
        if filas or referencias:
            motivos = []
            if filas:
                motivos.append(f'tiene {filas} fila(s)')
            if referencias:
                motivos.append('la referencian: ' + ', '.join(f'{t} ({c})' for t, c in referencias))
            print(f'\n  [0006] NO se borró la tabla {TABLA}: ' + '; '.join(motivos) + '. Revisala a mano.')
            return
        cursor.execute(f'DROP TABLE `{TABLA}`')
        print(f'\n  [0006] Tabla {TABLA} borrada (estaba vacía y sin vínculos).')


def recrear(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{TABLA}` (
              `id` int NOT NULL,
              `id_certificado_inym_no_aplicacion` int DEFAULT NULL,
              `total` decimal(20,2) DEFAULT NULL,
              PRIMARY KEY (`id`)
            )
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ('retenciones_inym', '0005_certificados_no_aplicacion'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(borrar_si_vacia, recrear)],
            state_operations=[migrations.DeleteModel(name='RetencionInymNoAplicacion')],
        ),
    ]
