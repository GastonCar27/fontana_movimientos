from django.db import migrations


class Migration(migrations.Migration):
    """La migración 0005 (AlterField de 'solicitante' y 'responsable_retiro',
    de Empleado a Entidad) quedó marcada como aplicada, pero Django la
    resolvió como "no-op" a nivel SQL (confirmado con `sqlmigrate
    solicitudes_compra 0005`, que no imprime ningún ALTER TABLE): nunca
    llegó a tocar las restricciones (FOREIGN KEY) reales en la base, que
    seguían apuntando a la tabla vieja 'empleado' en vez de a 'entidad'
    -- por eso al guardar una solicitud saltaba IntegrityError (1452).

    Se verificó antes (sin tocar nada) que ninguna solicitud_compra.
    solicitante_id / responsable_retiro_id apunta a un id que no exista en
    'entidad'. Un primer intento de esta migración sólo hacía el DROP
    FOREIGN KEY de las dos restricciones viejas + el ADD CONSTRAINT de las
    nuevas, pero MySQL rechazó el ADD CONSTRAINT (error 3780, "columns...
    are incompatible") porque responsable_retiro_id/solicitante_id habían
    quedado en bigint (el tipo de la vieja Empleado) mientras que
    entidad.id es un int normal -- MySQL exige que el tipo de la columna
    que referencia coincida exactamente con el de la columna referenciada
    para poder crear la FOREIGN KEY. Como MySQL confirma cada ALTER TABLE
    al instante (no espera a que termine toda la migración para
    confirmar), los dos DROP FOREIGN KEY de ese primer intento ya habían
    quedado aplicados aunque la migración en conjunto haya fallado (se
    confirmó con un SHOW CREATE TABLE antes de escribir esta versión) --
    por eso acá NO se repite ese DROP, sólo se corrige el tipo de columna
    y se agregan las restricciones nuevas."""

    dependencies = [
        ('solicitudes_compra', '0007_alter_productogenerico_id'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'ALTER TABLE solicitud_compra MODIFY COLUMN responsable_retiro_id INT NOT NULL',
                'ALTER TABLE solicitud_compra MODIFY COLUMN solicitante_id INT NOT NULL',
                'ALTER TABLE solicitud_compra ADD CONSTRAINT '
                'solicitud_compra_responsable_retiro_id_fk_entidad_id '
                'FOREIGN KEY (responsable_retiro_id) REFERENCES entidad (id)',
                'ALTER TABLE solicitud_compra ADD CONSTRAINT '
                'solicitud_compra_solicitante_id_fk_entidad_id '
                'FOREIGN KEY (solicitante_id) REFERENCES entidad (id)',
            ],
            reverse_sql=[
                'ALTER TABLE solicitud_compra DROP FOREIGN KEY '
                'solicitud_compra_responsable_retiro_id_fk_entidad_id',
                'ALTER TABLE solicitud_compra DROP FOREIGN KEY '
                'solicitud_compra_solicitante_id_fk_entidad_id',
                'ALTER TABLE solicitud_compra MODIFY COLUMN responsable_retiro_id BIGINT NOT NULL',
                'ALTER TABLE solicitud_compra MODIFY COLUMN solicitante_id BIGINT NOT NULL',
            ],
        ),
    ]
