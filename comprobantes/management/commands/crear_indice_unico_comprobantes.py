"""
Índice ÚNICO en la tabla comprobante (06/10/2026): impide a nivel base de
datos cargar dos veces el mismo comprobante -- misma entidad + tipo + punto
de venta + número --, venga de este sistema, del importador de AFIP o de
cualquier otro programa que escriba en la base.

Antes de crearlo hay que limpiar los duplicados que ya existan (MySQL no
deja crear el índice si los hay): el comando los lista. Para los de una
entidad se puede usar fusionar_comprobantes_duplicados.

(Los comprobantes con punto de venta o número vacío no cuentan: MySQL
permite varios NULL en un índice único.)

Uso:
    python manage.py crear_indice_unico_comprobantes             # informe
    python manage.py crear_indice_unico_comprobantes --aplicar   # crea el índice si no hay duplicados
"""
from django.core.management.base import BaseCommand
from django.db import connection

NOMBRE_INDICE = 'comprobante_unico_entidad_tipo_pv_numero'


class Command(BaseCommand):
    help = 'Lista duplicados exactos de comprobantes y crea el índice único (entidad, tipo, pv, número).'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **o):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'comprobante' AND INDEX_NAME = %s", [NOMBRE_INDICE])
            if cursor.fetchone()[0]:
                self.stdout.write(self.style.SUCCESS(f'El índice {NOMBRE_INDICE} ya existe. Nada para hacer.'))
                return
            cursor.execute(
                "SELECT c.id_entidad, e.nombre, c.id_tipo_comp, c.punto_de_venta, c.numero, COUNT(*), "
                "GROUP_CONCAT(c.id ORDER BY c.id) "
                "FROM comprobante c LEFT JOIN entidad e ON e.id = c.id_entidad "
                "WHERE c.id_entidad IS NOT NULL AND c.id_tipo_comp IS NOT NULL "
                "AND c.punto_de_venta IS NOT NULL AND c.numero IS NOT NULL "
                "GROUP BY c.id_entidad, e.nombre, c.id_tipo_comp, c.punto_de_venta, c.numero HAVING COUNT(*) > 1 "
                "ORDER BY e.nombre, c.numero")
            duplicados = cursor.fetchall()

        if duplicados:
            self.stdout.write(self.style.WARNING(
                f'Hay {len(duplicados)} comprobante(s) cargados más de una vez (misma entidad + tipo + pv + número). '
                'Hay que dejar uno solo de cada uno antes de crear el índice:'))
            for ent, nombre, tipo, pv, numero, cant, ids in duplicados:
                self.stdout.write(f'  entidad {ent} ({nombre}) tipo {tipo} pv {pv} nº {numero}: {cant} veces -> ids {ids}')
            self.stdout.write('\nPara una entidad: python manage.py fusionar_comprobantes_duplicados --entidad <id>  '
                              '(o borrar el sobrante desde Comprobantes > Modificar).')
            return

        self.stdout.write('No hay duplicados exactos.')
        if not o['aplicar']:
            self.stdout.write(self.style.WARNING('DRY RUN: volvé a correr con --aplicar para crear el índice.'))
            return
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE UNIQUE INDEX {NOMBRE_INDICE} ON comprobante (id_entidad, id_tipo_comp, punto_de_venta, numero)")
        self.stdout.write(self.style.SUCCESS(f'Índice único {NOMBRE_INDICE} creado.'))
