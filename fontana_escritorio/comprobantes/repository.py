"""
Acceso a datos de Comprobantes (tabla `comprobante`), alcance genérico:
alta, edición, listado/búsqueda y eliminación de la CABECERA -- el mismo
subconjunto que las vistas Django `comprobante_form` / `comprobante_listado`
/ `comprobante_eliminar` (módulo "Modificar" de Comprobantes).

Fuera de alcance por ahora (ver README.md): el tipo de cambio para moneda
extranjera -- OJO: esto ni siquiera existe todavía del lado Django (el
modelo `ComprobanteTipoDeCambio` está declarado pero no hay ninguna vista
que lo use), así que no hay nada real para replicar acá todavía.

Igual que `entidad` y `producto_detalle` (y a diferencia de `movimiento`),
la columna `id` de esta tabla NO es AUTO_INCREMENT real -- Django la trata
como IntegerField(primary_key=True) y calcula MAX(id)+1 a mano
(`comprobantes.views._siguiente_id_comprobante`); acá se replica el mismo
criterio.

Agregado el 2026-09-22: soporte de renglones (`comprobante_renglon` /
`comprobante_renglon_detalle`), ver la sección al final del archivo --
réplica de las vistas Django `comprobante_renglon_form` /
`comprobante_renglon_listado` / `comprobante_renglon_eliminar`. `id` de
`comprobante_renglon` TAMPOCO es AUTO_INCREMENT real (mismo criterio
MAX(id)+1, ver `_siguiente_id_comprobante_renglon` en Django).
"""
from decimal import Decimal, InvalidOperation

from db import get_connection


class ComprobanteEnUso(Exception):
    """Se lanza al intentar eliminar un comprobante que ya está incluido en
    una Liquidación (tabla `liquidacion_comprobante`) -- réplica del
    chequeo `comprobante.liquidaciones.exists()` que tiene comprobantes.
    views.comprobante_eliminar en Django. Agregado el 2026-09-22: hasta
    acá este chequeo NO estaba replicado del lado escritorio (quedaba
    documentado como pendiente en el docstring de `eliminar` más abajo),
    así que si `liquidacion_comprobante` no tuviera una FOREIGN KEY real
    en MySQL, el DELETE se hacía igual y el vínculo quedaba huérfano en
    silencio -- ahora se chequea a mano ANTES de borrar nada, igual
    criterio que se usó el 2026-09-18 para Movimientos vinculados a Cuenta
    Corriente de Productos.
    """


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

    Chequeo agregado el 2026-09-22: si el comprobante ya está incluido en
    una Liquidación (tabla `liquidacion_comprobante`, ver
    `liquidaciones/repository.py`), se lanza `ComprobanteEnUso` ANTES de
    borrar nada -- réplica del chequeo `comprobante.liquidaciones.exists()`
    que tiene la vista Django, que hasta ahora no estaba replicado acá (el
    comentario original decía que, si la base tenía una FOREIGN KEY real,
    el DELETE la iba a rechazar igual -- pero como estas tablas son
    managed=False del lado Django, no hay garantía de que esa FK exista de
    verdad, así que confiar en eso era un supuesto sin verificar).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT 1 FROM liquidacion_comprobante WHERE id_comprobante = %s LIMIT 1',
                (comprobante_id,),
            )
            if cur.fetchone():
                raise ComprobanteEnUso(
                    f'El comprobante {comprobante_id} ya está incluido en una liquidación; '
                    'no se puede eliminar. Hay que sacarlo de esa liquidación primero '
                    '(editarla y destildarlo, o eliminar la liquidación).'
                )
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
    except ComprobanteEnUso:
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ComprobanteRenglon / ComprobanteRenglonDetalle -- agregado el 2026-09-22
# Réplica de comprobantes.views.comprobante_renglon_form /
# comprobante_renglon_listado / comprobante_renglon_eliminar en Django.
# ---------------------------------------------------------------------------

# Mismos valores que comprobantes.forms.CATEGORIAS_CON_DETALLE /
# CATEGORIA_IVA en Django: sólo los renglones cuyo producto es de una de
# estas categorías (item_tipo.nombre) llevan fila en
# comprobante_renglon_detalle -- IVA y otros tributos no.
CATEGORIAS_CON_DETALLE = {
    'producto o servicio',
    'producto/servicio',
    'producto',
    'servicio',
}
CATEGORIA_IVA = 'iva'

# Mismo criterio que comprobantes.models.IDS_UNIDADES_SOLO_REMITOS: estas
# unidades (Bolsón/Bolsa) se agregaron a mano sólo para uso interno de
# Remitos y tienen que quedar excluidas del desplegable de un comprobante
# fiscal real.
IDS_UNIDADES_SOLO_REMITOS = ['BN', 'BS']

SQL_RENGLON_BASE = """
    SELECT cr.id, cr.id_comprobante, cr.id_producto, p.nombre AS producto_nombre,
           p.id_item_tipo, it.nombre AS producto_categoria,
           cr.total, cr.id_cuenta_contable, cr.id_asiento_contable,
           crd.cantidad, crd.id_unidad_de_medida, u.nombre AS unidad_nombre,
           crd.precio_unitario, crd.bonificacion,
           crd.id_iva_tipo, piva.nombre AS iva_tipo_nombre,
           crd.id_sector_tipo, st.nombre AS sector_tipo_nombre
      FROM comprobante_renglon cr
      LEFT JOIN producto_detalle p ON p.id = cr.id_producto
      LEFT JOIN item_tipo it ON it.id = p.id_item_tipo
      LEFT JOIN comprobante_renglon_detalle crd ON crd.id = cr.id
      LEFT JOIN comprobante_unidad_de_medida u ON u.id = crd.id_unidad_de_medida
      LEFT JOIN producto_detalle piva ON piva.id = crd.id_iva_tipo
      LEFT JOIN sector_tipo st ON st.id = crd.id_sector_tipo
"""


def _producto_requiere_detalle(item_tipo_nombre):
    """Igual que comprobantes.views._producto_requiere_detalle: True si la
    categoría (item_tipo.nombre) del producto elegido es Producto o
    Servicio -- caso en el que corresponde tener fila en
    comprobante_renglon_detalle."""
    categoria = (item_tipo_nombre or '').strip().lower()
    return categoria in CATEGORIAS_CON_DETALLE


def _calcular_precio_unitario(total, cantidad):
    """Igual que comprobante_renglon_form en Django: el precio unitario
    SIEMPRE se calcula acá (total del renglón / cantidad), nunca se toma de
    lo que mande la UI -- ver forms.ComprobanteRenglonDetalleForm
    (precio_unitario es de solo lectura en el formulario web)."""
    if not cantidad or total is None:
        return None
    try:
        total_dec = total if isinstance(total, Decimal) else Decimal(str(total))
        cantidad_dec = cantidad if isinstance(cantidad, Decimal) else Decimal(str(cantidad))
        if cantidad_dec == 0:
            return None
        return (total_dec / cantidad_dec).quantize(Decimal('0.01'))
    except (InvalidOperation, ZeroDivisionError):
        return None


def listar_renglones(comprobante_id):
    """Igual orden que comprobante_renglon_form en Django: productos/
    servicios primero, iva/otros tributos al final (lectura natural de una
    factura), después por id."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_RENGLON_BASE + ' WHERE cr.id_comprobante = %s', (comprobante_id,))
            filas = cur.fetchall()
    finally:
        conn.close()
    return sorted(
        filas,
        key=lambda f: (0 if _producto_requiere_detalle(f['producto_categoria']) else 1, f['id']),
    )


def obtener_renglon(renglon_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_RENGLON_BASE + ' WHERE cr.id = %s', (renglon_id,))
            return cur.fetchone()
    finally:
        conn.close()


def _siguiente_id_renglon(cur):
    cur.execute('SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM comprobante_renglon')
    return cur.fetchone()['siguiente']


def _categoria_producto_por_id(cur, producto_id):
    cur.execute(
        """SELECT it.nombre FROM producto_detalle p
             LEFT JOIN item_tipo it ON it.id = p.id_item_tipo
            WHERE p.id = %s""",
        (producto_id,),
    )
    fila = cur.fetchone()
    return fila['nombre'] if fila else None


def crear_renglon(datos):
    """datos: id_comprobante, id_producto, total y opcionalmente
    id_cuenta_contable/id_asiento_contable, más los campos de detalle
    (cantidad, id_unidad_de_medida, bonificacion, id_iva_tipo,
    id_sector_tipo) -- estos últimos sólo se guardan si el producto elegido
    es de una categoría que requiere detalle (ver _producto_requiere_detalle),
    igual que comprobante_renglon_form en Django. Devuelve el id asignado
    (MAX(id)+1, igual que Django)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            nuevo_id = _siguiente_id_renglon(cur)
            cur.execute(
                """
                INSERT INTO comprobante_renglon
                    (id, id_comprobante, id_producto, total, id_cuenta_contable, id_asiento_contable)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    nuevo_id, datos['id_comprobante'], datos['id_producto'],
                    datos.get('total'), datos.get('id_cuenta_contable'),
                    datos.get('id_asiento_contable'),
                ),
            )
            categoria = _categoria_producto_por_id(cur, datos['id_producto'])
            if _producto_requiere_detalle(categoria):
                precio_unitario = _calcular_precio_unitario(datos.get('total'), datos.get('cantidad'))
                cur.execute(
                    """
                    INSERT INTO comprobante_renglon_detalle
                        (id, cantidad, id_unidad_de_medida, precio_unitario, bonificacion,
                         id_iva_tipo, id_sector_tipo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        nuevo_id, datos.get('cantidad'), datos.get('id_unidad_de_medida'),
                        precio_unitario, datos.get('bonificacion'),
                        datos.get('id_iva_tipo'), datos.get('id_sector_tipo'),
                    ),
                )
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar_renglon(renglon_id, datos):
    """Misma lógica que crear_renglon para el detalle; además, si la
    categoría del producto elegido ya no requiere detalle pero el renglón
    tenía uno guardado, se borra (huérfano de una categoría anterior) --
    réplica del 'elif detalle is not None: detalle.delete()' de
    comprobante_renglon_form en Django."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE comprobante_renglon SET
                    id_producto=%s, total=%s, id_cuenta_contable=%s, id_asiento_contable=%s
                WHERE id=%s
                """,
                (
                    datos['id_producto'], datos.get('total'),
                    datos.get('id_cuenta_contable'), datos.get('id_asiento_contable'),
                    renglon_id,
                ),
            )
            categoria = _categoria_producto_por_id(cur, datos['id_producto'])
            cur.execute('SELECT id FROM comprobante_renglon_detalle WHERE id = %s', (renglon_id,))
            tenia_detalle = cur.fetchone() is not None

            if _producto_requiere_detalle(categoria):
                precio_unitario = _calcular_precio_unitario(datos.get('total'), datos.get('cantidad'))
                if tenia_detalle:
                    cur.execute(
                        """
                        UPDATE comprobante_renglon_detalle SET
                            cantidad=%s, id_unidad_de_medida=%s, precio_unitario=%s,
                            bonificacion=%s, id_iva_tipo=%s, id_sector_tipo=%s
                        WHERE id=%s
                        """,
                        (
                            datos.get('cantidad'), datos.get('id_unidad_de_medida'), precio_unitario,
                            datos.get('bonificacion'), datos.get('id_iva_tipo'), datos.get('id_sector_tipo'),
                            renglon_id,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO comprobante_renglon_detalle
                            (id, cantidad, id_unidad_de_medida, precio_unitario, bonificacion,
                             id_iva_tipo, id_sector_tipo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            renglon_id, datos.get('cantidad'), datos.get('id_unidad_de_medida'),
                            precio_unitario, datos.get('bonificacion'),
                            datos.get('id_iva_tipo'), datos.get('id_sector_tipo'),
                        ),
                    )
            elif tenia_detalle:
                cur.execute('DELETE FROM comprobante_renglon_detalle WHERE id = %s', (renglon_id,))
        conn.commit()
    finally:
        conn.close()


def eliminar_renglon(renglon_id):
    """Al ser on_delete=CASCADE en Django, borrar el renglón también borra
    su detalle si tenía -- réplica manual (ver comprobante_renglon_eliminar).

    OJO: a diferencia de Movimiento (ver movimientos/repository.py), acá NO
    hay chequeo cruzado contra Cuenta Corriente de Productos porque ese
    módulo todavía no existe del lado escritorio -- si en algún momento se
    porta, agregar acá el mismo chequeo que tiene Django (vía los vínculos
    de este renglón con Movimiento) antes de permitir borrar un renglón que
    ya esté usado."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM comprobante_renglon_detalle WHERE id = %s', (renglon_id,))
            cur.execute('DELETE FROM comprobante_renglon WHERE id = %s', (renglon_id,))
        conn.commit()
    finally:
        conn.close()


def listar_unidades_medida():
    """Excluye IDS_UNIDADES_SOLO_REMITOS (Bolsón/Bolsa) -- a diferencia de
    remitos.repository.listar_unidades_medida, acá SÍ hay que excluirlas:
    esas unidades son sólo para uso interno de Remitos, nunca para un
    comprobante fiscal real."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            marcadores = ','.join(['%s'] * len(IDS_UNIDADES_SOLO_REMITOS))
            cur.execute(
                'SELECT id, nombre FROM comprobante_unidad_de_medida '
                f'WHERE id NOT IN ({marcadores}) ORDER BY nombre',
                IDS_UNIDADES_SOLO_REMITOS,
            )
            return cur.fetchall()
    finally:
        conn.close()


def listar_productos_iva():
    """Productos de categoría Iva (item_tipo.nombre = 'iva'), para el
    desplegable 'tipo de iva' del detalle de un renglón -- mismo filtro que
    ComprobanteRenglonDetalleForm.__init__ en Django."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.nombre FROM producto_detalle p
                  JOIN item_tipo it ON it.id = p.id_item_tipo
                 WHERE LOWER(TRIM(it.nombre)) = %s
                 ORDER BY p.nombre
                """,
                (CATEGORIA_IVA,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def listar_sector_tipos():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre FROM sector_tipo ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Ranking de entidades por monto de comprobantes -- agregado el 2026-09-22.
# Réplica de comprobantes.views._comprobantes_ranking_filtrados /
# _calcular_ranking_entidades / comprobante_ranking_entidades(_excel/_pdf).
# ---------------------------------------------------------------------------

# Mismo id que remitos.repository.ENTIDAD_PROPIA_ID / liquidaciones.views.
# ENTIDAD_PROPIA_ID / movimientos_caja.views.ENTIDAD_PROPIA_ID en Django.
ENTIDAD_PROPIA_ID = 100

# Mismos choices que comprobantes.forms.RankingEntidadesForm.ROL_CHOICES.
ROL_EMISORA = 'emisora'
ROL_RECEPTORA = 'receptora'


def calcular_ranking_entidades(rol=ROL_EMISORA, fecha_desde=None, fecha_hasta=None, excluir_fontana=False):
    """Ranking de entidades por monto total de comprobantes, de mayor a
    menor -- réplica de _comprobantes_ranking_filtrados +
    _calcular_ranking_entidades en Django. 'rol' es el MODO del ranking, no
    un filtro opcional: Comprobante sólo tiene el FK 'id_entidad' (el
    emisor), así que 'emisora' agrupa por las entidades que emitieron el
    comprobante (de las que Fontana recibió) y 'receptora' agrupa por las
    que lo recibieron de Fontana (mismo criterio 'es_emisor' que la
    cabecera). El monto de una Nota de Crédito (que se guarda siempre en
    positivo) se resta en vez de sumarse, igual que en Django. Devuelve
    (ranking, total_general); cada fila trae posicion, entidad_id,
    entidad_nombre, cantidad y total_monto/porcentaje (Decimal)."""
    if rol not in (ROL_EMISORA, ROL_RECEPTORA):
        rol = ROL_EMISORA
    es_emisor = 1 if rol == ROL_EMISORA else 0

    condiciones = ['c.es_emisor = %s']
    parametros_where = [es_emisor]
    if fecha_desde:
        condiciones.append('c.fecha >= %s')
        parametros_where.append(fecha_desde)
    if fecha_hasta:
        condiciones.append('c.fecha <= %s')
        parametros_where.append(fecha_hasta)
    if excluir_fontana:
        condiciones.append('(c.id_entidad IS NULL OR c.id_entidad <> %s)')
        parametros_where.append(ENTIDAD_PROPIA_ID)

    sql = f"""
        SELECT c.id_entidad AS entidad_id, e.nombre AS entidad_nombre,
               SUM(CASE WHEN LOWER(t.nombre) LIKE %s THEN -c.total ELSE c.total END) AS total_monto,
               COUNT(*) AS cantidad
          FROM comprobante c
          LEFT JOIN entidad e ON e.id = c.id_entidad
          LEFT JOIN comprobante_tipo t ON t.id = c.id_tipo_comp
         WHERE {' AND '.join(condiciones)}
         GROUP BY c.id_entidad, e.nombre
         ORDER BY total_monto DESC
    """
    # El patrón LIKE va primero porque en el texto del SQL aparece antes que
    # las condiciones del WHERE (orden posicional de los %s).
    parametros = ['%nota de credito%'] + parametros_where

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            filas = cur.fetchall()
    finally:
        conn.close()

    total_general = sum(
        (Decimal(str(f['total_monto'])) for f in filas if f['total_monto'] is not None), Decimal('0')
    )
    ranking = []
    for posicion, fila in enumerate(filas, start=1):
        monto = Decimal(str(fila['total_monto'])) if fila['total_monto'] is not None else None
        porcentaje = (monto / total_general * 100) if total_general and monto is not None else Decimal('0')
        ranking.append({
            'posicion': posicion,
            'entidad_id': fila['entidad_id'],
            'entidad_nombre': fila['entidad_nombre'],
            'cantidad': fila['cantidad'],
            'total_monto': monto,
            'porcentaje': porcentaje,
        })
    return ranking, total_general


def resultado_ranking_entidades_para_exportar(ranking):
    """Mismo formato que _filas_ranking_entidades en Django, adaptado al
    dict que espera reportes.exportar_excel/exportar_pdf del escritorio."""
    columnas = ['#', 'Entidad', 'Comprobantes', 'Monto total', 'Participación %']
    filas = [
        [
            fila['posicion'],
            fila['entidad_nombre'] or 'Sin entidad',
            fila['cantidad'],
            float(fila['total_monto']) if fila['total_monto'] is not None else None,
            float(fila['porcentaje']) if fila['porcentaje'] is not None else None,
        ]
        for fila in ranking
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': {3, 4},
        'anchos': [0.4, 2.2, 1.0, 1.2, 1.2],
    }
