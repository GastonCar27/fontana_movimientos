"""
Diagnóstico (sólo lectura): por qué un comprobante NO aparece para liquidar
en /liquidaciones/alta/?tipo=pago&entidad=<id> (o tipo=cobro).

Para la entidad indicada lista:
  1. los comprobantes cargados con ESA entidad (id_entidad) y, para cada uno,
     si se ofrece o el motivo por el que no aparece:
       - dirección: es_emisor no corresponde al tipo (pago = 1 o vacío,
         cobro = 0);
       - ya está en una liquidación del mismo tipo (dice cuál);
       - está marcado NO RECIBIDO;
  2. comprobantes que parecen ser de esa entidad pero están cargados con
     OTRA entidad o SIN entidad (id_entidad vacío) -- se buscan por el texto
     del nombre (entidad_nombre) y por entidades con el mismo CUIT. Este es el
     caso típico de los importados del CSV de AFIP que no se pudieron
     asociar a la entidad.

Uso:
    python manage.py diagnosticar_pendientes_liquidacion --entidad 40
    python manage.py diagnosticar_pendientes_liquidacion --entidad 40 --tipo cobro
    python manage.py diagnosticar_pendientes_liquidacion --entidad 40 --texto "electricidad"
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from comprobantes.models import Comprobante
from entidades.models import Entidad
from liquidaciones.models import Liquidacion, LiquidacionComprobante


class Command(BaseCommand):
    help = 'Explica por qué los comprobantes de una entidad aparecen o no en el alta de liquidación.'

    def add_arguments(self, parser):
        parser.add_argument('--entidad', type=int, required=True)
        parser.add_argument('--tipo', choices=['pago', 'cobro'], default='pago')
        parser.add_argument('--texto', help='Texto para buscar en entidad_nombre (default: primera palabra significativa del nombre).')

    def handle(self, *args, **o):
        entidad = Entidad.objects.filter(pk=o['entidad']).first()
        if not entidad:
            raise CommandError(f'No existe la entidad {o["entidad"]}.')
        tipo = o['tipo']
        self.stdout.write(f'Entidad: {entidad.id} - {entidad.nombre} (CUIT {entidad.cuit or "-"})   Tipo: {tipo}\n')

        en_liq = {}
        for lc in LiquidacionComprobante.objects.filter(liquidacion__tipo=tipo).select_related('liquidacion'):
            en_liq.setdefault(lc.comprobante_id, []).append(lc.liquidacion)

        def motivo(c):
            motivos = []
            if tipo == 'pago' and c.es_emisor not in (1, None):
                motivos.append(f'es_emisor={c.es_emisor} (es una factura emitida por Fontana: va en COBRO, no en pago)')
            if tipo == 'cobro' and c.es_emisor != 0:
                motivos.append(f'es_emisor={c.es_emisor} (es una factura recibida: va en PAGO, no en cobro)')
            if c.id in en_liq:
                motivos.append('ya está en la liquidación de ' + tipo + ' ' +
                               ', '.join(f'id {l.id} (nº {l.numero}, {l.fecha})' for l in en_liq[c.id]))
            if hasattr(c, 'no_recibido_marca') and c.no_recibido_marca:
                motivos.append('marcado NO RECIBIDO')
            return motivos

        def linea(c, prefijo=''):
            return (f'  {prefijo}id {c.id}  {c.fecha}  {c.comprobante_string or ""}  pv {c.punto_de_venta} nº {c.numero}  '
                    f'total {c.total}  es_emisor={c.es_emisor}  id_entidad={c.entidad_emisor_id}  '
                    f'nombre="{c.entidad_nombre or ""}"  agregado_desde={c.agregado_desde or "-"}')

        def con_marca(qs):
            lista = list(qs.order_by('-fecha', '-id'))
            ids_nr = set(Comprobante.objects.filter(id__in=[c.id for c in lista], no_recibido__isnull=False)
                         .values_list('id', flat=True))
            for c in lista:
                c.no_recibido_marca = c.id in ids_nr
            return lista

        # 1) Cargados con esta entidad
        propios = con_marca(Comprobante.objects.filter(entidad_emisor_id=entidad.id))
        ofrecidos = [c for c in propios if not motivo(c)]
        self.stdout.write(f'1) Comprobantes con id_entidad={entidad.id}: {len(propios)}  -- se ofrecen en el alta: {len(ofrecidos)}')
        for c in propios:
            m = motivo(c)
            self.stdout.write(linea(c, 'OK   ' if not m else 'NO   '))
            for x in m:
                self.stdout.write(self.style.WARNING(f'         -> {x}'))

        # 2) Posibles comprobantes de esta entidad cargados con otra entidad o sin entidad
        texto = o.get('texto')
        if not texto:
            palabras = [p for p in (entidad.nombre or '').split() if len(p) > 3 and p.upper() not in ('S.A.', 'SRL', 'S.R.L.', 'SOCIEDAD', 'ANONIMA')]
            texto = palabras[0] if palabras else (entidad.nombre or '')
        mismas_cuit = []
        if entidad.cuit:
            cuit_limpio = ''.join(ch for ch in entidad.cuit if ch.isdigit())
            mismas_cuit = [e for e in Entidad.objects.exclude(pk=entidad.id).exclude(cuit__isnull=True).exclude(cuit='')
                           if ''.join(ch for ch in e.cuit if ch.isdigit()) == cuit_limpio]
        filtro = Q(entidad_nombre__icontains=texto)
        if mismas_cuit:
            filtro |= Q(entidad_emisor_id__in=[e.id for e in mismas_cuit])
        otros = con_marca(Comprobante.objects.filter(filtro).exclude(entidad_emisor_id=entidad.id))
        self.stdout.write(f'\n2) Comprobantes que parecen de esta entidad pero con OTRA entidad o SIN entidad '
                          f'(nombre contiene "{texto}"' + (f' o entidad con el mismo CUIT: {", ".join(f"{e.id}-{e.nombre}" for e in mismas_cuit)}' if mismas_cuit else '') +
                          f'): {len(otros)}')
        for c in otros:
            self.stdout.write(self.style.WARNING(linea(c)))
        if otros:
            self.stdout.write(self.style.WARNING(
                '   -> Estos NO aparecen en el alta de la entidad porque id_entidad no es '
                f'{entidad.id}. Hay que asignarles la entidad correcta (Editar comprobante) '
                'o usar el buscador de "otros comprobantes" de la liquidación.'
            ))
