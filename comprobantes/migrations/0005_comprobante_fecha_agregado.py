# Escrita a mano (2026-10-06): agrega la columna 'fecha_agregado' (fecha y
# hora de carga) a la tabla legada 'comprobante' (Comprobante, managed=False).
#
# Como la tabla es unmanaged, la columna se agrega con SQL directo y el
# AddField queda sólo en el estado de las migraciones (mismo patrón que
# movimientos_caja 0003/0004). Los comprobantes que ya existen quedan en NULL:
# el DEFAULT se pone en un segundo paso (MODIFY), que no toca las filas ya
# existentes.
#
# Se hace con RunPython para que sea seguro volver a correrla: si la columna
# ya existe no la vuelve a agregar, y si el MySQL no acepta el DEFAULT con
# expresión (versiones anteriores a 8.0.13) sólo avisa -- Django la completa
# igual al guardar.
from django.db import migrations, models


def agregar_columna(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'comprobante' AND COLUMN_NAME = 'fecha_agregado'"
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE comprobante ADD COLUMN fecha_agregado DATETIME(6) NULL")
            print('\n  Columna comprobante.fecha_agregado agregada (comprobantes existentes en NULL).')
        else:
            print('\n  La columna comprobante.fecha_agregado ya existía.')
        try:
            cursor.execute(
                "ALTER TABLE comprobante MODIFY COLUMN fecha_agregado DATETIME(6) NULL DEFAULT (UTC_TIMESTAMP(6))"
            )
            print('  DEFAULT UTC_TIMESTAMP() aplicado (también se completa si se inserta desde otro programa).')
        except Exception as exc:  # MySQL < 8.0.13
            print(f'  AVISO: no se pudo poner el DEFAULT en MySQL ({exc}). Desde Django se completa igual.')


def quitar_columna(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE comprobante DROP COLUMN fecha_agregado")


class Migration(migrations.Migration):

    dependencies = [
        ('comprobantes', '0004_comprobantenorecibido'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(agregar_columna, quitar_columna),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='comprobante',
                    name='fecha_agregado',
                    field=models.DateTimeField(
                        'Fecha de carga', blank=True, null=True, auto_now_add=True,
                    ),
                ),
            ],
        ),
    ]
