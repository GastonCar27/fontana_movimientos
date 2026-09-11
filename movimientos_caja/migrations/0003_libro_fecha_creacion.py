from django.db import migrations, models


class Migration(migrations.Migration):
    """Agrega la columna 'fecha_creacion' a banco_cuenta_libro (LibroCaja).

    La tabla es unmanaged (managed=False), así que Django no la crea ni la
    altera solo: la columna se agrega con SQL directo (RunSQL) y, aparte,
    se deja registrado el AddField en el estado de las migraciones (con
    state_operations) para que coincida con el modelo actual y no queden
    diferencias si en el futuro se agregan más campos a este mismo modelo.

    Los libros que ya existían quedan con fecha_creacion en NULL hasta
    correr el comando de gestión 'backfill_fecha_creacion_libros', que la
    completa con la fecha de emisión del movimiento más viejo cargado en
    cada libro. Los libros nuevos la completan solos (auto_now_add=True).
    """

    dependencies = [
        ('movimientos_caja', '0002_productotipo'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE banco_cuenta_libro ADD COLUMN fecha_creacion DATE NULL;",
                    reverse_sql="ALTER TABLE banco_cuenta_libro DROP COLUMN fecha_creacion;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='librocaja',
                    name='fecha_creacion',
                    field=models.DateField(blank=True, null=True, auto_now_add=True),
                ),
            ],
        ),
    ]
