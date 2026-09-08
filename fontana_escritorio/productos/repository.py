"""
Acceso a las tablas 'producto_detalle' e 'item_tipo' (mismas tablas que
productos.models.ProductoDetalle / ItemTipo en Django). Mismo criterio de
id manual (MAX(id)+1) que entidades.repository -- ver ese archivo.
"""
from db import get_connection


def listar_item_tipos():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre FROM item_tipo ORDER BY nombre")
            return cur.fetchall()
    finally:
        conn.close()


def listar(filtro_texto=''):
    sql = (
        "SELECT p.id, p.nombre, p.id_item_tipo, t.nombre AS item_tipo_nombre "
        "FROM producto_detalle p LEFT JOIN item_tipo t ON t.id = p.id_item_tipo"
    )
    parametros = []
    if filtro_texto:
        sql += " WHERE p.nombre LIKE %s"
        parametros.append(f"%{filtro_texto}%")
    sql += " ORDER BY p.nombre"

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.fetchall()
    finally:
        conn.close()


def obtener(producto_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM producto_detalle WHERE id = %s", (producto_id,))
            return cur.fetchone()
    finally:
        conn.close()


def _siguiente_id(cur):
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM producto_detalle")
    return cur.fetchone()['siguiente']


def crear(nombre, item_tipo_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            nuevo_id = _siguiente_id(cur)
            cur.execute(
                "INSERT INTO producto_detalle (id, nombre, id_item_tipo) VALUES (%s, %s, %s)",
                (nuevo_id, nombre, item_tipo_id),
            )
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar(producto_id, nombre, item_tipo_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE producto_detalle SET nombre=%s, id_item_tipo=%s WHERE id=%s",
                (nombre, item_tipo_id, producto_id),
            )
        conn.commit()
    finally:
        conn.close()


def esta_en_uso(producto_id):
    """
    Chequeo best-effort antes de permitir eliminar un producto: revisa las
    referencias más obvias (movimientos, renglones de comprobante y de
    remito). OJO: esto es una réplica desde afuera de lo que hace
    productos.views.producto_eliminar en Django -- antes de confiar en esto
    a ciegas conviene comparar contra esa vista real, por si chequea alguna
    tabla más que acá no se contempló. Aparte, si en MySQL esas columnas
    tienen FOREIGN KEY de verdad, el propio DELETE de eliminar() va a
    rechazar el borrado igual (se captura ese caso también).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM movimiento WHERE id_producto=%s", (producto_id,))
            if cur.fetchone()['n'] > 0:
                return True
            cur.execute("SELECT COUNT(*) AS n FROM comprobante_renglon WHERE id_producto=%s", (producto_id,))
            if cur.fetchone()['n'] > 0:
                return True
            cur.execute(
                "SELECT COUNT(*) AS n FROM remito_renglon WHERE producto_id=%s", (producto_id,)
            )
            if cur.fetchone()['n'] > 0:
                return True
        return False
    finally:
        conn.close()


def eliminar(producto_id):
    """Lanza pymysql.err.IntegrityError si la base rechaza el borrado por
    una FOREIGN KEY real -- la UI debe capturarlo y avisar, no asumir que
    esta_en_uso() ya cubrió el 100% de los casos."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM producto_detalle WHERE id=%s", (producto_id,))
        conn.commit()
    finally:
        conn.close()
