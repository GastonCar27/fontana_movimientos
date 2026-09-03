from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        'Inspecciona la base para encontrar la tabla/valores que definen la '
        'categoria de producto_detalle (Producto/Servicio/etc). No modifica '
        'nada, solo lee. Uso:\n'
        '  python manage.py inspeccionar_categoria_producto'
    )

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # 1. Tablas candidatas (nombre relacionado con item/tipo/categoria)
            cursor.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND (
                    table_name LIKE %s OR table_name LIKE %s OR table_name LIKE %s
                )
                ORDER BY table_name
                """,
                ['%item%', '%categoria%', '%producto_tipo%'],
            )
            tablas = [row[0] for row in cursor.fetchall()]

            self.stdout.write(self.style.SUCCESS('--- Tablas candidatas encontradas ---'))
            if tablas:
                for t in tablas:
                    self.stdout.write(f'  - {t}')
            else:
                self.stdout.write('  (ninguna con ese nombre)')

            # 2. Si existe una tabla llamada exactamente item_tipo, mostrar su contenido
            if 'item_tipo' in tablas:
                self.stdout.write(self.style.SUCCESS('\n--- Contenido de item_tipo ---'))
                cursor.execute('SELECT * FROM item_tipo')
                columnas = [col[0] for col in cursor.description]
                self.stdout.write(' | '.join(columnas))
                for row in cursor.fetchall():
                    self.stdout.write(' | '.join(str(v) for v in row))

            # 3. Valores distintos de id_item_tipo realmente usados en producto_detalle
            self.stdout.write(self.style.SUCCESS('\n--- Valores distintos de id_item_tipo en producto_detalle ---'))
            cursor.execute(
                """
                SELECT id_item_tipo, COUNT(*)
                FROM producto_detalle
                GROUP BY id_item_tipo
                ORDER BY id_item_tipo
                """
            )
            conteos = cursor.fetchall()
            for id_item_tipo, cantidad in conteos:
                self.stdout.write(f'  id_item_tipo={id_item_tipo}: {cantidad} productos')

            # 4. Ejemplos de nombres de producto por cada id_item_tipo, para
            #    poder reconocer a ojo cual es "Producto" y cual "Servicio"
            self.stdout.write(self.style.SUCCESS('\n--- Ejemplos de productos por id_item_tipo ---'))
            cursor.execute('SELECT id_item_tipo, nombre FROM producto_detalle ORDER BY id_item_tipo')
            ejemplos = defaultdict(list)
            for id_item_tipo, nombre in cursor.fetchall():
                if len(ejemplos[id_item_tipo]) < 6:
                    ejemplos[id_item_tipo].append(nombre)
            for id_item_tipo, nombres in ejemplos.items():
                self.stdout.write(f'  id_item_tipo={id_item_tipo}: {", ".join(str(n) for n in nombres)}')
