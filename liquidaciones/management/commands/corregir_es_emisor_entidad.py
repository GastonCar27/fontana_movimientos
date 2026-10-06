"""
Corrección puntual (pedido de Gastón, 06/10/2026): comprobantes de una
entidad que quedaron cargados como emitidos por FONTANA (es_emisor = 0) cuando
en realidad los emitió la ENTIDAD (compras / gastos -> es_emisor = 1).
Caso real: Electricidad de Misiones (entidad 40), cuyas facturas aparecían
para liquidar en COBRO en vez de PAGO.

Pasa es_emisor de 0 a 1 en los comprobantes de la entidad indicada. NO toca
los que ya están en una liquidación de COBRO (se listan aparte para revisar
a mano, porque cambiarlos dejaría esa liquidación inconsistente).

Por defecto es DRY RUN (sólo informe). Pasar --aplicar para guardar.

Uso:
    python manage.py corregir_es_emisor_entidad --entidad 40
    python manage.py corregir_es_emisor_entidad --entidad 40 --aplicar
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from comprobantes.models import Comprobante
from entidades.models import Entidad
from liquidaciones.models import LiquidacionComprobante


class Command(BaseCommand):
    help = 'Pasa es_emisor de 0 a 1 (emitido por la entidad) en los comprobantes de una entidad. Dry-run salvo --aplicar.'

    def add_arguments(self, parser):
        parser.add_argument('--entidad', type=int, required=True)
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **o):
        entidad = Entidad.objects.filter(pk=o['entidad']).first()
        if not entidad:
            raise CommandError(f'No existe la entidad {o["entidad"]}.')
        self.stdout.write(f'Entidad: {entidad.id} - {entidad.nombre} (CUIT {entidad.cuit or "-"})')

        comprobantes = list(
            Comprobante.objects.filter(entidad_emisor_id=entidad.id, es_emisor=0).order_by('fecha', 'id')
        )
        en_cobro = {}
        for lc in LiquidacionComprobante.objects.filter(
            comprobante_id__in=[c.id for c in comprobantes], liquidacion__tipo='cobro'
        ).select_related('liquidacion'):
            en_cobro.setdefault(lc.comprobante_id, []).append(lc.liquidacion)

        a_corregir = [c for c in comprobantes if c.id not in en_cobro]
        bloqueados = [c for c in comprobantes if c.id in en_cobro]

        def linea(c):
            return (f'  id {c.id}  {c.fecha}  {c.comprobante_string or ""}  pv {c.punto_de_venta} nº {c.numero}  '
                    f'total {c.total}  agregado_desde={c.agregado_desde or "-"}')

        self.stdout.write(f'\nComprobantes cargados como emitidos por Fontana (es_emisor=0): {len(comprobantes)}')
        self.stdout.write(f'A corregir (pasan a emitidos por la entidad -> se liquidan en PAGO): {len(a_corregir)}')
        for c in a_corregir:
            self.stdout.write(linea(c))
        if bloqueados:
            self.stdout.write(self.style.WARNING(
                f'\nYa están en una liquidación de COBRO -- NO se tocan, revisar a mano: {len(bloqueados)}'
            ))
            for c in bloqueados:
                liqs = ', '.join(f'id {l.id} (nº {l.numero}, {l.fecha})' for l in en_cobro[c.id])
                self.stdout.write(self.style.WARNING(linea(c) + f'  -> liquidación de cobro {liqs}'))

        if not a_corregir:
            self.stdout.write(self.style.SUCCESS('\nNada para corregir.'))
            return
        if not o['aplicar']:
            self.stdout.write(self.style.WARNING(
                '\nEsto fue un DRY RUN, no se guardó nada. Volvé a correr con --aplicar para guardar.'
            ))
            return

        with transaction.atomic():
            n = Comprobante.objects.filter(id__in=[c.id for c in a_corregir], es_emisor=0).update(es_emisor=1)
        self.stdout.write(self.style.SUCCESS(
            f'\nListo -- {n} comprobante(s) de {entidad.nombre} pasaron a "emitido por la entidad" '
            f'({timezone.now():%Y-%m-%d %H:%M}). Ya aparecen en las liquidaciones de PAGO.'
        ))
