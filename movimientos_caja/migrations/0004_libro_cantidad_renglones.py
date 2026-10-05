from django.db import migrations, models


class Migration(migrations.Migration):
    """Agrega la columna opcional 'cantidad_renglones' a banco_cuenta_libro
    (LibroCaja): cuántos renglones tiene cada hoja de ese libro. La usa el
    alta encadenada de movimientos de caja para saber cuándo pasar a la
    hoja siguiente (antes era fijo 25). Vacío = 25.

    Igual que 0003: la tabla es unmanaged, así que la columna se agrega con
    SQL directo y el AddField queda sólo en el estado de las migraciones.
    """

    dependencies = [
        ('movimientos_caja', '0003_libro_fecha_creacion'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE banco_cuenta_libro ADD COLUMN cantidad_renglones INT UNSIGNED NULL;",
                    reverse_sql="ALTER TABLE banco_cuenta_libro DROP COLUMN cantidad_renglones;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='librocaja',
                    name='cantidad_renglones',
                    field=models.PositiveIntegerField(
                        'Cantidad de renglones por hoja', blank=True, null=True,
                        help_text='Opcional. Si se deja vacío se usan 25 renglones por hoja.',
                    ),
                ),
            ],
        ),
    ]
