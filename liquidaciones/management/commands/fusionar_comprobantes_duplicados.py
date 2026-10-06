"""
Corrección (pedido de Gastón, 06/10/2026): comprobantes DUPLICADOS de una
entidad. Caso real: Electricidad de Misiones (entidad 40) -- se habían
cargado a mano como "Factura A" y al importar el CSV de AFIP venían como
"17 - LIQUIDACION DE SERVICIOS PUBLICOS CLASE A"; el importador no los
reconoció como el mismo comprobante (distinto tipo) y los cargó de nuevo.
Ej.: número 1654506.

Para cada par (misma entidad + mismo número, y mismo punto de venta si los
dos lo tienen cargado):
  - ORIGINAL = el cargado a mano (sin fecha_agregado o, si no, el de id menor);
  - DUPLICADO = el que vino del CSV.
Se deja sólo el ORIGINAL y se le copian los datos del CSV:
  - tipo de comprobante y comprobante_string: SIEMPRE los del CSV (el
    original estaba mal cargado como Factura A);
  - el resto de los campos: sólo se completan los que el original tiene
    vacíos (o en 0, salvo es_emisor). Si los dos tienen un valor distinto,
    NO se pisa: se informa para revisarlo a mano.
Lo que cuelga del DUPLICADO se pasa al ORIGINAL antes de borrarlo:
renglones, vínculos a liquidaciones y a retenciones, tipo de cambio y marca
NO RECIBIDO -- salvo que el original ya tenga lo mismo, o que el duplicado
esté en una liquidación del tipo contrario al del original (ej. el duplicado
del CSV, cargado como emitido por Fontana, metido en un COBRO), en cuyo caso
el par NO se toca y se informa.

Por defecto es DRY RUN. Pasar --aplicar para guardar.

Uso:
    python manage.py fusionar_comprobantes_duplicados --entidad 40
    python manage.py fusionar_comprobantes_duplicados --entidad 40 --numero 1654506
    python manage.py fusionar_comprobantes_duplicados --entidad 40 --aplicar
"""
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from comprobantes.models import (
    Comprobante, ComprobanteNoRecibido, ComprobanteRenglon, ComprobanteTipoDeCambio,
)
from entidades.models import Entidad
from liquidaciones.models import LiquidacionComprobante
from retenciones.models import RetencionRenglon

# Campos que nunca se copian del CSV al original.
NO_COPIAR = {'id', 'entidad_emisor', 'fecha_agregado', 'agregado_desde'}
# Siempre se toman del CSV (el original tenía mal el tipo).
SIEMPRE_DEL_CSV = {'tipo_comprobante', 'comprobante_string'}


def _vacio(campo, valor):
    if valor is None or valor == '':
        return True
    if campo != 'es_emisor' and isinstance(valor, (int, float, Decimal)) and valor == 0:
        return True
    return False


class Command(BaseCommand):
    help = 'Fusiona comprobantes duplicados (cargado a mano + importado del CSV de AFIP) de una entidad.'

    def add_arguments(self, parser):
        parser.add_argument('--entidad', type=int, required=True)
        parser.add_argument('--numero', type=int, help='Sólo este número de comprobante.')
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **o):
        entidad = Entidad.objects.filter(pk=o['entidad']).first()
        if not entidad:
            raise CommandError(f'No existe la entidad {o["entidad"]}.')
        self.stdout.write(f'Entidad: {entidad.id} - {entidad.nombre}\n')

        qs = Comprobante.objects.filter(entidad_emisor_id=entidad.id, numero__isnull=False)
        if o.get('numero'):
            qs = qs.filter(numero=o['numero'])
        grupos = defaultdict(list)
        for c in qs.order_by('id'):
            grupos[c.numero].append(c)

        # El duplicado del CSV puede haber quedado SIN entidad o con OTRA
        # entidad (si el importador no la pudo asociar). Se suman los
        # comprobantes con el mismo número que sean "de esta entidad" por:
        # mismo CUIT, o entidad_nombre parecido (sin entidad o con otra).
        palabras = [p for p in (entidad.nombre or '').upper().replace('.', ' ').split()
                    if len(p) > 3 and p not in ('SOCIEDAD', 'ANONIMA', 'LIMITADA')]
        cuit = ''.join(ch for ch in (entidad.cuit or '') if ch.isdigit())
        ids_mismo_cuit = [e.id for e in Entidad.objects.exclude(pk=entidad.id).exclude(cuit__isnull=True).exclude(cuit='')
                          if cuit and ''.join(ch for ch in e.cuit if ch.isdigit()) == cuit]
        extra = Q(entidad_emisor_id__in=ids_mismo_cuit) if ids_mismo_cuit else Q(pk__in=[])
        if palabras:
            extra |= Q(entidad_nombre__icontains=palabras[0])
        ya = {c.id for lista in grupos.values() for c in lista}
        numeros = list(grupos.keys())
        for i in range(0, len(numeros), 500):
            for c in (Comprobante.objects.filter(numero__in=numeros[i:i + 500]).filter(extra)
                      .exclude(id__in=ya).order_by('id')):
                c.otra_entidad = True
                grupos[c.numero].append(c)

        if o.get('numero'):
            todos = list(Comprobante.objects.filter(numero=o['numero']).order_by('id'))
            nombres = dict(Entidad.objects.filter(id__in={c.entidad_emisor_id for c in todos if c.entidad_emisor_id})
                           .values_list('id', 'nombre'))
            self.stdout.write(f'Todos los comprobantes con nº {o["numero"]} en la base: {len(todos)}')
            for c in todos:
                self.stdout.write(
                    f'  id {c.id}  entidad {c.entidad_emisor_id} ({nombres.get(c.entidad_emisor_id, "-")})  '
                    f'nombre CSV "{c.entidad_nombre or ""}"  pv {c.punto_de_venta}  tipo {c.tipo_comprobante_id}  '
                    f'fecha {c.fecha}  total {c.total}  es_emisor={c.es_emisor}  cargado {c.fecha_agregado or "-"}'
                )
            self.stdout.write('')

        campos = [f for f in Comprobante._meta.concrete_fields if f.name not in NO_COPIAR]
        pares, raros = [], []
        for numero, lista in sorted(grupos.items()):
            if len(lista) < 2:
                continue
            pvs = {c.punto_de_venta for c in lista if c.punto_de_venta}
            if len(lista) > 2 or len(pvs) > 1:
                raros.append((numero, lista))
                continue
            a, b = lista
            # Original = el cargado a mano: sin fecha_agregado (anterior a hoy); si no, el de id menor.
            if a.fecha_agregado is None and b.fecha_agregado is not None:
                orig, dup = a, b
            elif b.fecha_agregado is None and a.fecha_agregado is not None:
                orig, dup = b, a
            else:
                orig, dup = (a, b) if a.id < b.id else (b, a)
            if getattr(orig, 'otra_entidad', False) and not getattr(dup, 'otra_entidad', False):
                # El "original" tiene que ser el de esta entidad.
                orig, dup = dup, orig
            pares.append((orig, dup))

        def tipo_txt(c):
            return str(c.tipo_comprobante) if c.tipo_comprobante_id else '-'

        listos = []
        for orig, dup in pares:
            self.stdout.write(
                f'Nº {orig.numero}  pv {orig.punto_de_venta or dup.punto_de_venta}:  '
                f'ORIGINAL id {orig.id} ({tipo_txt(orig)}, {orig.fecha}, total {orig.total}, es_emisor={orig.es_emisor})  '
                f'<- DUPLICADO CSV id {dup.id} ({tipo_txt(dup)}, {dup.fecha}, total {dup.total}, es_emisor={dup.es_emisor})'
                + (f'  [el duplicado tenía entidad {dup.entidad_emisor_id or "VACÍA"}]' if getattr(dup, 'otra_entidad', False) else '')
            )
            cambios, conflictos = {}, []
            for f in campos:
                vo, vd = getattr(orig, f.attname), getattr(dup, f.attname)
                if f.name in SIEMPRE_DEL_CSV:
                    if vd not in (None, '') and vo != vd:
                        cambios[f.attname] = vd
                elif _vacio(f.name, vo) and not _vacio(f.name, vd):
                    cambios[f.attname] = vd
                elif not _vacio(f.name, vo) and not _vacio(f.name, vd) and vo != vd:
                    if isinstance(vo, (int, float, Decimal)) and isinstance(vd, (int, float, Decimal)) \
                            and abs(Decimal(str(vo)) - Decimal(str(vd))) < Decimal('0.01'):
                        continue
                    conflictos.append(f'{f.name}: original={vo!r} / CSV={vd!r}')

            # Dependencias del duplicado
            bloqueos = []
            ren_dup = ComprobanteRenglon.objects.filter(comprobante=dup).count()
            ren_orig = ComprobanteRenglon.objects.filter(comprobante=orig).count()
            if ren_dup and ren_orig:
                bloqueos.append(f'los dos tienen renglones (original {ren_orig}, CSV {ren_dup})')
            liq_dup = list(LiquidacionComprobante.objects.filter(comprobante=dup).select_related('liquidacion'))
            tipo_esperado = 'cobro' if orig.es_emisor == 0 else 'pago'
            liq_otro_tipo = [lc for lc in liq_dup if lc.liquidacion.tipo != tipo_esperado]
            if liq_otro_tipo:
                bloqueos.append(
                    'el duplicado está en una liquidación de ' + ', '.join(
                        f'{lc.liquidacion.tipo} id {lc.liquidacion_id} (nº {lc.liquidacion.numero})' for lc in liq_otro_tipo)
                    + f' pero el original corresponde a {tipo_esperado}: revisar/eliminar esa liquidación primero')
            liq_orig = set(LiquidacionComprobante.objects.filter(comprobante=orig).values_list('liquidacion_id', flat=True))
            if liq_dup and liq_orig:
                bloqueos.append('los dos están en liquidaciones: ' + ', '.join(
                    [f'original {i}' for i in liq_orig] + [f'CSV {lc.liquidacion_id}' for lc in liq_dup]))
            ret_dup = RetencionRenglon.objects.filter(comprobante=dup).count()
            ret_orig = RetencionRenglon.objects.filter(comprobante=orig).count()
            if ret_dup and ret_orig:
                bloqueos.append('los dos están vinculados a retenciones')
            tc_dup = ComprobanteTipoDeCambio.objects.filter(comprobante=dup).exists()
            tc_orig = ComprobanteTipoDeCambio.objects.filter(comprobante=orig).exists()
            nr_dup = ComprobanteNoRecibido.objects.filter(comprobante=dup).exists()
            nr_orig = ComprobanteNoRecibido.objects.filter(comprobante=orig).exists()

            for k, v in cambios.items():
                self.stdout.write(f'      completar {k}: {getattr(orig, k)!r} -> {v!r}')
            for x in conflictos:
                self.stdout.write(self.style.WARNING(f'      distinto (no se pisa, revisar): {x}'))
            mover = []
            if ren_dup and not ren_orig:
                mover.append(f'{ren_dup} renglón(es)')
            if liq_dup and not liq_orig:
                mover.append('vínculo a liquidación ' + ', '.join(str(lc.liquidacion_id) for lc in liq_dup))
            if ret_dup and not ret_orig:
                mover.append(f'{ret_dup} vínculo(s) a retenciones')
            if tc_dup and not tc_orig:
                mover.append('tipo de cambio')
            if nr_dup and not nr_orig:
                mover.append('marca NO RECIBIDO')
            if mover:
                self.stdout.write(f'      pasar al original: {", ".join(mover)}')
            if bloqueos:
                self.stdout.write(self.style.ERROR('      NO SE TOCA: ' + '; '.join(bloqueos)))
                continue
            self.stdout.write(f'      se borra el duplicado id {dup.id}')
            listos.append((orig, dup, cambios, tc_dup and not tc_orig, nr_dup and not nr_orig))

        if raros:
            self.stdout.write(self.style.WARNING('\nGrupos que no son un par simple (no se tocan, revisar a mano):'))
            for numero, lista in raros:
                self.stdout.write(self.style.WARNING(
                    f'  Nº {numero}: ' + ', '.join(f'id {c.id} pv {c.punto_de_venta} {tipo_txt(c)} total {c.total}' for c in lista)))

        self.stdout.write(f'\nPares duplicados encontrados: {len(pares)}  -- a fusionar: {len(listos)}')
        if not listos:
            return
        if not o['aplicar']:
            self.stdout.write(self.style.WARNING('\nEsto fue un DRY RUN, no se guardó nada. Volvé a correr con --aplicar para guardar.'))
            return

        with transaction.atomic():
            for orig, dup, cambios, mover_tc, mover_nr in listos:
                if cambios:
                    Comprobante.objects.filter(pk=orig.pk).update(**cambios)
                ComprobanteRenglon.objects.filter(comprobante=dup).update(comprobante=orig)
                LiquidacionComprobante.objects.filter(comprobante=dup).update(comprobante=orig)
                RetencionRenglon.objects.filter(comprobante=dup).update(comprobante=orig)
                if mover_tc:
                    ComprobanteTipoDeCambio.objects.filter(comprobante=dup).update(comprobante=orig)
                else:
                    ComprobanteTipoDeCambio.objects.filter(comprobante=dup).delete()
                if mover_nr:
                    ComprobanteNoRecibido.objects.filter(comprobante=dup).update(comprobante=orig)
                else:
                    ComprobanteNoRecibido.objects.filter(comprobante=dup).delete()
                Comprobante.objects.filter(pk=dup.pk).delete()

        self.stdout.write(self.style.SUCCESS(
            f'\nListo -- se fusionaron {len(listos)} par(es); quedaron sólo los originales con los datos del CSV '
            f'({timezone.now():%Y-%m-%d %H:%M}).'
        ))
