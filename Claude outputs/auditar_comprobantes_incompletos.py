"""
Auditoría (pedido de Gastón, 08/10/2026): comprobantes guardados SIN alguno
de los datos que desde ahora son obligatorios al cargarlos a mano:
tipo de comprobante, entidad, fecha, número y total.

No modifica nada: sólo informa. Muestra un resumen por dato faltante y por
origen de la carga (agregado_desde), y el detalle de cada comprobante.

Uso:
    python manage.py auditar_comprobantes_incompletos
    python manage.py auditar_comprobantes_incompletos --detalle
    python manage.py auditar_comprobantes_incompletos --excel auditoria_comprobantes_incompletos.xlsx
    python manage.py auditar_comprobantes_incompletos --incluir-no-recibidos
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import Q

from comprobantes.models import Comprobante

FALTANTES = [
    ('tipo', 'Tipo de comprobante', Q(tipo_comprobante__isnull=True)),
    ('entidad', 'Entidad', Q(entidad_emisor__isnull=True)),
    ('fecha', 'Fecha', Q(fecha__isnull=True)),
    ('numero', 'Número', Q(numero__isnull=True) | Q(numero__lte=0)),
    ('total', 'Total', Q(total__isnull=True)),
]


class Command(BaseCommand):
    help = 'Lista los comprobantes a los que les falta tipo, entidad, fecha, número o total (no modifica nada).'

    def add_arguments(self, parser):
        parser.add_argument('--detalle', action='store_true', help='Listar cada comprobante (por defecto, los primeros 30).')
        parser.add_argument('--excel', help='Guardar el detalle completo en este archivo .xlsx.')
        parser.add_argument('--incluir-no-recibidos', action='store_true',
                            help='Incluir también los marcados NO RECIBIDO (por defecto quedan afuera).')

    def handle(self, *args, **o):
        condicion = Q()
        for _clave, _etiqueta, q in FALTANTES:
            condicion |= q
        qs = Comprobante.objects.filter(condicion)
        if not o['incluir_no_recibidos']:
            qs = qs.filter(no_recibido__isnull=True)
        qs = qs.select_related('tipo_comprobante').order_by('id')

        total_comprobantes = Comprobante.objects.count()
        incompletos = list(qs)
        self.stdout.write(f'Comprobantes en la base: {total_comprobantes}')
        self.stdout.write(f'Comprobantes con algún dato obligatorio vacío: {len(incompletos)}\n')
        if not incompletos:
            self.stdout.write(self.style.SUCCESS('Todos los comprobantes tienen tipo, entidad, fecha, número y total.'))
            return

        def faltan(c):
            f = []
            if c.tipo_comprobante_id is None:
                f.append('Tipo de comprobante')
            if c.entidad_emisor_id is None:
                f.append('Entidad')
            if c.fecha is None:
                f.append('Fecha')
            if c.numero is None or c.numero <= 0:
                f.append('Número')
            if c.total is None:
                f.append('Total')
            return f

        por_dato = Counter()
        por_origen = Counter()
        filas = []
        for c in incompletos:
            f = faltan(c)
            por_dato.update(f)
            por_origen[c.agregado_desde or '(sin dato)'] += 1
            try:
                entidad = str(c.entidad_emisor) if c.entidad_emisor_id else ''
            except Exception:  # entidad borrada
                entidad = f'{c.entidad_emisor_id} (no existe)'
            filas.append([c.id, c.fecha, entidad, str(c.tipo_comprobante) if c.tipo_comprobante_id else '',
                          c.punto_de_venta, c.numero, float(c.total) if c.total is not None else None,
                          c.agregado_desde or '', c.fecha_agregado, ', '.join(f)])

        self.stdout.write('Por dato faltante:')
        for etiqueta, n in por_dato.most_common():
            self.stdout.write(f'  {n:>6}  sin {etiqueta}')
        self.stdout.write('\nPor origen de la carga (agregado_desde):')
        for origen, n in por_origen.most_common():
            self.stdout.write(f'  {n:>6}  {origen}')

        lista = filas if o['detalle'] else filas[:30]
        self.stdout.write('\nDetalle (id | fecha | entidad | tipo | pv-número | total | origen | falta):')
        for f in lista:
            self.stdout.write(f'  {f[0]} | {f[1] or "-"} | {f[2] or "-"} | {f[3] or "-"} | '
                              f'{f[4] or "-"}-{f[5] or "-"} | {f[6] if f[6] is not None else "-"} | {f[7] or "-"} | {f[9]}')
        if not o['detalle'] and len(filas) > 30:
            self.stdout.write(f'  ... y {len(filas) - 30} más (--detalle para ver todos, o --excel archivo.xlsx)')

        if o['excel']:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Incompletos'
            ws.append(['ID', 'Fecha', 'Entidad', 'Tipo', 'Punto de venta', 'Número', 'Total',
                       'Agregado desde', 'Fecha de carga', 'Falta'])
            for f in filas:
                if f[8] is not None and getattr(f[8], 'tzinfo', None) is not None:
                    f[8] = f[8].replace(tzinfo=None)
                ws.append(f)
            wb.save(o['excel'])
            self.stdout.write(self.style.SUCCESS(f'\nDetalle completo guardado en {o["excel"]}'))
