from django.db import migrations, models


class Migration(migrations.Migration):
    """Agrega la columna 'activo' a la tabla legada 'entidad' (modelo
    managed=False: Django no la crea/altera solo, hace falta el SQL a
    mano). Se usa SeparateDatabaseAndState para que, además de correr el
    ALTER TABLE de verdad, el "estado" interno de migraciones de Django
    quede sincronizado con el campo que se agregó en models.py (si no, un
    futuro makemigrations detectaría el campo como "faltante" y trataría
    de crear otra migración para lo mismo).

    DEFAULT 1: en MySQL, al agregar una columna NOT NULL con DEFAULT a una
    tabla que ya tiene filas, esas filas existentes quedan con ese default
    automáticamente -> todas las entidades ya cargadas quedan activo=1,
    tal como se pidió.
    """

    dependencies = [
        ('entidades', '0003_grupo_rankings'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE entidad ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1",
                    reverse_sql="ALTER TABLE entidad DROP COLUMN activo",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='entidad',
                    name='activo',
                    field=models.BooleanField(default=True),
                ),
            ],
        ),
    ]
