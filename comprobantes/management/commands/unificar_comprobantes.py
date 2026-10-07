"""
Unifica comprobantes cargados dos veces (pedido de Gastón, 06/10/2026).

Caso que lo originó: 4 Facturas A que FONTANA le emitió a la Cooperativa Alto
Uruguay (honorarios, punto de venta 8, nº 723, 736, 737 y 743). Se habían
cargado a mano con la entidad FONTANA S.A. para poder usarlas en las
liquidaciones de PAGO a la Cooperativa, y después la carga "csv" de AFIP las
volvió a cargar, bien, con la entidad Cooperativa y emitidas por Fontana.

Para cada par --par CONSERVAR:BORRAR:
  * se pasan al que se conserva los vínculos del que se borra: liquidaciones
    (manteniendo Debe/Haber), retenciones, renglones (si el que queda no
    tiene), tipo de cambio, marca no recibido y otros tributos;
  * se completan en el que queda los datos que tenga vacíos (nunca la
    entidad, el tipo ni quién lo emitió);
  * se borra el otro;
  * se recalculan las liquidaciones afectadas y se muestra el Debe/Haber
    antes y después (tiene que dar igual si los dos tenían el mismo total).
No se toca un par si los dos están en la MISMA liquidación, o si los totales
son distintos (salvo --forzar).

Por defecto es DRY RUN; --aplicar para guardar.

Con --tomar-tipo, al que queda se le pone además el tipo de comprobante del
que se borra (caso: recibidos cargados a mano con un tipo y por la carga de
AFIP con el tipo correcto; se deja el cargado a mano porque está liquidado).

Uso (recibidos con el tipo mal cargado a mano):
    python manage.py unificar_comprobantes --par 4480:4501 --par 4807:14837 --par 4928:14860 --par 5191:5212 --tomar-tipo

Uso (Cooperativa Alto Uruguay):
    python manage.py unificar_comprobantes --par 6585:5387 --par 11854:5134 --par 11885:5135 --par 13777:5454
    python manage.py unificar_comprobantes --par 6585:5387 --par 11854:5134 --par 11885:5135 --par 13777:5454 --aplicar
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from comprobantes.importador_afip import _comprobante_string
from comprobantes.models import (
    Comprobante, ComprobanteNoRecibido, ComprobanteRenglon, ComprobanteTipoDeCambio,
)
from liquidaciones.models import Liquidacion, LiquidacionComprobante
from retenciones.models import RetencionRenglon

NO_COPIAR = {'id', 'entidad_emisor', 'tipo_comprobante', 'es_emisor', 'fecha_agregado', 'agregado_desde',
             'comprobante_string'}


def _vacio(v):
    return v is None or v == '' or (isinstance(v, (int, float, Decimal)) and v == 0)


class Command(BaseCommand):
    help = 'Unifica pares de comprobantes duplicados (CONSERVAR:BORRAR), pasando liquidaciones y demás vínculos.'

    def add_arguments(self, parser):
        parser.add_argument('--par', action='append', required=True, help='CONSERVAR:BORRAR (ids). Se puede repetir.')
        parser.add_argument('--tomar-tipo', action='store_true',
                            help='Al que queda ponerle el tipo de comprobante del que se borra (el que vino de AFIP).')
        parser.add_argument('--forzar', action='store_true', help='Unificar aunque los totales sean distintos.')
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **o):
        pares = []
        for p in o['par']:
            try:
                a, b = (int(x) for x in p.split(':'))
            except ValueError:
                raise CommandError(f'--par mal escrito: {p!r} (tiene que ser CONSERVAR:BORRAR, ej. 6585:5387)')
            pares.append((a, b))

        listos, liqs_afectadas = [], set()
        for id_k, id_b in pares:
            k = Comprobante.objects.filter(pk=id_k).first()
            b = Comprobante.objects.filter(pk=id_b).first()
            if not k or not b:
                self.stdout.write(self.style.ERROR(f'{id_k}:{id_b} -- no existe el comprobante {id_k if not k else id_b}'))
                continue
            self.stdout.write(
                f'\nQueda  {k.id}: {k.fecha} {k.tipo_comprobante_id} pv {k.punto_de_venta} nº {k.numero} ${k.total}  '
                f'entidad {k.entidad_emisor_id} - {k.entidad_nombre or ""}  es_emisor={k.es_emisor}  ({k.agregado_desde})')
            self.stdout.write(
                f'Se borra {b.id}: {b.fecha} {b.tipo_comprobante_id} pv {b.punto_de_venta} nº {b.numero} ${b.total}  '
                f'entidad {b.entidad_emisor_id}  es_emisor={b.es_emisor}  ({b.agregado_desde})')
            problemas = []
            if (k.total or 0) != (b.total or 0) and not o['forzar']:
                problemas.append(f'totales distintos ({k.total} / {b.total}); usar --forzar si igual corresponde')
            liq_k = set(LiquidacionComprobante.objects.filter(comprobante=k).values_list('liquidacion_id', flat=True))
            liq_b = list(LiquidacionComprobante.objects.filter(comprobante=b).select_related('liquidacion'))
            comunes = liq_k & {lc.liquidacion_id for lc in liq_b}
            if comunes:
                problemas.append(f'los dos están en la liquidación {", ".join(map(str, comunes))}')
            for lc in liq_b:
                self.stdout.write(f'   pasa la liquidación {lc.liquidacion.tipo} {lc.liquidacion_id} '
                                  f'({lc.liquidacion.fecha}) en {lc.tipo}')
            cambios = {}
            for f in Comprobante._meta.concrete_fields:
                if f.name not in NO_COPIAR and _vacio(getattr(k, f.attname)) and not _vacio(getattr(b, f.attname)):
                    cambios[f.attname] = getattr(b, f.attname)
            if o['tomar_tipo'] and b.tipo_comprobante_id and b.tipo_comprobante_id != k.tipo_comprobante_id:
                cambios['tipo_comprobante_id'] = b.tipo_comprobante_id
                cambios['comprobante_string'] = b.comprobante_string or _comprobante_string(
                    b.tipo_comprobante, k.punto_de_venta or b.punto_de_venta, k.numero)
                self.stdout.write(f'   tipo: {k.tipo_comprobante} -> {b.tipo_comprobante}')
            if cambios:
                self.stdout.write(f'   se completa: {", ".join(c for c in cambios if c not in ("tipo_comprobante_id", "comprobante_string"))}')
            if problemas:
                self.stdout.write(self.style.WARNING('   NO SE TOCA: ' + '; '.join(problemas)))
                continue
            listos.append((k, b, cambios))
            liqs_afectadas.update(lc.liquidacion_id for lc in liq_b)

        antes = {l.id: (l.debe, l.haber) for l in Liquidacion.objects.filter(id__in=liqs_afectadas)}
        self.stdout.write(f'\nPares a unificar: {len(listos)}')
        if not o['aplicar']:
            self.stdout.write('Esto fue un DRY RUN, no se guardó nada. Volvé a correr con --aplicar para guardar.')
            return

        with transaction.atomic():
            for k, b, cambios in listos:
                LiquidacionComprobante.objects.filter(comprobante=b).update(comprobante=k)
                RetencionRenglon.objects.filter(comprobante=b).update(comprobante=k)
                if not ComprobanteRenglon.objects.filter(comprobante=k).exists():
                    ComprobanteRenglon.objects.filter(comprobante=b).update(comprobante=k)
                else:
                    ComprobanteRenglon.objects.filter(comprobante=b).delete()
                for modelo in (ComprobanteTipoDeCambio, ComprobanteNoRecibido):
                    if modelo.objects.filter(comprobante=k).exists():
                        modelo.objects.filter(comprobante=b).delete()
                    else:
                        modelo.objects.filter(comprobante=b).update(comprobante=k)
                with connection.cursor() as cur:
                    cur.execute('SELECT COUNT(*) FROM comprobante_otro_tributo_detalle WHERE id_comprobante=%s', [k.id])
                    if cur.fetchone()[0]:
                        cur.execute('DELETE FROM comprobante_otro_tributo_detalle WHERE id_comprobante=%s', [b.id])
                    else:
                        cur.execute('UPDATE comprobante_otro_tributo_detalle SET id_comprobante=%s WHERE id_comprobante=%s',
                                    [k.id, b.id])
                if cambios:
                    Comprobante.objects.filter(pk=k.pk).update(**cambios)
                Comprobante.objects.filter(pk=b.pk).delete()
            for liq in Liquidacion.objects.filter(id__in=liqs_afectadas):
                liq.recalcular_totales(guardar=True)

        self.stdout.write('\nLiquidaciones afectadas (Debe / Haber antes -> después):')
        for liq in Liquidacion.objects.filter(id__in=liqs_afectadas).order_by('id'):
            d0, h0 = antes.get(liq.id, (None, None))
            igual = (d0 or 0) == (liq.debe or 0) and (h0 or 0) == (liq.haber or 0)
            linea = f'   {liq.tipo} {liq.id} ({liq.fecha}): {d0} / {h0}  ->  {liq.debe} / {liq.haber}'
            self.stdout.write(self.style.SUCCESS(linea + '  (igual)') if igual else self.style.WARNING(linea + '  CAMBIÓ'))
        self.stdout.write(self.style.SUCCESS(f'\nListo: {len(listos)} par(es) unificados.'))
