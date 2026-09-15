"""
Acceso a datos de Movimientos de Caja (tabla `movimiento_caja` + sus tablas
relacionadas 1 a 1), alcance genérico: alta, edición, listado/búsqueda y
eliminación -- el mismo subconjunto que las vistas Django
`movimiento_caja_form` / `movimiento_caja_listado` / `movimiento_caja_
eliminar` (módulo "Modificación" de Movimientos de Caja).

Igual que `entidad`, `producto_detalle` y `comprobante`, la columna `id` de
`movimiento_caja` NO es AUTO_INCREMENT real -- el propio modelo Django la
declara `IntegerField(primary_key=True, blank=True)` y calcula `MAX(id)+1`
a mano en su `save()`; acá se replica el mismo criterio.

La cabecera (`MovimientoCajaForm`: caja, tipo, emisión, monto, receptor,
efectivización) va junto con varios datos opcionales que Django guarda en
tablas aparte, 1 a 1 con el movimiento (`MovimientoCajaRelacionadosForm`):
libro/hoja/renglón, número, emisor, fecha de diferido y concepto. Cada uno
se guarda, actualiza o borra independientemente según venga o no completo
en el formulario (mismo criterio `update_or_create` / `delete()` que usa
`movimientos_caja.views.movimiento_caja_form`).

Fuera de alcance por ahora (ver README.md): la cuenta bancaria del
receptor (`movimiento_caja_banco_cuenta_entidad`) y los reportes/rankings/
exportaciones (`movimiento_caja_reporte`, `movimiento_caja_ranking_
entidades`, "Estado de caja").
"""
from db import get_connection

# Mismo tope que RENGLON_MAXIMO_POR_HOJA en movimientos_caja/views.py: al
# llegar a este renglón, el próximo alta (ver siguiente_renglon_y_hoja)
# pasa a renglón 1 de la hoja siguiente.
RENGLON_MAXIMO_POR_HOJA = 25

SQL_BASE = """
    SELECT mc.id, mc.emision, mc.monto, mc.efectivizacion,
           mc.idBancoCuenta AS id_caja, c.nombre AS caja_nombre,
           mc.id_tipoMov AS id_tipo, t.nombre AS tipo_nombre,
           mc.id_entidad AS id_receptor, r.nombre AS receptor_nombre,
           n.numero,
           lm.id_libro, l.nombre AS libro_nombre, lm.hoja, lm.renglon,
           d.diferido,
           me.id_entidad AS id_emisor, em.nombre AS emisor_nombre,
           mcc.id_concepto, ct.nombre AS concepto_nombre
      FROM movimiento_caja mc
      LEFT JOIN bancocuenta c ON c.id = mc.idBancoCuenta
      LEFT JOIN bancocuenta_tipomovim t ON t.id = mc.id_tipoMov
      LEFT JOIN entidad r ON r.id = mc.id_entidad
      LEFT JOIN movimiento_caja_numero n ON n.id = mc.id
      LEFT JOIN bancocuentalibro_movim lm ON lm.id = mc.id
      LEFT JOIN banco_cuenta_libro l ON l.id = lm.id_libro
      LEFT JOIN movimiento_caja_diferido d ON d.id = mc.id
      LEFT JOIN movimiento_caja_emisor me ON me.id = mc.id
      LEFT JOIN entidad em ON em.id = me.id_entidad
      LEFT JOIN movimiento_caja_concepto mcc ON mcc.id = mc.id
      LEFT JOIN movimiento_caja_concepto_tipo ct ON ct.id = mcc.id_concepto
"""


def listar_cajas():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre FROM bancocuenta ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


def listar_tipos_movimiento():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre FROM bancocuenta_tipomovim ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


def listar_conceptos():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre FROM movimiento_caja_concepto_tipo ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


def listar_libros(caja_id=None):
    """Igual que AsignarLibroMovimientoForm: si se pasa una caja, sólo los
    libros de esa caja; si no, todos (para no bloquear la carga mientras el
    usuario todavía no eligió la caja en el formulario de escritorio)."""
    sql = 'SELECT id, nombre, id_bancocuenta FROM banco_cuenta_libro'
    parametros = []
    if caja_id:
        sql += ' WHERE id_bancocuenta = %s'
        parametros.append(caja_id)
    sql += ' ORDER BY nombre'
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.fetchall()
    finally:
        conn.close()


def listar(filtro_receptor='', filtro_id='', filtro_fecha='', filtro_caja='', filtro_numero=''):
    """Subconjunto de los filtros de movimientos_caja.views.movimiento_caja_
    listado (receptor -- acá busca en receptor Y emisor, igual que la web
    --, id, fecha, caja y número); igual que la vista, un id/número no
    numérico no devuelve resultados en vez de fallar. El filtro de monto de
    la web no se replicó todavía (ver README)."""
    condiciones = []
    parametros = []

    if filtro_receptor:
        comodin = f'%{filtro_receptor}%'
        condiciones.append(
            '(r.nombre LIKE %s OR r.cuit LIKE %s OR em.nombre LIKE %s OR em.cuit LIKE %s)'
        )
        parametros.extend([comodin, comodin, comodin, comodin])
    if filtro_id:
        if not filtro_id.isdigit():
            return []
        condiciones.append('mc.id = %s')
        parametros.append(int(filtro_id))
    if filtro_fecha:
        condiciones.append('mc.emision = %s')
        parametros.append(filtro_fecha)
    if filtro_caja:
        if not filtro_caja.isdigit():
            return []
        condiciones.append('mc.idBancoCuenta = %s')
        parametros.append(int(filtro_caja))
    if filtro_numero:
        if not filtro_numero.isdigit():
            return []
        condiciones.append('n.numero = %s')
        parametros.append(int(filtro_numero))

    sql = SQL_BASE
    if condiciones:
        sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' ORDER BY mc.emision DESC, mc.id DESC LIMIT 200'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.fetchall()
    finally:
        conn.close()


def obtener(movimiento_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_BASE + ' WHERE mc.id = %s', (movimiento_id,))
            return cur.fetchone()
    finally:
        conn.close()


def siguiente_renglon_y_hoja(ultimo_renglon, ultima_hoja):
    """Igual que movimientos_caja.views._proximo_renglon_y_hoja: dado el
    renglón/hoja del movimiento recién guardado, calcula los valores a
    precargar para el próximo alta (renglón +1, o renglón 1 de la hoja
    siguiente si se llegó al tope)."""
    if ultimo_renglon is None:
        return None, ultima_hoja
    if ultimo_renglon >= RENGLON_MAXIMO_POR_HOJA:
        proxima_hoja = (ultima_hoja + 1) if ultima_hoja is not None else None
        return 1, proxima_hoja
    return ultimo_renglon + 1, ultima_hoja


def _siguiente_id(cur):
    cur.execute('SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM movimiento_caja')
    return cur.fetchone()['siguiente']


def _guardar_relacionados(cur, movimiento_id, relacionados):
    """Aplica el mismo criterio que la vista Django para cada tabla
    relacionada: si el dato vino completo se hace upsert (UPDATE si ya
    existía la fila, INSERT si no), si vino vacío se borra la fila (si
    existía). 'relacionados' es un dict con las claves: libro, hoja,
    renglon, numero, emisor, diferido, concepto_tipo."""

    libro = relacionados.get('libro')
    hoja = relacionados.get('hoja')
    renglon = relacionados.get('renglon')
    if libro:
        cur.execute('SELECT 1 FROM bancocuentalibro_movim WHERE id = %s', (movimiento_id,))
        if cur.fetchone():
            cur.execute(
                'UPDATE bancocuentalibro_movim SET id_libro=%s, hoja=%s, renglon=%s WHERE id=%s',
                (libro, hoja, renglon, movimiento_id),
            )
        else:
            cur.execute(
                'INSERT INTO bancocuentalibro_movim (id, id_libro, hoja, renglon) VALUES (%s, %s, %s, %s)',
                (movimiento_id, libro, hoja, renglon),
            )
    else:
        cur.execute('DELETE FROM bancocuentalibro_movim WHERE id = %s', (movimiento_id,))

    numero = relacionados.get('numero')
    if numero is not None:
        cur.execute('SELECT 1 FROM movimiento_caja_numero WHERE id = %s', (movimiento_id,))
        if cur.fetchone():
            cur.execute('UPDATE movimiento_caja_numero SET numero=%s WHERE id=%s', (numero, movimiento_id))
        else:
            cur.execute('INSERT INTO movimiento_caja_numero (id, numero) VALUES (%s, %s)', (movimiento_id, numero))
    else:
        cur.execute('DELETE FROM movimiento_caja_numero WHERE id = %s', (movimiento_id,))

    emisor = relacionados.get('emisor')
    if emisor:
        cur.execute('SELECT 1 FROM movimiento_caja_emisor WHERE id = %s', (movimiento_id,))
        if cur.fetchone():
            cur.execute('UPDATE movimiento_caja_emisor SET id_entidad=%s WHERE id=%s', (emisor, movimiento_id))
        else:
            cur.execute('INSERT INTO movimiento_caja_emisor (id, id_entidad) VALUES (%s, %s)', (movimiento_id, emisor))
    else:
        cur.execute('DELETE FROM movimiento_caja_emisor WHERE id = %s', (movimiento_id,))

    diferido = relacionados.get('diferido')
    if diferido:
        cur.execute('SELECT 1 FROM movimiento_caja_diferido WHERE id = %s', (movimiento_id,))
        if cur.fetchone():
            cur.execute('UPDATE movimiento_caja_diferido SET diferido=%s WHERE id=%s', (diferido, movimiento_id))
        else:
            cur.execute('INSERT INTO movimiento_caja_diferido (id, diferido) VALUES (%s, %s)', (movimiento_id, diferido))
    else:
        cur.execute('DELETE FROM movimiento_caja_diferido WHERE id = %s', (movimiento_id,))

    concepto_tipo = relacionados.get('concepto_tipo')
    if concepto_tipo:
        cur.execute('SELECT 1 FROM movimiento_caja_concepto WHERE id = %s', (movimiento_id,))
        if cur.fetchone():
            cur.execute('UPDATE movimiento_caja_concepto SET id_concepto=%s WHERE id=%s', (concepto_tipo, movimiento_id))
        else:
            cur.execute('INSERT INTO movimiento_caja_concepto (id, id_concepto) VALUES (%s, %s)', (movimiento_id, concepto_tipo))
    else:
        cur.execute('DELETE FROM movimiento_caja_concepto WHERE id = %s', (movimiento_id,))


def crear(datos, relacionados):
    """datos: id_caja, id_tipo, emision, monto, id_receptor (puede ser
    None), efectivizacion. relacionados: ver _guardar_relacionados.
    Devuelve el id asignado (MAX(id)+1, igual que Django)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            nuevo_id = _siguiente_id(cur)
            cur.execute(
                """
                INSERT INTO movimiento_caja
                    (id, idBancoCuenta, id_tipoMov, emision, monto, id_entidad, efectivizacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    nuevo_id, datos['id_caja'], datos['id_tipo'], datos.get('emision'),
                    datos['monto'], datos.get('id_receptor'), datos.get('efectivizacion'),
                ),
            )
            _guardar_relacionados(cur, nuevo_id, relacionados)
        conn.commit()
        return nuevo_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def actualizar(movimiento_id, datos, relacionados):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE movimiento_caja SET
                    idBancoCuenta=%s, id_tipoMov=%s, emision=%s, monto=%s,
                    id_entidad=%s, efectivizacion=%s
                WHERE id=%s
                """,
                (
                    datos['id_caja'], datos['id_tipo'], datos.get('emision'), datos['monto'],
                    datos.get('id_receptor'), datos.get('efectivizacion'), movimiento_id,
                ),
            )
            _guardar_relacionados(cur, movimiento_id, relacionados)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def eliminar(movimiento_id):
    """Borra primero las tablas relacionadas (libro/hoja/renglón, número,
    emisor, diferido, concepto) y recién después la cabecera -- en Django
    algunas de estas relaciones son on_delete=CASCADE y otras DO_NOTHING (no
    se borran solas), así que replicarlo a mano acá es, si algo, más
    prolijo que el borrado real de la vista Django (evita dejar filas
    huérfanas en las tablas DO_NOTHING). El chequeo específico que sí tiene
    la vista Django (no dejar borrar un movimiento ya incluido en una
    Liquidación) NO se replicó todavía -- Liquidaciones sigue pendiente de
    investigar; mientras tanto, si existe una FOREIGN KEY real desde esa
    tabla, el DELETE final la va a rechazar igual y el error se propaga
    para que la UI lo muestre como "no se puede eliminar"."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM bancocuentalibro_movim WHERE id = %s', (movimiento_id,))
            cur.execute('DELETE FROM movimiento_caja_numero WHERE id = %s', (movimiento_id,))
            cur.execute('DELETE FROM movimiento_caja_emisor WHERE id = %s', (movimiento_id,))
            cur.execute('DELETE FROM movimiento_caja_diferido WHERE id = %s', (movimiento_id,))
            cur.execute('DELETE FROM movimiento_caja_concepto WHERE id = %s', (movimiento_id,))
            cur.execute('DELETE FROM movimiento_caja_banco_cuenta_entidad WHERE id = %s', (movimiento_id,))
            cur.execute('DELETE FROM movimiento_caja WHERE id = %s', (movimiento_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
