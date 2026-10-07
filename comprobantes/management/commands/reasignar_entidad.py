"""
Pasa los comprobantes de una entidad a otra (pedido de Gastón, 06/10/2026).

Caso que lo originó: 903 Facturas B emitidas en 2026 a consumidor final
(documento tipo 99 en AFIP) que la carga "csv" dejó en la entidad "NO USAR"
(12377); van a CONSUMIDOR FINAL (305).

  * Pasa TODOS los comprobantes de --de a --a (opcional: sólo los de un
    rango de fechas con --desde / --hasta).
  * No toca nada más: si la entidad vieja se usa en otras tablas
    (movimientos de caja, liquidaciones, retenciones, etc.) lo informa.
  * Con --desactivar marca la entidad vieja como inactiva (no se borra,
    criterio del sistema), sólo si después del cambio no le queda nada.
  * Las liquidaciones de los comprobantes que se pasan quedan como están
    (el vínculo es al comprobante); si alguno está en una liquidación de la
    entidad vieja, se avisa.

Por defecto es DRY RUN; --aplicar para guardar.

Uso:
    python manage.py reasignar_entidad --de 12377 --a 305 --desactivar
    python manage.py reasignar_entidad --de 12377 --a 305 --desactivar --aplicar
    python manage.py reasignar_entidad --de 2838 --a 2625 --pasar-documento --desactivar --aplicar   (CANTONI)
"""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from comprobantes.models import Comprobante
from entidades.models import Entidad
from liquidaciones.models import LiquidacionComprobante


class Command(BaseCommand):
    help = 'Pasa los comprobantes de una entidad a otra (y opcionalmente marca la vieja como inactiva).'

    def add_arguments(self, parser):
        parser.add_argument('--de', type=int, required=True, help='ID de la entidad de la que salen los comprobantes.')
        parser.add_argument('--a', type=int, required=True, help='ID de la entidad a la que pasan.')
        parser.add_argument('--desde', help='Sólo comprobantes desde esta fecha (AAAA-MM-DD).')
        parser.add_argument('--hasta', help='Sólo comprobantes hasta esta fecha (AAAA-MM-DD).')
        parser.add_argument('--desactivar', action='store_true', help='Marcar la entidad vieja como inactiva.')
        parser.add_argument('--pasar-documento', action='store_true',
                            help='Cargarle a la entidad nueva el DNI de la vieja (documento, o DNI cargado en el campo CUIT) si no tiene.')
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **o):
        if o['de'] == o['a']:
            raise CommandError('--de y --a son la misma entidad.')
        vieja = Entidad.objects.filter(pk=o['de']).first()
        nueva = Entidad.objects.filter(pk=o['a']).first()
        if not vieja or not nueva:
            raise CommandError(f'No existe la entidad {o["de"] if not vieja else o["a"]}.')
        self.stdout.write(f'De:  {vieja.id} - {vieja.nombre} (CUIT {vieja.cuit or "-"})')
        self.stdout.write(f'A:   {nueva.id} - {nueva.nombre} (CUIT {nueva.cuit or "-"})')

        qs = Comprobante.objects.filter(entidad_emisor_id=vieja.id)
        if o.get('desde'):
            qs = qs.filter(fecha__gte=o['desde'])
        if o.get('hasta'):
            qs = qs.filter(fecha__lte=o['hasta'])
        comps = list(qs.select_related('tipo_comprobante').order_by('fecha', 'id'))
        resumen = Counter((str(c.tipo_comprobante) if c.tipo_comprobante_id else '-', c.es_emisor) for c in comps)
        self.stdout.write(f'\nComprobantes a pasar: {len(comps)}')
        for (tipo, emisor), n in sorted(resumen.items()):
            self.stdout.write(f'   {n:>6}  {tipo}  ({"emitidos por Fontana" if emisor == 0 else "emitidos por la entidad"})')
        if comps:
            self.stdout.write(f'   fechas: {comps[0].fecha} a {comps[-1].fecha}; total ${sum((c.total or 0) for c in comps):,.2f}')

        liqs = list(LiquidacionComprobante.objects.filter(comprobante__in=comps).select_related('liquidacion'))
        en_liq_vieja = [lc for lc in liqs if lc.liquidacion.entidad_id == vieja.id]
        if liqs:
            self.stdout.write(self.style.WARNING(
                f'   {len(liqs)} están en liquidaciones (quedan vinculados igual)'
                + (f'; {len(en_liq_vieja)} en liquidaciones de la entidad vieja: '
                   + ', '.join(sorted({str(lc.liquidacion_id) for lc in en_liq_vieja})) if en_liq_vieja else '')))

        # Otros usos de la entidad vieja (no se tocan)
        otros = []
        ids = [c.id for c in comps]
        for rel in Entidad._meta.related_objects:
            try:
                if rel.many_to_many:
                    n = getattr(vieja, rel.get_accessor_name()).count()
                else:
                    q = rel.related_model._default_manager.filter(**{rel.field.name: vieja})
                    if rel.related_model is Comprobante:
                        q = q.exclude(id__in=ids)
                    n = q.count()
            except Exception:
                continue
            if n:
                otros.append(f'{rel.related_model._meta.verbose_name_plural} ({rel.related_model._meta.db_table}.{rel.field.name}): {n}')
        if otros:
            self.stdout.write(self.style.WARNING('\nLa entidad vieja se usa además en (no se toca):'))
            for x in otros:
                self.stdout.write(self.style.WARNING('   ' + x))
        else:
            self.stdout.write('\nLa entidad vieja no se usa en ninguna otra tabla.')

        dni = None
        if o['pasar_documento'] and not nueva.documento_nro:
            dni = vieja.documento_nro
            if not dni:
                d = ''.join(ch for ch in str(vieja.cuit or '') if ch.isdigit())
                if 6 <= len(d) <= 8 and d.strip('0'):
                    dni = int(d)
            if dni:
                self.stdout.write(f'\nA la entidad {nueva.id} se le carga el DNI {dni}.')
            else:
                self.stdout.write('\nLa entidad vieja no tiene un DNI para pasar.')

        desactivar = o['desactivar'] and not otros
        if o['desactivar'] and otros:
            self.stdout.write(self.style.WARNING('No se marca como inactiva porque todavía se usa en otras tablas.'))
        elif desactivar:
            self.stdout.write(f'Se marca la entidad {vieja.id} como inactiva.')

        if not o['aplicar']:
            self.stdout.write('\nEsto fue un DRY RUN, no se guardó nada. Volvé a correr con --aplicar para guardar.')
            return
        with transaction.atomic():
            n = Comprobante.objects.filter(id__in=ids).update(entidad_emisor_id=nueva.id)
            if dni:
                Entidad.objects.filter(pk=nueva.id, documento_nro__isnull=True).update(documento_nro=dni)
            if desactivar:
                Entidad.objects.filter(pk=vieja.id).update(activo=False)
        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {n} comprobantes pasaron a {nueva.id} - {nueva.nombre}'
            + (f'; la entidad {vieja.id} quedó inactiva.' if desactivar else '.')))
