from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('liquidaciones', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE liquidacion "
                        "ADD COLUMN tipo VARCHAR(10) NOT NULL DEFAULT 'pago';"
                    ),
                    reverse_sql="ALTER TABLE liquidacion DROP COLUMN tipo;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='liquidacion',
                    name='tipo',
                    field=models.CharField(
                        max_length=10,
                        default='pago',
                        choices=[('pago', 'Pago (nosotros pagamos)'), ('cobro', 'Cobro (nos pagan)')],
                    ),
                ),
            ],
        ),
    ]
