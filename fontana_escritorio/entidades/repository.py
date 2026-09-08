"""
Acceso a la tabla 'entidad' (misma tabla que usa entidades.models.Entidad en
Django). Replica el mismo criterio que la web: nunca se borra una entidad,
se la marca activo=0 ("dar de baja"); y el id se asigna a mano con
MAX(id)+1 en vez de confiar en AUTO_INCREMENT, porque así lo hace también
el resto del proyecto Django (ver productos._siguiente_id_producto_detalle,
liquidaciones._siguiente_id_liquidacion) para varias de estas tablas
legadas -- evita pisar un id ya usado si la columna no es autoincremental.
"""
from db import get_connection

CAMPOS_EDITABLES = [
    'nombre', 'cuit', 'direccion', 'documento_nro', 'codigo',
    'localidad', 'codpos', 'iva', 'provincia',
]


def listar(filtro_texto='', incluir_inactivas=False):
    sql = "SELECT id, nombre, cuit, localidad, provincia, activo FROM entidad"
    condiciones = []
    parametros = []
    if filtro_texto:
        condiciones.append("(nombre LIKE %s OR cuit LIKE %s)")
        comodin = f"%{filtro_texto}%"
        parametros.extend([comodin, comodin])
    if not incluir_inactivas:
        condiciones.append("activo = 1")
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY nombre"

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.fetchall()
    finally:
        conn.close()


def obtener(entidad_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM entidad WHERE id = %s", (entidad_id,))
            return cur.fetchone()
    finally:
        conn.close()


def _siguiente_id(cur):
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM entidad")
    return cur.fetchone()['siguiente']


def crear(datos):
    """datos: dict con las claves de CAMPOS_EDITABLES (las que falten se
    guardan como NULL). Devuelve el id asignado."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            nuevo_id = _siguiente_id(cur)
            cur.execute(
                """INSERT INTO entidad
                   (id, nombre, cuit, direccion, documento_nro, codigo,
                    localidad, codpos, iva, provincia, activo)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)""",
                (
                    nuevo_id,
                    datos.get('nombre') or None,
                    datos.get('cuit') or None,
                    datos.get('direccion') or None,
                    datos.get('documento_nro') or None,
                    datos.get('codigo') or None,
                    datos.get('localidad') or None,
                    datos.get('codpos') or None,
                    datos.get('iva') or None,
                    datos.get('provincia') or None,
                ),
            )
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar(entidad_id, datos):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE entidad SET
                       nombre=%s, cuit=%s, direccion=%s, documento_nro=%s,
                       codigo=%s, localidad=%s, codpos=%s, iva=%s, provincia=%s
                   WHERE id=%s""",
                (
                    datos.get('nombre') or None,
                    datos.get('cuit') or None,
                    datos.get('direccion') or None,
                    datos.get('documento_nro') or None,
                    datos.get('codigo') or None,
                    datos.get('localidad') or None,
                    datos.get('codpos') or None,
                    datos.get('iva') or None,
                    datos.get('provincia') or None,
                    entidad_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def dar_de_baja(entidad_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE entidad SET activo = 0 WHERE id = %s", (entidad_id,))
        conn.commit()
    finally:
        conn.close()


def reactivar(entidad_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE entidad SET activo = 1 WHERE id = %s", (entidad_id,))
        conn.commit()
    finally:
        conn.close()
