"""
Acceso a datos de Remitos (traslado de mercadería), alcance genérico -- el
mismo subconjunto que las vistas Django `remito_form`/`remito_listado`/
`remito_eliminar` (cabecera) y `remito_renglon_form`/`remito_renglon_listado`/
`remito_renglon_eliminar` (renglones), replicando `models.py`/`views.py` de
`fontana_movimientos/remitos`.

Fuera de alcance por ahora (ver README.md): catálogo de Observación
Estándar (es sólo un ayuda-memoria de UI, no afecta datos), el vínculo
"acoplados habituales" de Vehículo (M2M), la impresión de un remito en PDF
sobre el talonario A4 preimpreso (`remito_imprimir_pdf`, con coordenadas
milimétricas calibradas a un papel real) y su exportación a Excel, los
buscadores de transportista/chofer FILTRADOS por rol de entidad (acá se
puede elegir cualquier entidad), y los reportes/listados con exportación a
Excel/PDF de remitos.

A diferencia de las tablas legadas (entidad, producto_detalle, comprobante,
...), `remito`, `remito_renglon`, `remito_vehiculo`, `remito_acoplado` y
`remito_condicion_venta` son tablas NUEVAS creadas por Django (managed=True,
ver models.py): su columna `id` SÍ es AUTO_INCREMENT real, así que acá el
alta no calcula el próximo id a mano -- se deja que la base lo asigne y se
lee con `cursor.lastrowid`, igual que con la tabla `movimiento`.
"""
from db import get_connection

ENTIDAD_PROPIA_ID = 100

TIPO_SALIDA = 'salida'
TIPO_ENTRADA = 'entrada'


# ---------------------------------------------------------------------------
# Remito (cabecera)
# ---------------------------------------------------------------------------

SQL_REMITO_BASE = """
    SELECT r.id, r.tipo, r.punto_venta, r.numero, r.fecha,
           r.id_entidad_emisor, em.nombre AS emisor_nombre,
           r.id_entidad_receptor, re.nombre AS receptor_nombre,
           r.condicion_venta_id, cv.nombre AS condicion_venta_nombre,
           r.valor_declarado,
           r.transportista_id, tr.nombre AS transportista_nombre,
           r.chofer_id, ch.nombre AS chofer_nombre,
           r.vehiculo_id, v.nombre AS vehiculo_nombre, v.patente AS vehiculo_patente,
           r.acoplado_id, ac.patente AS acoplado_patente,
           r.observaciones
      FROM remito r
      LEFT JOIN entidad em ON em.id = r.id_entidad_emisor
      LEFT JOIN entidad re ON re.id = r.id_entidad_receptor
      LEFT JOIN remito_condicion_venta cv ON cv.id = r.condicion_venta_id
      LEFT JOIN entidad tr ON tr.id = r.transportista_id
      LEFT JOIN entidad ch ON ch.id = r.chofer_id
      LEFT JOIN remito_vehiculo v ON v.id = r.vehiculo_id
      LEFT JOIN remito_acoplado ac ON ac.id = r.acoplado_id
"""


def _con_contraparte(fila):
    """Agrega 'contraparte_id'/'contraparte_nombre' (la entidad que no es
    Fontana), igual que la property Remito.contraparte de Django -- para
    que la UI no tenga que repetir la lógica de tipo salida/entrada."""
    if fila is None:
        return None
    if fila['tipo'] == TIPO_SALIDA:
        fila['contraparte_id'] = fila['id_entidad_receptor']
        fila['contraparte_nombre'] = fila['receptor_nombre']
    else:
        fila['contraparte_id'] = fila['id_entidad_emisor']
        fila['contraparte_nombre'] = fila['emisor_nombre']
    return fila


def listar_remitos(filtro_texto='', filtro_tipo='', filtro_fecha_desde='', filtro_fecha_hasta=''):
    sql = SQL_REMITO_BASE
    condiciones = []
    parametros = []

    if filtro_texto:
        comodin = f'%{filtro_texto}%'
        condicion = '(r.numero LIKE %s OR em.nombre LIKE %s OR re.nombre LIKE %s'
        parametros.extend([comodin, comodin, comodin])
        if filtro_texto.isdigit():
            condicion += ' OR r.id = %s OR r.numero = %s'
            parametros.extend([int(filtro_texto), int(filtro_texto)])
        condicion += ')'
        condiciones.append(condicion)

    if filtro_tipo in (TIPO_SALIDA, TIPO_ENTRADA):
        condiciones.append('r.tipo = %s')
        parametros.append(filtro_tipo)

    if filtro_fecha_desde:
        condiciones.append('r.fecha >= %s')
        parametros.append(filtro_fecha_desde)
    if filtro_fecha_hasta:
        condiciones.append('r.fecha <= %s')
        parametros.append(filtro_fecha_hasta)

    if condiciones:
        sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' ORDER BY r.fecha DESC, r.id DESC LIMIT 500'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            return [_con_contraparte(f) for f in cur.fetchall()]
    finally:
        conn.close()


def obtener_remito(remito_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_REMITO_BASE + ' WHERE r.id = %s', (remito_id,))
            return _con_contraparte(cur.fetchone())
    finally:
        conn.close()


def _resolver_emisor_receptor(tipo, contraparte_id):
    if tipo == TIPO_SALIDA:
        return ENTIDAD_PROPIA_ID, contraparte_id
    return contraparte_id, ENTIDAD_PROPIA_ID


def _existe_conflicto_numero(cur, emisor_id, punto_venta, numero, excluir_id=None):
    """Refleja el UniqueConstraint(emisor, punto_venta, numero) del modelo
    Remito -- se chequea a mano porque 'emisor' no es un campo editado
    directamente (se arma a partir de tipo + contraparte, ver
    remito_form en Django)."""
    sql = 'SELECT id FROM remito WHERE id_entidad_emisor = %s AND punto_venta = %s AND numero = %s'
    parametros = [emisor_id, punto_venta, numero]
    if excluir_id is not None:
        sql += ' AND id <> %s'
        parametros.append(excluir_id)
    cur.execute(sql, parametros)
    return cur.fetchone() is not None


def crear_remito(datos):
    """datos: tipo, punto_venta, numero, fecha, id_contraparte y
    opcionalmente condicion_venta_id/valor_declarado/transportista_id/
    chofer_id/vehiculo_id/acoplado_id/observaciones.
    Devuelve el id asignado. Lanza ValueError si ya existe un remito con
    ese punto de venta y número para el emisor resultante."""
    emisor_id, receptor_id = _resolver_emisor_receptor(datos['tipo'], datos['id_contraparte'])
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if _existe_conflicto_numero(cur, emisor_id, datos['punto_venta'], datos['numero']):
                raise ValueError('Ya existe un remito con ese punto de venta y número para este emisor.')
            cur.execute(
                """
                INSERT INTO remito
                    (tipo, punto_venta, numero, fecha, id_entidad_emisor, id_entidad_receptor,
                     condicion_venta_id, valor_declarado, transportista_id, chofer_id,
                     vehiculo_id, acoplado_id, observaciones, guardado_el, modificado_el)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    datos['tipo'], datos['punto_venta'], datos['numero'], datos['fecha'],
                    emisor_id, receptor_id,
                    datos.get('condicion_venta_id'), datos.get('valor_declarado'),
                    datos.get('transportista_id'), datos.get('chofer_id'),
                    datos.get('vehiculo_id'), datos.get('acoplado_id'),
                    datos.get('observaciones') or '',
                ),
            )
            nuevo_id = cur.lastrowid
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar_remito(remito_id, datos):
    emisor_id, receptor_id = _resolver_emisor_receptor(datos['tipo'], datos['id_contraparte'])
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if _existe_conflicto_numero(cur, emisor_id, datos['punto_venta'], datos['numero'], excluir_id=remito_id):
                raise ValueError('Ya existe un remito con ese punto de venta y número para este emisor.')
            cur.execute(
                """
                UPDATE remito SET
                    tipo=%s, punto_venta=%s, numero=%s, fecha=%s,
                    id_entidad_emisor=%s, id_entidad_receptor=%s,
                    condicion_venta_id=%s, valor_declarado=%s,
                    transportista_id=%s, chofer_id=%s, vehiculo_id=%s, acoplado_id=%s,
                    observaciones=%s, modificado_el=NOW()
                WHERE id=%s
                """,
                (
                    datos['tipo'], datos['punto_venta'], datos['numero'], datos['fecha'],
                    emisor_id, receptor_id,
                    datos.get('condicion_venta_id'), datos.get('valor_declarado'),
                    datos.get('transportista_id'), datos.get('chofer_id'),
                    datos.get('vehiculo_id'), datos.get('acoplado_id'),
                    datos.get('observaciones') or '',
                    remito_id,
                ),
            )
            # Si cambió el tipo/contraparte, los renglones ya sincronizados
            # con un Movimiento tienen que reflejar el nuevo emisor/receptor
            # (igual que si se hubieran vuelto a guardar uno por uno).
            cur.execute('SELECT id FROM remito_renglon WHERE remito_id = %s', (remito_id,))
            renglon_ids = [f['id'] for f in cur.fetchall()]
            for renglon_id in renglon_ids:
                _sincronizar_movimiento_renglon(cur, renglon_id)
        conn.commit()
    finally:
        conn.close()


def eliminar_remito(remito_id):
    """Igual que remito_eliminar en Django: borra primero el Movimiento
    vinculado a cada renglón (si tiene), después los renglones, y por
    último la cabecera."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT movimiento_id FROM remito_renglon WHERE remito_id = %s', (remito_id,))
            movimiento_ids = [f['movimiento_id'] for f in cur.fetchall() if f['movimiento_id']]
            for movimiento_id in movimiento_ids:
                cur.execute('DELETE FROM movimiento WHERE id_movimiento = %s', (movimiento_id,))
            cur.execute('DELETE FROM remito_renglon WHERE remito_id = %s', (remito_id,))
            cur.execute('DELETE FROM remito WHERE id = %s', (remito_id,))
        conn.commit()
    finally:
        conn.close()


def sugerir_punto_venta_numero():
    """Igual que remito_form en Django: para un alta nueva sugiere el punto
    de venta y el próximo número, tomando como base el último remito que
    Fontana emitió (tipo Salida). Sólo un valor sugerido, se puede cambiar
    antes de guardar."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT punto_venta, numero FROM remito
                 WHERE id_entidad_emisor = %s
                 ORDER BY fecha DESC, id DESC LIMIT 1
                """,
                (ENTIDAD_PROPIA_ID,),
            )
            fila = cur.fetchone()
    finally:
        conn.close()
    if not fila:
        return None, None
    return fila['punto_venta'], fila['numero'] + 1


# ---------------------------------------------------------------------------
# RemitoRenglon -- y la sincronización con Movimiento de producto
# ---------------------------------------------------------------------------

SQL_RENGLON_BASE = """
    SELECT rr.id, rr.remito_id, rr.orden, rr.producto_id, p.nombre AS producto_nombre,
           rr.detalle_adicional, rr.cantidad,
           rr.unidad_de_medida_id, u.nombre AS unidad_nombre,
           rr.kilogramos_enviados, rr.kilogramos_confirmados, rr.movimiento_id
      FROM remito_renglon rr
      LEFT JOIN producto_detalle p ON p.id = rr.producto_id
      LEFT JOIN comprobante_unidad_de_medida u ON u.id = rr.unidad_de_medida_id
"""


def listar_renglones(remito_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_RENGLON_BASE + ' WHERE rr.remito_id = %s ORDER BY rr.orden, rr.id', (remito_id,))
            return cur.fetchall()
    finally:
        conn.close()


def obtener_renglon(renglon_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_RENGLON_BASE + ' WHERE rr.id = %s', (renglon_id,))
            return cur.fetchone()
    finally:
        conn.close()


def _siguiente_numero_movimiento(cur, producto_id):
    """Igual que remitos.views._siguiente_numero_movimiento: el 'numero' de
    Movimiento es un correlativo POR PRODUCTO (hay una restricción única
    (numero, producto) en la tabla movimiento)."""
    cur.execute('SELECT COALESCE(MAX(numero), 0) AS maximo FROM movimiento WHERE id_producto = %s', (producto_id,))
    return (cur.fetchone()['maximo'] or 0) + 1


def _sincronizar_movimiento_renglon(cur, renglon_id):
    """Crea o actualiza el Movimiento vinculado a este renglón -- réplica
    exacta de remitos.views._sincronizar_movimiento_renglon: se crea la
    primera vez que se guarda el renglón (con el peso definitivo disponible
    en ese momento) y, si más tarde se completa 'kilogramos_confirmados' o
    cambia el producto del renglón, se actualiza el MISMO movimiento (nunca
    se crea uno nuevo, para no duplicar el saldo del producto).

    El emisor/receptor del Movimiento es siempre igual al emisor/receptor
    del Remito (para un remito de Salida, Fontana ya es el emisor del
    remito y la contraparte el receptor; para uno de Entrada es al revés
    -- exactamente lo que necesita el Movimiento), así que se toman
    directo de la cabecera en vez de recalcularlos con 'tipo'."""
    cur.execute(
        """
        SELECT rr.producto_id, rr.unidad_de_medida_id, rr.kilogramos_enviados,
               rr.kilogramos_confirmados, rr.movimiento_id,
               r.fecha, r.id_entidad_emisor, r.id_entidad_receptor
          FROM remito_renglon rr
          JOIN remito r ON r.id = rr.remito_id
         WHERE rr.id = %s
        """,
        (renglon_id,),
    )
    fila = cur.fetchone()
    total = fila['kilogramos_confirmados'] if fila['kilogramos_confirmados'] is not None else fila['kilogramos_enviados']

    if fila['movimiento_id']:
        cur.execute('SELECT id_producto, numero FROM movimiento WHERE id_movimiento = %s', (fila['movimiento_id'],))
        movimiento_actual = cur.fetchone()
        if movimiento_actual and movimiento_actual['id_producto'] != fila['producto_id']:
            # Cambió el producto del renglón: el numero viejo puede chocar
            # con la restricción única (numero, producto) del producto
            # nuevo -- se recalcula.
            numero = _siguiente_numero_movimiento(cur, fila['producto_id'])
        elif movimiento_actual:
            numero = movimiento_actual['numero']
        else:
            numero = _siguiente_numero_movimiento(cur, fila['producto_id'])
        cur.execute(
            """
            UPDATE movimiento SET
                id_producto=%s, fecha=%s, total=%s,
                id_entidad_emisor=%s, id_entidad_receptor=%s,
                numero=%s, id_unidad_de_medida=%s, modificado_el=NOW()
            WHERE id_movimiento=%s
            """,
            (
                fila['producto_id'], fila['fecha'], total,
                fila['id_entidad_emisor'], fila['id_entidad_receptor'],
                numero, fila['unidad_de_medida_id'], fila['movimiento_id'],
            ),
        )
    else:
        numero = _siguiente_numero_movimiento(cur, fila['producto_id'])
        cur.execute(
            """
            INSERT INTO movimiento
                (id_producto, fecha, total, id_entidad_emisor, id_entidad_receptor,
                 numero, id_unidad_de_medida, guardado_el)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                fila['producto_id'], fila['fecha'], total,
                fila['id_entidad_emisor'], fila['id_entidad_receptor'],
                numero, fila['unidad_de_medida_id'],
            ),
        )
        nuevo_movimiento_id = cur.lastrowid
        cur.execute('UPDATE remito_renglon SET movimiento_id = %s WHERE id = %s', (nuevo_movimiento_id, renglon_id))


def crear_renglon(datos):
    """datos: remito_id, producto_id, kilogramos_enviados y opcionalmente
    detalle_adicional/cantidad/unidad_de_medida_id/kilogramos_confirmados.
    Devuelve el id del renglón creado; el Movimiento vinculado se crea en
    la misma transacción."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COALESCE(MAX(orden), 0) AS maximo FROM remito_renglon WHERE remito_id = %s', (datos['remito_id'],))
            orden = (cur.fetchone()['maximo'] or 0) + 1
            cur.execute(
                """
                INSERT INTO remito_renglon
                    (remito_id, orden, producto_id, detalle_adicional, cantidad,
                     unidad_de_medida_id, kilogramos_enviados, kilogramos_confirmados)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    datos['remito_id'], orden, datos['producto_id'],
                    datos.get('detalle_adicional') or '', datos.get('cantidad'),
                    datos.get('unidad_de_medida_id'), datos['kilogramos_enviados'],
                    datos.get('kilogramos_confirmados'),
                ),
            )
            nuevo_id = cur.lastrowid
            _sincronizar_movimiento_renglon(cur, nuevo_id)
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar_renglon(renglon_id, datos):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE remito_renglon SET
                    producto_id=%s, detalle_adicional=%s, cantidad=%s,
                    unidad_de_medida_id=%s, kilogramos_enviados=%s, kilogramos_confirmados=%s
                WHERE id=%s
                """,
                (
                    datos['producto_id'], datos.get('detalle_adicional') or '', datos.get('cantidad'),
                    datos.get('unidad_de_medida_id'), datos['kilogramos_enviados'],
                    datos.get('kilogramos_confirmados'), renglon_id,
                ),
            )
            _sincronizar_movimiento_renglon(cur, renglon_id)
        conn.commit()
    finally:
        conn.close()


def eliminar_renglon(renglon_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT movimiento_id, remito_id FROM remito_renglon WHERE id = %s', (renglon_id,))
            fila = cur.fetchone()
            if fila and fila['movimiento_id']:
                cur.execute('DELETE FROM movimiento WHERE id_movimiento = %s', (fila['movimiento_id'],))
            cur.execute('DELETE FROM remito_renglon WHERE id = %s', (renglon_id,))
        conn.commit()
        return fila['remito_id'] if fila else None
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


# ---------------------------------------------------------------------------
# Catálogos: Vehículo / Acoplado / Condición de venta
# (alta + edición nada más, igual que Django: no hay vista de "eliminar"
# para estos catálogos, sólo se los desactiva editando el campo activo/a)
# ---------------------------------------------------------------------------

def listar_vehiculos(incluir_inactivos=False):
    sql = 'SELECT id, nombre, patente, activo FROM remito_vehiculo'
    if not incluir_inactivos:
        sql += ' WHERE activo = 1'
    sql += ' ORDER BY nombre'
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


def crear_vehiculo(nombre, patente, activo=True):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO remito_vehiculo (nombre, patente, activo) VALUES (%s, %s, %s)',
                (nombre, patente, 1 if activo else 0),
            )
            nuevo_id = cur.lastrowid
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar_vehiculo(vehiculo_id, nombre, patente, activo=True):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE remito_vehiculo SET nombre=%s, patente=%s, activo=%s WHERE id=%s',
                (nombre, patente, 1 if activo else 0, vehiculo_id),
            )
        conn.commit()
    finally:
        conn.close()


def listar_acoplados(incluir_inactivos=False):
    sql = 'SELECT id, patente, activo FROM remito_acoplado'
    if not incluir_inactivos:
        sql += ' WHERE activo = 1'
    sql += ' ORDER BY patente'
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


def crear_acoplado(patente, activo=True):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO remito_acoplado (patente, activo) VALUES (%s, %s)', (patente, 1 if activo else 0))
            nuevo_id = cur.lastrowid
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar_acoplado(acoplado_id, patente, activo=True):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE remito_acoplado SET patente=%s, activo=%s WHERE id=%s', (patente, 1 if activo else 0, acoplado_id))
        conn.commit()
    finally:
        conn.close()


def listar_condiciones_venta(incluir_inactivas=False):
    sql = 'SELECT id, nombre, activa FROM remito_condicion_venta'
    if not incluir_inactivas:
        sql += ' WHERE activa = 1'
    sql += ' ORDER BY nombre'
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


def crear_condicion_venta(nombre, activa=True):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO remito_condicion_venta (nombre, activa) VALUES (%s, %s)', (nombre, 1 if activa else 0))
            nuevo_id = cur.lastrowid
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar_condicion_venta(condicion_id, nombre, activa=True):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE remito_condicion_venta SET nombre=%s, activa=%s WHERE id=%s', (nombre, 1 if activa else 0, condicion_id))
        conn.commit()
    finally:
        conn.close()
