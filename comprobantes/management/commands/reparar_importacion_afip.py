"""
Reparación (pedido de Gastón, 06/10/2026) de comprobantes DUPLICADOS y con
TIPO EQUIVOCADO, usando como referencia los archivos de "Mis comprobantes"
de AFIP.

Qué pasó:
  * La primera versión del importador de AFIP (agregado_desde =
    'AFIP importador') tomaba el código AFIP del tipo como si fuera el ID de
    la tabla de tipos, y en esta base no siempre coinciden:
        código 6 (Factura B)        -> ID 7   (el ID 6 es RECIBO C)
        código 2 (Nota de Débito A) -> ID 3   (el ID 2 es Nota de Crédito A)
        código 3 (Nota de Crédito A)-> ID 2   (el ID 3 es Nota de Débito A)
        código 11 / 13 / 15         -> ID 4 / 5 / 6
    Además no reconoció comprobantes que YA estaban cargados (con otra
    entidad, o sin entidad, o con el DNI en el campo CUIT) y los cargó de
    nuevo: quedaron duplicados.
  * La carga anterior "csv" ya tenía el mismo problema de tipo en parte de
    sus comprobantes (Facturas B como RECIBO C, NC A / ND A invertidas) y
    tiques cargados dos o tres veces.

Criterio: cada fila del archivo de AFIP es UN comprobante. Todos los
comprobantes del sistema con el mismo número, la misma fecha, el mismo total
y el mismo punto de venta (o sin punto de venta) son ese mismo comprobante.

Para cada fila de AFIP:
  1. Si hay más de uno en el sistema, se deja UNO: el que no vino del
     importador nuevo, el que está en una liquidación / tiene renglones o
     retenciones, y si no el de ID menor. A ese se le completan los datos
     vacíos con los de los otros, se le pasa lo que cuelgue de los otros
     (renglones, liquidaciones, retenciones, tipo de cambio, marca no
     recibido) y los otros se borran. Si más de uno está en liquidaciones,
     tiene renglones o retenciones, ese caso NO se toca y se informa.
  2. Al que queda se le pone el tipo que corresponde al código AFIP (por la
     columna id_afip de la tabla de tipos) y se le rearma el texto.
  3. Si quién lo emitió (es_emisor) no coincide con el archivo, se corrige,
     salvo que esté en una liquidación del tipo contrario (se informa).
Entidades:
  4. Las entidades que creó el importador y quedaron duplicando a una que ya
     estaba (mismo nombre, cargada sin documento) se unen a la que estaba
     (se le carga el DNI) y se borran. Las que quedan vacías y sin uso en
     ninguna otra tabla, se borran.

Por defecto es DRY RUN. Pasar --aplicar para guardar.

Uso:
    python manage.py reparar_importacion_afip --csv "afip_csv/recibidos.csv" --csv "afip_csv/emitidos.csv"
    python manage.py reparar_importacion_afip --csv ... --csv ... --detalle
    python manage.py reparar_importacion_afip --csv ... --csv ... --aplicar
"""
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from comprobantes.importador_afip import (
    _comprobante_string, _cuit_valido, _nombre_clave, _solo_digitos, leer_filas, tipos_por_codigo_afip,
)
from comprobantes.models import (
    Comprobante, ComprobanteNoRecibido, ComprobanteRenglon, ComprobanteTipo, ComprobanteTipoDeCambio,
)
from entidades.models import Entidad
from liquidaciones.models import LiquidacionComprobante
from retenciones.models import RetencionRenglon

VIEJO = 'AFIP importador'
NO_COPIAR = {'id', 'tipo_comprobante', 'fecha_agregado', 'agregado_desde', 'comprobante_string', 'es_emisor'}
CENT = Decimal('0.01')


def _vacio(valor):
    if valor is None or valor == '':
        return True
    if isinstance(valor, (int, float, Decimal)) and valor == 0:
        return True
    return False


def _q(total):
    return Decimal(str(total)).quantize(CENT) if total is not None else None


class Command(BaseCommand):
    help = 'Repara comprobantes duplicados y con tipo equivocado usando los archivos de AFIP como referencia.'

    def add_arguments(self, parser):
        parser.add_argument('--csv', action='append', default=[], required=True,
                            help='Archivo de "Mis comprobantes" de AFIP (recibidos o emitidos). Se puede repetir.')
        parser.add_argument('--aplicar', action='store_true')
        parser.add_argument('--detalle', action='store_true', help='Listar cada caso (por defecto, resumen).')

    def p(self, txt=''):
        self.stdout.write(txt)

    def handle(self, *args, **o):
        por_codigo = tipos_por_codigo_afip()
        tipos = {t.id: t for t in ComprobanteTipo.objects.all()}

        def tnom(tid):
            t = tipos.get(tid)
            return f'{tid} - {t.nombre.strip()}' if t else f'{tid} - ?'

        cruzados = {cod: t for cod, t in por_codigo.items() if t.id != cod}
        self.p('Tipos cuyo código AFIP no es su ID:')
        for cod, t in sorted(cruzados.items()):
            self.p(f'  código AFIP {cod:>3} -> {tnom(t.id)}   (el ID {cod} es {tnom(cod) if cod in tipos else "inexistente"})')

        # ---------------- Leer los archivos de AFIP ----------------
        filas_afip = []
        cuit_propio = _solo_digitos(Entidad.objects.filter(pk=100).values_list('cuit', flat=True).first() or '')
        for ruta in o['csv']:
            path = Path(ruta)
            if not path.exists():
                raise CommandError(f'No existe el archivo {ruta}')
            with open(path, 'rb') as fh:
                filas, mapa = leer_filas(fh, path.name)
            nombre = path.name.lower()
            for f in filas:
                if f.get('errores') or f.get('numero') is None or f.get('total') is None:
                    continue
                if 'emitidos' in nombre or ('nro_doc_emisor' not in mapa):
                    es_emisor = 0
                elif 'recibidos' in nombre or ('nro_doc_receptor' not in mapa):
                    es_emisor = 1
                else:
                    es_emisor = 0 if (cuit_propio and f.get('cuit_emisor') == cuit_propio) else 1
                f['es_emisor'] = es_emisor
                f['origen'] = f'{path.name} línea {f["linea"]}'
                filas_afip.append(f)
        self.p(f'\nFilas leídas de los archivos de AFIP: {len(filas_afip)}')

        # ---------------- Comprobantes del sistema con esos números ----------------
        numeros = sorted({f['numero'] for f in filas_afip})
        por_clave = defaultdict(list)  # (numero, fecha, total) -> [Comprobante]
        for i in range(0, len(numeros), 1000):
            for c in Comprobante.objects.filter(numero__in=numeros[i:i + 1000]).order_by('id'):
                por_clave[(c.numero, c.fecha, _q(c.total))].append(c)
        ids_todos = [c.id for lst in por_clave.values() for c in lst]
        con_liq, con_ren, con_ret, con_tc, con_nr = set(), set(), set(), set(), set()
        ren_usado, con_otros_trib = set(), set()   # renglones referenciados desde otras tablas
        suma_ren = defaultdict(Decimal)
        liq_tipo = defaultdict(set)
        for i in range(0, len(ids_todos), 2000):
            bloque = ids_todos[i:i + 2000]
            for cid, tipo_liq in LiquidacionComprobante.objects.filter(comprobante_id__in=bloque).values_list(
                    'comprobante_id', 'liquidacion__tipo'):
                con_liq.add(cid)
                liq_tipo[cid].add(tipo_liq)
            ph = ','.join(['%s'] * len(bloque))
            with connection.cursor() as cur:
                cur.execute(f'SELECT id_comprobante, id, total, id_asiento_contable FROM comprobante_renglon '
                            f'WHERE id_comprobante IN ({ph})', bloque)
                renglones = cur.fetchall()
                ren_de = {}
                for cid, rid, tot, asiento in renglones:
                    con_ren.add(cid)
                    suma_ren[cid] += Decimal(str(tot or 0))
                    ren_de[rid] = cid
                    if asiento:
                        ren_usado.add(cid)
                if ren_de:
                    rids = list(ren_de)
                    php = ','.join(['%s'] * len(rids))
                    for tabla, col in (('movimiento_comprobante_renglon', 'id_comprobante_renglon'),
                                       ('solicitud_compra_renglon_comprobante_renglon', 'comprobante_renglon_id'),
                                       ('cta_cte_comprobante_renglon_movimiento', 'renglon_id'),
                                       ('cta_cte_liquidacion_producto_comprobante_renglon', 'renglon_id')):
                        try:
                            cur.execute(f'SELECT DISTINCT {col} FROM {tabla} WHERE {col} IN ({php})', rids)
                            ren_usado.update(ren_de[r[0]] for r in cur.fetchall())
                        except Exception:
                            pass
                try:
                    cur.execute(f'SELECT DISTINCT id_comprobante FROM comprobante_otro_tributo_detalle '
                                f'WHERE id_comprobante IN ({ph})', bloque)
                    con_otros_trib.update(r[0] for r in cur.fetchall())
                except Exception:
                    pass
            con_ret.update(RetencionRenglon.objects.filter(comprobante_id__in=bloque).values_list('comprobante_id', flat=True))
            con_tc.update(ComprobanteTipoDeCambio.objects.filter(comprobante_id__in=bloque).values_list('comprobante_id', flat=True))
            con_nr.update(ComprobanteNoRecibido.objects.filter(comprobante_id__in=bloque).values_list('comprobante_id', flat=True))

        cuit_ent = {}
        ids_ent = {c.entidad_emisor_id for lst in por_clave.values() for c in lst if c.entidad_emisor_id}
        for eid, cuit in Entidad.objects.filter(id__in=ids_ent).values_list('id', 'cuit'):
            d = _solo_digitos(cuit)
            cuit_ent[eid] = d if _cuit_valido(d) else None

        def usado(c):
            # En una liquidación, con retenciones, o con renglones que se usan en otro lado
            # (movimientos, cuenta corriente, solicitudes de compra, asientos).
            return c.id in con_liq or c.id in con_ret or c.id in ren_usado

        # ---------------- Plan ----------------
        fusiones = []      # (keep, [borrar], cambios, fila)
        solo_cambios = []  # (keep, cambios, fila)
        bloqueados = []
        avisos_emisor = []
        sin_match = 0
        usados_ids = set()
        for f in filas_afip:
            tipo_ok = por_codigo.get(f.get('tipo_codigo'))
            # Del mismo tipo: el ID correcto, o el ID = código AFIP (el error de las cargas anteriores).
            tipos_compat = {f.get('tipo_codigo')} | ({tipo_ok.id} if tipo_ok else set())
            grupo = [c for c in por_clave.get((f['numero'], f['fecha'], _q(abs(f['total']))), [])
                     if (c.punto_de_venta in (None, 0) or c.punto_de_venta == f.get('pv')) and c.id not in usados_ids
                     and c.tipo_comprobante_id in tipos_compat]
            if not grupo:
                sin_match += 1
                continue
            usados_ids.update(c.id for c in grupo)
            cuits = {cuit_ent.get(c.entidad_emisor_id) for c in grupo} - {None}
            if len(cuits) > 1:
                bloqueados.append((f, grupo, 'están cargados con entidades de distinto CUIT: ' + ', '.join(sorted(cuits))))
                continue
            con_uso = [c for c in grupo if usado(c)]
            if len(con_uso) > 1:
                bloqueados.append((f, grupo, 'más de uno está en liquidaciones / tiene renglones o retenciones: ' +
                                   ', '.join(str(c.id) for c in con_uso)))
                continue
            grupo_ord = sorted(grupo, key=lambda c: (not usado(c), c.id not in con_ren, c.agregado_desde == VIEJO, c.id))
            keep, borrar = grupo_ord[0], grupo_ord[1:]
            # Si la copia también tiene renglones, tienen que sumar lo mismo (son copias de la misma carga).
            dif = [b for b in borrar if b.id in con_ren and keep.id in con_ren and suma_ren[b.id] != suma_ren[keep.id]]
            if dif:
                bloqueados.append((f, grupo, 'tienen renglones distintos: ' + ', '.join(
                    f'{c.id} suma {suma_ren[c.id]}' for c in [keep] + dif)))
                continue
            cambios = {}
            if tipo_ok and keep.tipo_comprobante_id != tipo_ok.id:
                cambios['tipo_comprobante_id'] = tipo_ok.id
            for otro in borrar:
                for fld in Comprobante._meta.concrete_fields:
                    if fld.name in NO_COPIAR or fld.attname in cambios:
                        continue
                    if _vacio(getattr(keep, fld.attname)) and not _vacio(getattr(otro, fld.attname)):
                        cambios[fld.attname] = getattr(otro, fld.attname)
            if keep.es_emisor != f['es_emisor']:
                contrario = 'cobro' if keep.es_emisor == 0 else 'pago'
                if contrario in liq_tipo.get(keep.id, set()):
                    avisos_emisor.append((keep, f, contrario))
                else:
                    cambios['es_emisor'] = f['es_emisor']
            if borrar:
                fusiones.append((keep, borrar, cambios, f))
            elif cambios:
                solo_cambios.append((keep, cambios, f))

        # Copias del importador viejo que no aparecen en ningún archivo: sólo se corrige el tipo.
        huerfanas = []
        for c in Comprobante.objects.filter(agregado_desde=VIEJO).exclude(id__in=usados_ids):
            t = por_codigo.get(c.tipo_comprobante_id)
            if t and t.id != c.tipo_comprobante_id:
                huerfanas.append((c, t))

        # ---------------- Entidades ----------------
        ids_borrar = {b.id for _, bs, _, _ in fusiones for b in bs}
        ent_importador = set(Comprobante.objects.filter(agregado_desde=VIEJO).exclude(
            entidad_emisor_id__isnull=True).values_list('entidad_emisor_id', flat=True).distinct())
        # Creada por el importador: sólo tiene comprobantes del importador y nada más cargado que
        # nombre + CUIT o DNI (el importador no carga dirección, localidad, IVA, etc.).
        creadas = {e.id for e in Entidad.objects.filter(id__in=ent_importador)
                   if not any([e.direccion, e.localidad, e.codpos, e.iva, e.provincia, e.codigo])
                   and not Comprobante.objects.filter(entidad_emisor_id=e.id).exclude(agregado_desde=VIEJO).exists()}
        ents = {e.id: e for e in Entidad.objects.filter(id__in=creadas)}
        # Cuando el original queda con una entidad vieja y la copia tenía una creada por el importador con
        # documento: se le carga el documento a la vieja (si no lo tiene).
        doc_a_vieja = {}
        for keep, borrar, cambios, f in fusiones:
            eid_keep = cambios.get('entidad_emisor_id', keep.entidad_emisor_id)
            for b in borrar:
                if (b.entidad_emisor_id in creadas and eid_keep and eid_keep != b.entidad_emisor_id
                        and ents[b.entidad_emisor_id].documento_nro):
                    doc_a_vieja.setdefault(eid_keep, ents[b.entidad_emisor_id])
        # Entidades creadas con un gemelo por nombre (cargado sin documento) -> unificar
        sin_doc = defaultdict(list)
        for e in Entidad.objects.filter(documento_nro__isnull=True).exclude(id__in=creadas):
            if not _cuit_valido(_solo_digitos(e.cuit)) and _nombre_clave(e.nombre):
                sin_doc[_nombre_clave(e.nombre)].append(e)
        unificar = {}
        for eid in creadas:
            k = _nombre_clave(ents[eid].nombre)
            if k and len(sin_doc.get(k, [])) == 1:
                unificar[eid] = sin_doc[k][0]

        # ---------------- Informe ----------------
        n_borrar = sum(len(bs) for _, bs, _, _ in fusiones)
        self.p(f'Filas de AFIP que no están en el sistema (no se hace nada): {sin_match}')
        self.p(f'\n1. DUPLICADOS: {len(fusiones)} comprobantes cargados más de una vez -> se borran {n_borrar} copias')
        por_origen = Counter()
        for keep, borrar, _, _ in fusiones:
            for b in borrar:
                por_origen[(b.agregado_desde or '-', tnom(b.tipo_comprobante_id))] += 1
        for (orig, tn), n in sorted(por_origen.items(), key=lambda x: -x[1]):
            self.p(f'   {n:>6} copias cargadas por "{orig}" como {tn}')
        lista = fusiones if o['detalle'] else fusiones[:10]
        for keep, borrar, cambios, f in lista:
            self.p(f'     queda {keep.id} ({tnom(keep.tipo_comprobante_id)}, ent {keep.entidad_emisor_id}, '
                   f'{keep.agregado_desde})  se borra {", ".join(str(b.id) for b in borrar)}  -- nº {f["pv"]}-{f["numero"]} '
                   f'{f["fecha"]} ${abs(f["total"])}' + (f' | cambia: {", ".join(cambios)}' if cambios else ''))
        if not o['detalle'] and len(fusiones) > 10:
            self.p(f'     ... y {len(fusiones) - 10} más (--detalle para ver todos)')

        cambios_tipo = Counter()
        for keep, borrar, cambios, f in fusiones:
            if 'tipo_comprobante_id' in cambios:
                cambios_tipo[(keep.tipo_comprobante_id, cambios['tipo_comprobante_id'])] += 1
        for keep, cambios, f in solo_cambios:
            if 'tipo_comprobante_id' in cambios:
                cambios_tipo[(keep.tipo_comprobante_id, cambios['tipo_comprobante_id'])] += 1
        for c, t in huerfanas:
            cambios_tipo[(c.tipo_comprobante_id, t.id)] += 1
        self.p(f'\n2. TIPO EQUIVOCADO: {sum(cambios_tipo.values())} comprobantes (de los que quedan)')
        for (de, a), n in sorted(cambios_tipo.items()):
            self.p(f'   {n:>6} de "{tnom(de)}"  ->  "{tnom(a)}"')
        if o['detalle']:
            for keep, cambios, f in solo_cambios:
                self.p(f'     {keep.id} nº {f["pv"]}-{f["numero"]} {f["fecha"]} {keep.entidad_nombre or ""}: '
                       + ', '.join(f'{k}: {getattr(keep, k)!r} -> {v!r}' for k, v in cambios.items()))

        n_emisor = sum(1 for _, _, c, _ in fusiones if 'es_emisor' in c) + sum(1 for _, c, _ in solo_cambios if 'es_emisor' in c)
        self.p(f'\n3. QUIÉN LO EMITIÓ corregido según AFIP: {n_emisor}')
        if avisos_emisor:
            self.p(f'   NO se corrigen porque ya están en una liquidación del tipo contrario: {len(avisos_emisor)}')
            for keep, f, tipo_liq in avisos_emisor:
                self.p(f'     {keep.id} nº {f["pv"]}-{f["numero"]} {f["fecha"]} ({keep.entidad_nombre}) está en {tipo_liq}')

        if bloqueados:
            self.p(f'\nNO SE TOCAN (revisar a mano): {len(bloqueados)}')
            for f, grupo, motivo in bloqueados:
                self.p(f'     nº {f["pv"]}-{f["numero"]} {f["fecha"]} ${abs(f["total"])}: ids '
                       f'{", ".join(str(c.id) for c in grupo)} -- {motivo}')

        self.p('\n4. ENTIDADES')
        for eid, vieja in sorted(unificar.items()):
            self.p(f'   la {eid} ({ents[eid].nombre}, DNI {ents[eid].documento_nro}, creada por el importador) se une a '
                   f'la {vieja.id} ({vieja.nombre}) y se borra')
        otras = [(eid, e) for eid, e in doc_a_vieja.items() if e.id not in unificar]
        for eid, e in otras:
            self.p(f'   a la {eid} se le carga el DNI {e.documento_nro} (de la {e.id} {e.nombre}, creada por el importador)')
        self.p(f'   las entidades creadas por el importador que queden sin comprobantes ni otro uso se borran '
               f'(hoy: {len(creadas)} creadas)')

        if not o['aplicar']:
            self.p('\nEsto fue un DRY RUN, no se guardó nada. Volvé a correr con --aplicar para guardar.')
            return

        # ---------------- Aplicar ----------------
        borradas_ent = []
        with transaction.atomic():
            for keep, borrar, cambios, f in fusiones:
                for b in borrar:
                    if keep.id not in con_ren and b.id in con_ren:
                        ComprobanteRenglon.objects.filter(comprobante_id=b.id).update(comprobante_id=keep.id)
                        con_ren.add(keep.id)
                    if keep.id not in con_otros_trib and b.id in con_otros_trib:
                        with connection.cursor() as cur:
                            cur.execute('UPDATE comprobante_otro_tributo_detalle SET id_comprobante=%s '
                                        'WHERE id_comprobante=%s', [keep.id, b.id])
                        con_otros_trib.add(keep.id)
                    LiquidacionComprobante.objects.filter(comprobante_id=b.id).update(comprobante_id=keep.id)
                    RetencionRenglon.objects.filter(comprobante_id=b.id).update(comprobante_id=keep.id)
                    if keep.id in con_tc:
                        ComprobanteTipoDeCambio.objects.filter(comprobante_id=b.id).delete()
                    elif b.id in con_tc:
                        ComprobanteTipoDeCambio.objects.filter(comprobante_id=b.id).update(comprobante_id=keep.id)
                        con_tc.add(keep.id)
                    if keep.id in con_nr:
                        ComprobanteNoRecibido.objects.filter(comprobante_id=b.id).delete()
                    elif b.id in con_nr:
                        ComprobanteNoRecibido.objects.filter(comprobante_id=b.id).update(comprobante_id=keep.id)
                        con_nr.add(keep.id)
                # Los renglones que quedaron en la copia (repetidos de los del original) se borran con ella.
                ComprobanteRenglon.objects.filter(comprobante_id__in=[b.id for b in borrar]).delete()
                Comprobante.objects.filter(id__in=[b.id for b in borrar]).delete()
                self._guardar(keep, cambios, tipos)
            for keep, cambios, f in solo_cambios:
                self._guardar(keep, cambios, tipos)
            for c, t in huerfanas:
                Comprobante.objects.filter(pk=c.pk).update(
                    tipo_comprobante_id=t.id, comprobante_string=_comprobante_string(t, c.punto_de_venta, c.numero))
            for eid, vieja in unificar.items():
                nueva = Entidad.objects.get(pk=eid)
                Comprobante.objects.filter(entidad_emisor_id=eid).update(entidad_emisor_id=vieja.id)
                if nueva.documento_nro and not Entidad.objects.get(pk=vieja.id).documento_nro:
                    Entidad.objects.filter(pk=vieja.id).update(documento_nro=nueva.documento_nro)
            for eid, e in doc_a_vieja.items():
                if e.documento_nro:
                    Entidad.objects.filter(pk=eid, documento_nro__isnull=True).update(documento_nro=e.documento_nro)
            for eid in sorted(creadas):
                e = Entidad.objects.filter(pk=eid).first()
                if e and not Comprobante.objects.filter(entidad_emisor_id=eid).exists() and not self._referencias(e):
                    borradas_ent.append(f'{e.id} - {e.nombre}')
                    e.delete()

        self.p(f'\nListo ({timezone.now():%Y-%m-%d %H:%M}): {n_borrar} copias borradas, '
               f'{sum(cambios_tipo.values())} tipos corregidos, {n_emisor} "quién lo emitió" corregidos, '
               f'{len(borradas_ent)} entidades borradas.')

    def _guardar(self, keep, cambios, tipos):
        if not cambios:
            return
        cambios = dict(cambios)
        if 'tipo_comprobante_id' in cambios:
            cambios['comprobante_string'] = _comprobante_string(
                tipos[cambios['tipo_comprobante_id']], cambios.get('punto_de_venta', keep.punto_de_venta), keep.numero)
        Comprobante.objects.filter(pk=keep.pk).update(**cambios)

    def _referencias(self, entidad):
        """¿La entidad se usa en alguna otra tabla? (si sí, no se borra)."""
        for rel in Entidad._meta.related_objects:
            try:
                if rel.many_to_many:
                    if getattr(entidad, rel.get_accessor_name()).exists():
                        return True
                elif rel.related_model._default_manager.filter(**{rel.field.name: entidad}).exists():
                    return True
            except Exception:
                return True
        return False
