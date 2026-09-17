from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retenciones', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE retencion ADD COLUMN es_emisor INT NULL DEFAULT 1;"
                    ),
                    reverse_sql="ALTER TABLE retencion DROP COLUMN es_emisor;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='retencion',
                    name='es_emisor',
                    field=models.IntegerField(
                        blank=False, null=True, default=1,
                        choices=[(1, 'Sí'), (0, 'No')],
                    ),
                ),
            ],
        ),
    ]
