from django.db import migrations, models


class Migration(migrations.Migration):
    """Relación muchos-a-muchos entre Rol ("tipo de entidad") y Entidad:
    una entidad puede tener más de un tipo. Se declara en Rol (managed=True)
    para que Django cree normalmente la tabla intermedia, aunque el otro
    lado (Entidad) sea managed=False -> Django solo necesita que la tabla
    'entidad' y su columna 'id' ya existan, cosa que ya es así."""

    dependencies = [
        ('entidades', '0004_entidad_activo'),
    ]

    operations = [
        migrations.AddField(
            model_name='rol',
            name='entidades',
            field=models.ManyToManyField(blank=True, related_name='roles', to='entidades.entidad'),
        ),
    ]
