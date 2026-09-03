from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        'Exporta la estructura completa de la base (el CREATE TABLE de cada '
        'tabla, SIN datos) a un archivo .sql. Es de solo lectura, no '
        'modifica nada. Uso:\n'
        '  python manage.py exportar_estructura_bd\n'
        '  python manage.py exportar_estructura_bd --salida otro_nombre.sql'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--salida',
            type=str,
            default='estructura_bd.sql',
            help='Nombre del archivo de salida (por defecto: estructura_bd.sql, en la raíz del proyecto).',
        )

    def handle(self, *args, **options):
        salida = options['salida']

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            tablas = [row[0] for row in cursor.fetchall()]

            with open(salida, 'w', encoding='utf-8') as f:
                f.write('-- Estructura de la base (solo esquema, sin datos)\n')
                f.write(f'-- {len(tablas)} tablas\n\n')
                for tabla in tablas:
                    # Los nombres de tabla salen de information_schema (no son
                    # input externo), así que es seguro interpolarlos acá.
                    cursor.execute(f'SHOW CREATE TABLE `{tabla}`')
                    row = cursor.fetchone()
                    create_stmt = row[1]
                    f.write(f'-- Tabla: {tabla}\n')
                    f.write(create_stmt + ';\n\n')

        self.stdout.write(self.style.SUCCESS(f'{len(tablas)} tablas exportadas a {salida}'))
