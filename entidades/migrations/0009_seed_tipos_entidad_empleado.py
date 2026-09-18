# Data migration: crea los tipos de entidad ("Rol") usados para migrar a los
# empleados a la base de Entidad (ver services/buscadores.py y
# solicitudes_compra/forms.py) en vez de tener un modelo Empleado aparte.
#
# 'Empleado' es sólo descriptiva/informativa (para categorizar, igual que
# Transportista o Chofer de Transporte) y por sí sola NO habilita a una
# entidad a aparecer en los buscadores de Solicitud de Compra: para eso hace
# falta además el rol específico correspondiente:
#   - 'Autorizado a solicitar': habilita el campo "Solicitante" (quien
#     autoriza el pedido).
#   - 'Autorizado a retirar': habilita el campo "Autorizado a retirar"
#     (quien va a buscar la mercadería).
# Una misma entidad puede tener uno, otro, ambos, o ninguno de estos dos
# roles (además de 'Empleado'), y se pueden seguir agregando más roles de
# este tipo a futuro (ej. bomberos, policía, donaciones) sin tocar código.
#
# Mismo patrón que 0006_seed_tipos_entidad.py.

from django.db import migrations
from django.utils.text import slugify

TIPOS_INICIALES = [
    'Empleado',
    'Autorizado a solicitar',
    'Autorizado a retirar',
]


def crear_tipos(apps, schema_editor):
    Rol = apps.get_model('entidades', 'Rol')
    for nombre in TIPOS_INICIALES:
        Rol.objects.get_or_create(nombre=nombre, defaults={'slug': slugify(nombre)})


def eliminar_tipos(apps, schema_editor):
    Rol = apps.get_model('entidades', 'Rol')
    Rol.objects.filter(nombre__in=TIPOS_INICIALES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('entidades', '0008_grupo_remitos'),
    ]

    operations = [
        migrations.RunPython(crear_tipos, eliminar_tipos),
    ]
