"""
Acceso a datos de Liquidaciones (tabla `liquidacion` + las 4 tablas
intermedias `liquidacion_movimiento` / `liquidacion_comprobante` /
`liquidacion_retencion` / `liquidacion_retencion_inym`), alcance
genérico -- mismo subconjunto que las vistas Django `liquidaciones.views.
liquidacion_form` / `liquidacion_list` / `liquidacion_eliminar`.

Una Liquidación es una cabecera (número, fecha, entidad, debe, haber) más
una selección libre de ítems de las otras 4 tablas (Movimientos de Caja
recibidos de esa entidad, Comprobantes emitidos por ella, Retenciones y
Retenciones INYM de esa entidad) marcados cada uno como 'debe' o 'haber'.
debe/haber de la cabecera NUNCA se cargan a mano -- se recalculan siempre
sumando los ítems vinculados (ver `recalcular_totales`, réplica de
`Liquidacion.recalcular_totales()` en Django), que es la única fuente de
verdad tanto ahí como acá.

Fuera de alcance por ahora (ver README.md): el apartado "Otros
movimientos/comprobantes" de Django (agregar a mano, desde el buscador
global, un ítem de OTRA entidad a la liquidación -- por ejemplo para
aplicar un cheque recibido de un tercero), la impresión de una liquidación
puntual en PDF/Excel (`liquidaciones/documentos.py` del lado Django, un
formato de recibo con membrete) y los reportes/rankings/exportaciones
(`liquidacion_reporte`, `liquidacion_ranking_entidades`).

Igual que el resto de las tablas legadas (`entidad`, `movimiento_caja`,
`comprobante`, `retencion`...), `liquidacion` no es AUTO_INCREMENT real --
se calcula MAX(id)+1 a mano, igual que `_siguiente_id_liquidacion` en
`liquidaciones/views.py`.
"""
from decimal import Decimal

from db import get_connection

SQL_LISTAR = """
    SELECT l.id, l.numero, l.fecha, l.debe, l.haber,
           l.id_entidad, e.nombre AS entidad_nombre, e.cuit AS entidad_cuit
      FROM liquidacion l
      LEFT JOIN entidad e ON e.id = l.id_entidad
"""

# categoria -> (tabla intermedia, columna que apunta al ítem)
CATEGORIAS = {
    'mov': ('liquidacion_movimiento', 'id_movimiento'),
    'comp': ('liquidacion_comprobante', 'id_comprobante'),
    'ret': ('liquidacion_retencion', 'id_retencion'),
    'retinym': ('liquidacion_retencion_inym', 'id_retencion_inym'),
}


def _con_diferencia(fila):
    debe = fila['debe'] or Decimal('0')
    haber = fila['haber'] or Decimal('0')
    fila['diferencia'] = debe - haber
    return fila


def listar(filtro_entidad='', filtro_id='', filtro_fecha=''):
    condiciones = []
    parametros = []
    if filtro_entidad:
        comodin = f'%{filtro_entidad}%'
        condiciones.append('(e.nombre LIKE %s OR e.cuit LIKE %s)')
        parametros.extend([comodin, comodin])
    if filtro_id:
        if not filtro_id.isdigit():
            return []
        condiciones.append('l.id = %s')
        parametros.append(int(filtro_id))
    if filtro_fecha:
        condiciones.append('l.fecha = %s')
        parametros.append(filtro_fecha)

    sql = SQL_LISTAR
    if condiciones:
        sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' ORDER BY l.fecha DESC, l.id DESC LIMIT 300'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            filas = cur.fetchall()
    finally:
        conn.close()
    return [_con_diferencia(f) for f in filas]


def obtener(liquidacion_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_LISTAR + ' WHERE l.id = %s', (liquidacion_id,))
            fila = cur.fetchone()
    finally:
        conn.close()
    return _con_diferencia(fila) if fila else None


def _siguiente_id(cur):
    cur.execute('SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM liquidacion')
    return cur.fetchone()['siguiente']


def _excluidos(cur, categoria, liquidacion_id):
    """Ids de ítems de esa categoría ya vinculados a OTRA liquidación (o a
    cualquiera, si liquidacion_id es None -- alta nueva)."""
    tabla, columna = CATEGORIAS[categoria]
    sql = f'SELECT {columna} AS item_id FROM {tabla}'
    parametros = []
    if liquidacion_id:
        sql += ' WHERE id_liquidacion <> %s'
        parametros.append(liquidacion_id)
    cur.execute(sql, parametros)
    return {r['item_id'] for r in cur.fetchall()}


def _tipo_actual(cur, categoria, liquidacion_id):
    """{item_id: 'debe'|'haber'} de los ítems YA vinculados a ESTA
    liquidación (modo edición) -- para preseleccionarlos en la pantalla."""
    if not liquidacion_id:
        return {}
    tabla, columna = CATEGORIAS[categoria]
    cur.execute(
        f'SELECT {columna} AS item_id, tipo FROM {tabla} WHERE id_liquidacion = %s',
        (liquidacion_id,),
    )
    return {r['item_id']: r['tipo'] for r in cur.fetchall()}


def _monto_comprobante(cur, comprobante_id, total):
    """Igual que _monto_item en Django: si el comprobante tiene tipo de
    cambio cargado (moneda distinta a pesos), el total se multiplica por
    ese tipo de cambio; si no, queda igual."""
    cur.execute('SELECT tipo_de_cambio FROM comprobante_tipo_de_cambio WHERE id = %s', (comprobante_id,))
    fila = cur.fetchone()
    factor = fila['tipo_de_cambio'] if fila else Decimal('1')
    return (total or Decimal('0')) * factor


def items_disponibles(entidad_id, liquidacion_id=None):
    """Réplica de `liquidaciones.views._armar_items` (sin el apartado
    "otros movimientos/comprobantes" de otra entidad -- ver docstring del
    módulo): para la entidad dada, los ítems de las 4 categorías que no
    están en OTRA liquidación, más -- en modo edición -- los que ya están
    en ESTA, marcados con su 'tipo_actual'. Devuelve un dict
    {categoria: [ {id, fecha, monto, descripcion, tipo_actual}, ... ]}."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            resultado = {}

            # --- Movimientos de Caja recibidos de esta entidad ---
            excl = _excluidos(cur, 'mov', liquidacion_id)
            tipo_actual = _tipo_actual(cur, 'mov', liquidacion_id)
            cur.execute(
                """
                SELECT mc.id, mc.emision AS fecha, mc.monto AS monto,
                       t.nombre AS tipo_nombre, n.numero
                  FROM movimiento_caja mc
                  LEFT JOIN bancocuenta_tipomovim t ON t.id = mc.id_tipoMov
                  LEFT JOIN movimiento_caja_numero n ON n.id = mc.id
                 WHERE mc.id_entidad = %s
                 ORDER BY mc.emision DESC
                """,
                (entidad_id,),
            )
            filas = [f for f in cur.fetchall() if f['id'] not in excl]
            for f in filas:
                f['tipo_actual'] = tipo_actual.get(f['id'])
                numero = f['numero'] if f['numero'] is not None else 's/n'
                f['descripcion'] = f"{f['tipo_nombre'] or 'Movimiento'} N° {numero}"
            resultado['mov'] = filas

            # --- Comprobantes emitidos por esta entidad ---
            excl = _excluidos(cur, 'comp', liquidacion_id)
            tipo_actual = _tipo_actual(cur, 'comp', liquidacion_id)
            cur.execute(
                """
                SELECT c.id, c.fecha AS fecha, c.total AS total,
                       c.punto_de_venta, c.numero, ct.nombre AS tipo_comprobante_nombre
                  FROM comprobante c
                  LEFT JOIN comprobante_tipo ct ON ct.id = c.id_tipo_comp
                 WHERE c.id_entidad = %s
                 ORDER BY c.fecha DESC
                """,
                (entidad_id,),
            )
            filas = [f for f in cur.fetchall() if f['id'] not in excl]
            for f in filas:
                monto = _monto_comprobante(cur, f['id'], f['total'])
                es_nc = f['tipo_comprobante_nombre'] and 'nota de credito' in f['tipo_comprobante_nombre'].lower()
                f['monto'] = -monto if es_nc else monto
                f['tipo_actual'] = tipo_actual.get(f['id'])
                pv = f['punto_de_venta'] if f['punto_de_venta'] is not None else '-'
                nro = f['numero'] if f['numero'] is not None else '-'
                f['descripcion'] = f"{f['tipo_comprobante_nombre'] or 'Comprobante'} {pv}-{nro}"
            resultado['comp'] = filas

            # --- Retenciones de esta entidad ---
            excl = _excluidos(cur, 'ret', liquidacion_id)
            tipo_actual = _tipo_actual(cur, 'ret', liquidacion_id)
            cur.execute(
                'SELECT id, fecha, total, `año` AS anio, numero FROM retencion WHERE id_entidad = %s ORDER BY fecha DESC',
                (entidad_id,),
            )
            filas = [f for f in cur.fetchall() if f['id'] not in excl]
            for f in filas:
                f['monto'] = f['total']
                f['tipo_actual'] = tipo_actual.get(f['id'])
                f['descripcion'] = f"Retención {f['anio']}-{f['numero']}"
            resultado['ret'] = filas

            # --- Retenciones INYM de esta entidad (vía operador_retenido) ---
            excl = _excluidos(cur, 'retinym', liquidacion_id)
            tipo_actual = _tipo_actual(cur, 'retinym', liquidacion_id)
            cur.execute(
                """
                SELECT ri.id, ri.fecha, ri.total
                  FROM retencion_inym ri
                  JOIN inym_operador op ON op.id = ri.id_operador_retenido
                 WHERE op.id_entidad = %s
                 ORDER BY ri.fecha DESC
                """,
                (entidad_id,),
            )
            filas = [f for f in cur.fetchall() if f['id'] not in excl]
            for f in filas:
                f['monto'] = f['total']
                f['tipo_actual'] = tipo_actual.get(f['id'])
                f['descripcion'] = f"Retención INYM #{f['id']}"
            resultado['retinym'] = filas

            return resultado
    finally:
        conn.close()


def guardar(liquidacion_id, fecha, entidad_id, numero, selecciones):
    """selecciones: lista de (categoria, item_id, tipo) con tipo en
    ('debe', 'haber'). Si liquidacion_id es None, crea una liquidación
    nueva; si no, reemplaza sus 4 vínculos por los de `selecciones`
    (borra todo y recrea, igual que `liquidaciones.views.liquidacion_
    form`). Siempre termina recalculando debe/haber desde la base -- nunca
    se cargan a mano. Devuelve el id de la liquidación (nuevo o el mismo
    que se pasó)."""
    if not selecciones:
        raise ValueError('Debe seleccionar al menos un ítem para la liquidación.')

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if liquidacion_id is None:
                nuevo_id = _siguiente_id(cur)
                numero_final = numero or f'LIQ-{nuevo_id}'
                cur.execute(
                    'INSERT INTO liquidacion (id, numero, fecha, id_entidad) VALUES (%s, %s, %s, %s)',
                    (nuevo_id, numero_final, fecha, entidad_id),
                )
                liquidacion_id = nuevo_id
            else:
                for tabla, _columna in CATEGORIAS.values():
                    cur.execute(f'DELETE FROM {tabla} WHERE id_liquidacion = %s', (liquidacion_id,))
                numero_final = numero or f'LIQ-{liquidacion_id}'
                cur.execute(
                    'UPDATE liquidacion SET numero=%s, fecha=%s, id_entidad=%s WHERE id=%s',
                    (numero_final, fecha, entidad_id, liquidacion_id),
                )

            for categoria, item_id, tipo in selecciones:
                tabla, columna = CATEGORIAS[categoria]
                cur.execute(
                    f'INSERT INTO {tabla} (id_liquidacion, {columna}, tipo) VALUES (%s, %s, %s)',
                    (liquidacion_id, item_id, tipo),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    recalcular_totales(liquidacion_id)
    return liquidacion_id


def recalcular_totales(liquidacion_id):
    """Única fuente de verdad para debe/haber de una liquidación -- réplica
    de `Liquidacion.recalcular_totales()` en Django: suma, por cada una de
    las 4 tablas intermedias, los montos marcados 'debe' y los marcados
    'haber' (con la conversión de moneda y el signo de Nota de Crédito
    para comprobantes, igual que en `items_disponibles`), y actualiza la
    cabecera. Devuelve (debe, haber), ya redondeados a 2 decimales."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            total_debe = Decimal('0')
            total_haber = Decimal('0')

            cur.execute(
                """
                SELECT lm.tipo, mc.monto AS monto
                  FROM liquidacion_movimiento lm
                  JOIN movimiento_caja mc ON mc.id = lm.id_movimiento
                 WHERE lm.id_liquidacion = %s
                """,
                (liquidacion_id,),
            )
            for fila in cur.fetchall():
                monto = fila['monto'] or Decimal('0')
                if fila['tipo'] == 'debe':
                    total_debe += monto
                elif fila['tipo'] == 'haber':
                    total_haber += monto

            cur.execute(
                """
                SELECT lc.tipo, lc.id_comprobante AS comprobante_id, c.total AS total,
                       ct.nombre AS tipo_nombre
                  FROM liquidacion_comprobante lc
                  JOIN comprobante c ON c.id = lc.id_comprobante
                  LEFT JOIN comprobante_tipo ct ON ct.id = c.id_tipo_comp
                 WHERE lc.id_liquidacion = %s
                """,
                (liquidacion_id,),
            )
            for fila in cur.fetchall():
                monto = _monto_comprobante(cur, fila['comprobante_id'], fila['total'])
                if fila['tipo_nombre'] and 'nota de credito' in fila['tipo_nombre'].lower():
                    monto = -monto
                if fila['tipo'] == 'debe':
                    total_debe += monto
                elif fila['tipo'] == 'haber':
                    total_haber += monto

            cur.execute(
                """
                SELECT lr.tipo, r.total AS total
                  FROM liquidacion_retencion lr
                  JOIN retencion r ON r.id = lr.id_retencion
                 WHERE lr.id_liquidacion = %s
                """,
                (liquidacion_id,),
            )
            for fila in cur.fetchall():
                monto = fila['total'] or Decimal('0')
                if fila['tipo'] == 'debe':
                    total_debe += monto
                elif fila['tipo'] == 'haber':
                    total_haber += monto

            cur.execute(
                """
                SELECT lri.tipo, ri.total AS total
                  FROM liquidacion_retencion_inym lri
                  JOIN retencion_inym ri ON ri.id = lri.id_retencion_inym
                 WHERE lri.id_liquidacion = %s
                """,
                (liquidacion_id,),
            )
            for fila in cur.fetchall():
                monto = fila['total'] or Decimal('0')
                if fila['tipo'] == 'debe':
                    total_debe += monto
                elif fila['tipo'] == 'haber':
                    total_haber += monto

            total_debe = total_debe.quantize(Decimal('0.01'))
            total_haber = total_haber.quantize(Decimal('0.01'))
            cur.execute(
                'UPDATE liquidacion SET debe=%s, haber=%s WHERE id=%s',
                (total_debe, total_haber, liquidacion_id),
            )
        conn.commit()
        return total_debe, total_haber
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def eliminar(liquidacion_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for tabla, _columna in CATEGORIAS.values():
                cur.execute(f'DELETE FROM {tabla} WHERE id_liquidacion = %s', (liquidacion_id,))
            cur.execute('DELETE FROM liquidacion WHERE id = %s', (liquidacion_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
