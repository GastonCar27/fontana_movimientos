"""
Acceso a datos de Comprobantes (tabla `comprobante`), alcance genérico:
alta, edición, listado/búsqueda y eliminación de la CABECERA -- el mismo
subconjunto que las vistas Django `comprobante_form` / `comprobante_listado`
/ `comprobante_eliminar` (módulo "Modificar" de Comprobantes).

Fuera de alcance por ahora (ver README.md): los renglones de un
comprobante (`comprobante_renglon` / `comprobante_renglon_detalle`), los
reportes/rankings/exportaciones y el tipo de cambio para moneda extranjera.
Un comprobante se puede cargar y editar en su cabecera desde acá; agregarle
renglones queda para una próxima vuelta.

Igual que `entidad` y `producto_detalle` (y a diferencia de `movimiento`),
la columna `id` de esta tabla NO es AUTO_INCREMENT real -- Django la trata
como IntegerField(primary_key=True) y calcula MAX(id)+1 a mano
(`comprobantes.views._siguiente_id_comprobante`); acá se replica el mismo
criterio.
"""
from db import get_connection

CAMPOS_EDITABLES = [
    'id_entidad', 'id_tipo_comp', 'id_tipo_documento', 'fecha',
    'punto_de_venta', 'numero', 'moneda', 'neto_gravado', 'neto_no_gravado',
    'recargo', 'impuesto', 'iva', 'exento', 'otros_tributos', 'total',
    'detalle', 'es_emisor',
]

SQL_BASE = """
    SELECT c.id, c.fecha, c.punto_de_venta, c.numero, c.total, c.detalle,
           c.es_emisor,
           c.id_entidad, e.nombre AS entidad_nombre, e.cuit AS entidad_cuit,
           c.id_tipo_comp, t.nombre AS tipo_comprobante_nombre,
           t.abreviatura AS tipo_comprobante_abreviatura,
           c.id_tipo_documento, d.tipo AS tipo_documento_nombre,
           c.moneda, c.neto_gravado, c.neto_no_gravado, c.recargo,
           c.impuesto, c.iva, c.exento, c.otros_tributos,
           (SELECT COUNT(*) FROM comprobante_renglon r WHERE r.id_comprobante = c.id) AS renglones
      FROM comprobante c
      LEFT JOIN entidad e ON e.id = c.id_entidad
      LEFT JOIN comprobante_tipo t ON t.id = c.id_tipo_comp
      LEFT JOIN documento_tipo d ON d.id = c.id_tipo_documento
"""


def listar_tipos_comprobante():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre, abreviatura FROM comprobante_tipo ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


def listar_tipos_documento():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, tipo FROM documento_tipo ORDER BY tipo')
            return cur.fetchall()
    finally:
        conn.close()


def listar(filtro_entidad='', filtro_id='', filtro_fecha='', solo_sin_renglones=False):
    """Mismos 3 filtros de texto que comprobantes.views.comprobante_listado
    (entidad, id, fecha) más el checkbox "sin renglones cargados"; igual
    que la vista, un id no numérico no devuelve resultados en vez de
    fallar."""
    condiciones = []
    parametros = []

    if filtro_entidad:
        comodin = f'%{filtro_entidad}%'
        condiciones.append('(e.nombre LIKE %s OR e.cuit LIKE %s)')
        parametros.extend([comodin, comodin])
    if filtro_id:
        if not filtro_id.isdigit():
            return []
        condiciones.append('c.id = %s')
        parametros.append(int(filtro_id))
    if filtro_fecha:
        condiciones.append('c.fecha = %s')
        parametros.append(filtro_fecha)

    sql = SQL_BASE
    if condiciones:
        sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' ORDER BY c.fecha DESC, c.id DESC LIMIT 200'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            filas = cur.fetchall()
    finally:
        conn.close()

    if solo_sin_renglones:
        filas = [f for f in filas if not f['renglones']]
    return filas


def obtener(comprobante_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_BASE + ' WHERE c.id = %s', (comprobante_id,))
            return cur.fetchone()
    finally:
        conn.close()


def _siguiente_id(cur):
    cur.execute('SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM comprobante')
    return cur.fetchone()['siguiente']


def crear(datos):
    """datos: dict con las claves de CAMPOS_EDITABLES (las que falten se
    guardan como NULL). Devuelve el id asignado (MAX(id)+1, igual que
    Django)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            nuevo_id = _siguiente_id(cur)
            cur.execute(
                """
                INSERT INTO comprobante
                    (id, id_entidad, id_tipo_comp, id_tipo_documento, fecha,
                     punto_de_venta, numero, moneda, neto_gravado, neto_no_gravado,
                     recargo, impuesto, iva, exento, otros_tributos, total,
                     detalle, es_emisor)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    nuevo_id,
                    datos.get('id_entidad'), datos.get('id_tipo_comp'),
                    datos.get('id_tipo_documento'), datos.get('fecha'),
                    datos.get('punto_de_venta'), datos.get('numero'),
                    datos.get('moneda') or None, datos.get('neto_gravado'),
                    datos.get('neto_no_gravado'), datos.get('recargo'),
                    datos.get('impuesto'), datos.get('iva'), datos.get('exento'),
                    datos.get('otros_tributos'), datos.get('total'),
                    datos.get('detalle') or None, datos.get('es_emisor', 1),
                ),
            )
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar(comprobante_id, datos):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE comprobante SET
                    id_entidad=%s, id_tipo_comp=%s, id_tipo_documento=%s, fecha=%s,
                    punto_de_venta=%s, numero=%s, moneda=%s, neto_gravado=%s,
                    neto_no_gravado=%s, recargo=%s, impuesto=%s, iva=%s, exento=%s,
                    otros_tributos=%s, total=%s, detalle=%s, es_emisor=%s
                WHERE id=%s
                """,
                (
                    datos.get('id_entidad'), datos.get('id_tipo_comp'),
                    datos.get('id_tipo_documento'), datos.get('fecha'),
                    datos.get('punto_de_venta'), datos.get('numero'),
                    datos.get('moneda') or None, datos.get('neto_gravado'),
                    datos.get('neto_no_gravado'), datos.get('recargo'),
                    datos.get('impuesto'), datos.get('iva'), datos.get('exento'),
                    datos.get('otros_tributos'), datos.get('total'),
                    datos.get('detalle') or None, datos.get('es_emisor', 1),
                    comprobante_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def eliminar(comprobante_id):
    """Igual que comprobantes.views.comprobante_eliminar: al ser CASCADE en
    Django (ORM), borrar un comprobante también borra sus renglones
    (comprobante_renglon / comprobante_renglon_detalle) y su tipo de
    cambio si tenía. Como acá no se pasa por el ORM, se replica ese mismo
    efecto borrando primero a mano las tablas hijas conocidas de este app
    (en una sola transacción) y recién después el comprobante.

    Si el comprobante está referenciado desde otro app (por ejemplo ya
    incluido en una Liquidación -- ver el chequeo `comprobante.liquidaciones
    .exists()` de la vista Django, que acá NO se replica por no conocer
    todavía el modelo de Liquidaciones) la base va a rechazar el DELETE por
    integridad si esa tabla tiene una FOREIGN KEY real, y ese error se
    propaga para que la UI lo muestre como "no se puede eliminar" -- mismo
    resultado práctico que en la web, aunque con un mensaje más genérico."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE crd FROM comprobante_renglon_detalle crd
                   JOIN comprobante_renglon cr ON cr.id = crd.id
                   WHERE cr.id_comprobante = %s""",
                (comprobante_id,),
            )
            cur.execute(
                'DELETE FROM comprobante_renglon WHERE id_comprobante = %s',
                (comprobante_id,),
            )
            cur.execute(
                'DELETE FROM comprobante_tipo_de_cambio WHERE id = %s',
                (comprobante_id,),
            )
            cur.execute('DELETE FROM comprobante WHERE id = %s', (comprobante_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
