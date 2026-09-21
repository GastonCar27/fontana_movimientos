from django.db import migrations


class Migration(migrations.Migration):
    """Las migraciones 0002 (agrega 'prioridad') y 0003 (agrega 'sector')
    figuran aplicadas en django_migrations, pero ninguna de las dos llegó
    a tocar la tabla real solicitud_compra_renglon -- le faltaban las dos
    columnas por completo (confirmado con SHOW CREATE TABLE). Ambas se
    habían escrito a mano en su momento, sin poder correr
    `manage.py makemigrations`/`migrate` contra la base real en ese
    entorno, así que quedaron marcadas como aplicadas sin que el ALTER
    TABLE se haya ejecutado nunca. El estado de Django (models.py y el
    historial de migraciones) ya da por hecho que estas columnas existen,
    así que acá sólo se agregan con SQL directo -- no se vuelve a declarar
    el AddField, porque el estado ya las tiene."""

    dependencies = [
        ('solicitudes_compra', '0008_fix_fk_empleado_a_entidad'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE solicitud_compra_renglon "
                "ADD COLUMN prioridad VARCHAR(10) NOT NULL DEFAULT 'media'",
                'ALTER TABLE solicitud_compra_renglon ADD COLUMN sector_id INT NULL',
                'ALTER TABLE solicitud_compra_renglon ADD CONSTRAINT '
                'solicitud_compra_renglon_sector_id_fk_sector_tipo_id '
                'FOREIGN KEY (sector_id) REFERENCES sector_tipo (id)',
            ],
            reverse_sql=[
                'ALTER TABLE solicitud_compra_renglon DROP FOREIGN KEY '
                'solicitud_compra_renglon_sector_id_fk_sector_tipo_id',
                'ALTER TABLE solicitud_compra_renglon DROP COLUMN sector_id',
                'ALTER TABLE solicitud_compra_renglon DROP COLUMN prioridad',
            ],
        ),
    ]
