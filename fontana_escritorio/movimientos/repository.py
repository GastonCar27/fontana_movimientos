"""
Acceso a datos de Movimientos de producto (tabla `movimiento`), alcance
genérico: alta, edición, listado/búsqueda y eliminación -- el mismo
subconjunto que las vistas Django `movimiento_form` / `movimiento_listado`
/ `movimiento_eliminar` (módulo "Modificación" de Movimientos).

Fuera de alcance por ahora (ver README.md): salida de yerba mate canchada
y los reportes/rankings/exportaciones a Excel o PDF. La recepción de H.V.
de Yerba Mate (`crear_recepcion_hv_yerba_mate` más abajo) sí está --
replica `movimientos.views.recepcion_hv_yerba_mate` / `IngresoHvYerbaMateForm`.

A diferencia de `entidad` y `producto_detalle`, la columna `id_movimiento`
de esta tabla SÍ es AUTO_INCREMENT real en MySQL (en Django está declarada
como `AutoField`, no como `IntegerField(primary_key=True)` como las otras
dos) -- por eso acá el alta no calcula el próximo id a mano, se deja que
la base lo asigne y se lee con `cursor.lastrowid`.
"""
from db import get_connection

SQL_BASE = """
    SELECT m.id_movimiento, m.fecha, m.numero, m.total,
           m.id_producto, p.nombre AS producto_nombre,
           m.id_entidad_emisor, ee.nombre AS emisor_nombre,
           m.id_entidad_receptor, er.nombre AS receptor_nombre,
           m.id_unidad_de_medida, u.nombre AS unidad_nombre
      FROM movimiento m
      LEFT JOIN producto_detalle p ON p.id = m.id_producto
      LEFT JOIN entidad ee ON ee.id = m.id_entidad_emisor
      LEFT JOIN entidad er ON er.id = m.id_entidad_receptor
      LEFT JOIN comprobante_unidad_de_medida u ON u.id = m.id_unidad_de_medida
"""


def listar(filtro_receptor='', filtro_id='', filtro_fecha='', filtro_numero=''):
    """Mismos 4 filtros que movimientos.views.movimiento_listado (receptor,
    id, fecha, numero); igual que la vista, un id/numero no numérico no
    devuelve resultados en vez de fallar."""
    condiciones = []
    parametros = []

    if filtro_receptor:
        comodin = f'%{filtro_receptor}%'
        condiciones.append('(er.nombre LIKE %s OR er.cuit LIKE %s)')
        parametros.extend([comodin, comodin])
    if filtro_id:
        if not filtro_id.isdigit():
            return []
        condiciones.append('m.id_movimiento = %s')
        parametros.append(int(filtro_id))
    if filtro_fecha:
        condiciones.append('m.fecha = %s')
        parametros.append(filtro_fecha)
    if filtro_numero:
        if not filtro_numero.isdigit():
            return []
        condiciones.append('m.numero = %s')
        parametros.append(int(filtro_numero))

    sql = SQL_BASE
    if condiciones:
        sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' ORDER BY m.fecha DESC, m.id_movimiento DESC LIMIT 200'

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
            cur.execute(SQL_BASE + ' WHERE m.id_movimiento = %s', (movimiento_id,))
            return cur.fetchone()
    finally:
        conn.close()


def listar_unidades_medida():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre FROM comprobante_unidad_de_medida ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


def existe_numero_producto(numero, producto_id, excluir_id=None):
    """Refleja el UniqueConstraint(['numero', 'producto']) del modelo
    Movimiento: True si ya existe OTRO movimiento con ese mismo par."""
    if numero in (None, ''):
        return False
    sql = 'SELECT id_movimiento FROM movimiento WHERE numero = %s AND id_producto = %s'
    parametros = [numero, producto_id]
    if excluir_id is not None:
        sql += ' AND id_movimiento <> %s'
        parametros.append(excluir_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.fetchone() is not None
    finally:
        conn.close()


def crear(datos):
    """datos: dict con id_producto, fecha, total, id_entidad_emisor,
    id_entidad_receptor y opcionalmente numero / id_unidad_de_medida.
    Devuelve el id_movimiento asignado por MySQL (AUTO_INCREMENT)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO movimiento
                    (id_producto, fecha, total, id_entidad_emisor,
                     id_entidad_receptor, numero, id_unidad_de_medida, guardado_el)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    datos['id_producto'], datos.get('fecha'), datos['total'],
                    datos['id_entidad_emisor'], datos['id_entidad_receptor'],
                    datos.get('numero'), datos.get('id_unidad_de_medida'),
                ),
            )
            nuevo_id = cur.lastrowid
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar(movimiento_id, datos):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE movimiento
                   SET id_producto = %s, fecha = %s, total = %s,
                       id_entidad_emisor = %s, id_entidad_receptor = %s,
                       numero = %s, id_unidad_de_medida = %s, modificado_el = NOW()
                 WHERE id_movimiento = %s
                """,
                (
                    datos['id_producto'], datos.get('fecha'), datos['total'],
                    datos['id_entidad_emisor'], datos['id_entidad_receptor'],
                    datos.get('numero'), datos.get('id_unidad_de_medida'),
                    movimiento_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


# --- Recepción de H.V. de Yerba Mate ---------------------------------
# Constantes tomadas de movimientos.forms.IngresoHvYerbaMateForm (mismos
# valores fijos que usa la vista Django: producto "HOJA VERDE DE YERBA MATE
# PUESTA EN SECADERO" y el operador INYM de Fontana como Secadero receptor).
PRODUCTO_HOJA_VERDE_SECADERO_ID = 2
OPERADOR_FONTANA_SECADERO_ID = 181
UNIDAD_MEDIDA_KILOGRAMOS_ID = '01'


def listar_inym_operadores():
    """Operadores INYM con su entidad y tipo, ordenados igual que
    IngresoHvYerbaMateForm: por nombre de entidad y, dentro de cada
    entidad, primero el operador de tipo PRODUCTORES."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT io.id, io.id_entidad, e.nombre AS entidad_nombre,
                       io.id_operador_tipo, t.nombre AS tipo_nombre
                  FROM inym_operador io
                  JOIN entidad e ON e.id = io.id_entidad
                  JOIN inym_operador_tipo t ON t.id = io.id_operador_tipo
                 ORDER BY e.nombre,
                          CASE WHEN UPPER(t.nombre) = 'PRODUCTORES' THEN 0 ELSE 1 END,
                          io.id
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def obtener_inym_operador(operador_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT io.id, io.id_entidad, e.nombre AS entidad_nombre
                  FROM inym_operador io
                  JOIN entidad e ON e.id = io.id_entidad
                 WHERE io.id = %s
                """,
                (operador_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def ultima_recepcion_hv_yerba_mate():
    """Refleja MovimientoHvYerbaMate.objects.latest('guardado_el'): se usa
    para precargar numero+1 y la misma fecha en el formulario de alta."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.numero, m.fecha
                  FROM movimiento_hv_yerba_mate mh
                  JOIN movimiento m ON m.id_movimiento = mh.movimiento_id
                 ORDER BY m.guardado_el DESC
                 LIMIT 1
                """
            )
            return cur.fetchone()
    finally:
        conn.close()


PRODUCTO_YERBA_CANCHADA_ID = 1037


def _crear_movimiento_hv_yerba_mate(producto_id, operador_origen_id, operador_destino_id, datos):
    """Inserta en las 3 tablas (movimiento, movimiento_pesaje,
    movimiento_hv_yerba_mate) en una sola transacción. Uso interno, común a
    la recepción (origen variable, destino fijo=Fontana Secadero) y a la
    salida de yerba canchada (origen fijo=Fontana Secadero, destino
    variable) -- mismo patrón que las vistas Django recepcion_hv_yerba_mate
    / salida_yerba_mate_canchada."""
    operador_origen = obtener_inym_operador(operador_origen_id)
    operador_destino = obtener_inym_operador(operador_destino_id)
    if not operador_origen or not operador_destino:
        raise ValueError('No se encontró el operador INYM emisor o el receptor.')

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO movimiento
                    (id_producto, fecha, total, id_entidad_emisor,
                     id_entidad_receptor, numero, id_unidad_de_medida, guardado_el)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    producto_id, datos.get('fecha'), datos['total'],
                    operador_origen['id_entidad'], operador_destino['id_entidad'],
                    datos.get('numero'), UNIDAD_MEDIDA_KILOGRAMOS_ID,
                ),
            )
            nuevo_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO movimiento_pesaje (movimiento_id, bruto, tara, descuento)
                VALUES (%s, %s, %s, %s)
                """,
                (nuevo_id, datos.get('bruto'), datos.get('tara'), datos.get('descuento')),
            )
            cur.execute(
                """
                INSERT INTO movimiento_hv_yerba_mate
                    (movimiento_id, id_inym_operador_origen, id_inym_operador_destino)
                VALUES (%s, %s, %s)
                """,
                (nuevo_id, operador_origen['id'], operador_destino['id']),
            )
        conn.commit()
        return nuevo_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def crear_recepcion_hv_yerba_mate(datos):
    """datos: fecha, numero (pueden ser None), id_inym_operador_origen,
    bruto/tara/descuento (float u None) y total (ya calculado: bruto - tara
    - descuento). Igual que movimientos.views.recepcion_hv_yerba_mate:
    producto fijo Hoja Verde puesta en secadero, receptor fijo Fontana
    Secadero, se elige el operador INYM emisor."""
    return _crear_movimiento_hv_yerba_mate(
        PRODUCTO_HOJA_VERDE_SECADERO_ID, datos['id_inym_operador_origen'],
        OPERADOR_FONTANA_SECADERO_ID, datos,
    )


def crear_salida_yerba_mate_canchada(datos):
    """datos: fecha, numero, id_inym_operador_destino, bruto/tara/descuento
    y total. Igual que movimientos.views.salida_yerba_mate_canchada:
    producto fijo Yerba Canchada, emisor fijo Fontana Secadero, se elige el
    operador INYM receptor."""
    return _crear_movimiento_hv_yerba_mate(
        PRODUCTO_YERBA_CANCHADA_ID, OPERADOR_FONTANA_SECADERO_ID,
        datos['id_inym_operador_destino'], datos,
    )


def eliminar(movimiento_id):
    """Igual que movimientos.views.movimiento_eliminar: se intenta el
    DELETE y se deja propagar cualquier error de integridad (por ejemplo si
    hay pesaje/HV Yerba Mate u otra tabla referenciándolo) para que la UI lo
    muestre como "no se puede eliminar", en vez de intentar adivinar acá
    todas las tablas relacionadas y sus columnas."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM movimiento WHERE id_movimiento = %s', (movimiento_id,))
        conn.commit()
    finally:
        conn.close()
