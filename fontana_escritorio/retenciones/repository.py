"""
Acceso a datos de Retenciones (tabla `retencion`, más los catálogos
`retencion_tipo_impuesto` / `retencion_tipo_regimen`), alcance genérico --
replica retenciones/views.py, retenciones/forms.py del sitio Django.

Un "comprobante de retención" (lo que se ve como una fila en el listado)
en realidad son N filas de la tabla `retencion` que comparten el mismo
(año, numero): cada fila es un renglón -- una factura del proveedor sobre
la que se practicó la retención. Todos los renglones de un mismo
comprobante comparten proveedor (entidad/entidad_nombre) e
impuesto/régimen -- mismo criterio que RetencionHeaderForm +
RetencionRenglonFormSet en Django.

IMPORTANTE:
- `retencion.id` NO tiene AUTO_INCREMENT real: el próximo id se calcula a
  mano (MAX(id)+1) y se asigna renglón por renglón dentro de un mismo alta,
  igual que `retenciones.views._siguiente_id_retencion`.
- Modificar un comprobante de retención NO actualiza fila por fila: borra
  TODOS los renglones de ese (año, numero) y los vuelve a crear -- incluso
  pudiendo cambiar de año/número -- igual que
  `retenciones.views.retencion_modificar`.
- Antes de modificar o eliminar un comprobante se verifica que ninguno de
  sus renglones esté ya incluido en una Liquidación (tabla
  `liquidacion_retencion`, con `ON DELETE RESTRICT` hacia `retencion` en la
  base): si lo está, no se permite -- mismo criterio que
  `retenciones.views._tiene_liquidacion`. El módulo de Liquidaciones
  todavía no está construido acá, pero esta verificación no lo necesita:
  alcanza con consultar esa tabla directo por SQL.
- Los campos AFIP/legacy de la tabla (`id_condicion`, `porcentaje_exclusion`,
  `tipo_doc_entidad`, `id_operacion`, `numero_certificado_afip`) tampoco los
  completa la vista Django de alta/modificación -- acá se dejan igual de
  vacíos (no se replican porque no forman parte de este alcance genérico).

Fuera de alcance por ahora (ver README.md): la impresión "Constancia de
Retención" en PDF/Excel de un comprobante puntual (retencion_pdf /
retencion_excel en Django).
"""
from db import get_connection

SQL_LISTAR_RENGLONES = """
    SELECT r.id, r.año, r.numero, r.id_entidad, r.entidad_nombre,
           e.nombre AS entidad_nombre_actual,
           r.id_impuesto, ri.nombre AS impuesto_nombre,
           r.id_regimen, rr.nombre AS regimen_nombre,
           r.tipo_comp_origen, ct.abreviatura AS tipo_comp_origen_abrev,
           r.comprobante_origen, r.fecha_comp_origen,
           r.subtotal, r.porcentaje, r.total, r.fecha, r.comprobante_string
      FROM retencion r
      LEFT JOIN entidad e ON e.id = r.id_entidad
      LEFT JOIN retencion_tipo_impuesto ri ON ri.id = r.id_impuesto
      LEFT JOIN retencion_tipo_regimen rr ON rr.id = r.id_regimen
      LEFT JOIN comprobante_tipo ct ON ct.id = r.tipo_comp_origen
"""


# ---------------------------------------------------------------------------
# Helpers de numeración / cálculo (mismo criterio que retenciones/views.py)
# ---------------------------------------------------------------------------

def _siguiente_id(cur):
    cur.execute('SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM retencion')
    return cur.fetchone()['siguiente']


def _siguiente_numero(cur, anio):
    cur.execute('SELECT COALESCE(MAX(numero), 0) + 1 AS siguiente FROM retencion WHERE `año` = %s', (anio,))
    return cur.fetchone()['siguiente']


def siguiente_numero_sugerido(anio):
    """Numeración sugerida para un año (editable por el usuario), igual que
    el `initial` de RetencionHeaderForm en el alta Django."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            return _siguiente_numero(cur, anio)
    finally:
        conn.close()


def calcular_total(subtotal, porcentaje):
    """total = subtotal * porcentaje / 100, redondeado a 2 decimales
    (ROUND_HALF_UP) -- igual que `retenciones.views._calcular_total`."""
    if subtotal is None or porcentaje is None:
        return None
    from decimal import Decimal, ROUND_HALF_UP
    return (Decimal(str(subtotal)) * Decimal(str(porcentaje)) / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def combinar_comprobante_origen(punto_venta, numero_comprobante):
    """'PPPPP-NNNNNNNN', igual que
    `retenciones.views._combinar_comprobante_origen`."""
    if punto_venta is None or numero_comprobante is None:
        return None
    return f'{int(punto_venta):05d}-{int(numero_comprobante):08d}'


def parsear_comprobante_origen(valor):
    """Inverso de combinar_comprobante_origen, para precargar el formulario
    de edición -- igual que `retenciones.views._parsear_comprobante_origen`."""
    if not valor or '-' not in valor:
        return None, None
    izquierda, derecha = valor.split('-', 1)
    try:
        return int(izquierda), int(derecha)
    except ValueError:
        return None, None


# ---------------------------------------------------------------------------
# Catálogos: tipos de comprobante (para el combo del renglón)
# ---------------------------------------------------------------------------

def listar_tipos_comprobante():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre, abreviatura FROM comprobante_tipo ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Listado (agrupado por año+numero, igual que retenciones.views.retencion_listado)
# ---------------------------------------------------------------------------

def listar(filtro_anio='', filtro_numero='', filtro_entidad=''):
    condiciones = []
    parametros = []
    if filtro_anio:
        if not filtro_anio.isdigit():
            return []
        condiciones.append('r.`año` = %s')
        parametros.append(int(filtro_anio))
    if filtro_numero:
        if not filtro_numero.isdigit():
            return []
        condiciones.append('r.numero = %s')
        parametros.append(int(filtro_numero))
    if filtro_entidad:
        comodin = f'%{filtro_entidad}%'
        condiciones.append('(r.entidad_nombre LIKE %s OR e.nombre LIKE %s)')
        parametros.extend([comodin, comodin])

    sql = SQL_LISTAR_RENGLONES
    if condiciones:
        sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' ORDER BY r.`año` DESC, r.numero DESC, r.id ASC'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            filas = cur.fetchall()
    finally:
        conn.close()

    grupos = {}
    orden_grupos = []
    for fila in filas:
        clave = (fila['año'], fila['numero'])
        if clave not in grupos:
            grupos[clave] = {
                'año': fila['año'],
                'numero': fila['numero'],
                'entidad_nombre': fila['entidad_nombre'] or fila['entidad_nombre_actual'] or '',
                'fecha': fila['fecha'],
                'cantidad_renglones': 0,
                'total': 0,
            }
            orden_grupos.append(clave)
        grupos[clave]['cantidad_renglones'] += 1
        if fila['total'] is not None:
            grupos[clave]['total'] += fila['total']
        if fila['fecha'] and (grupos[clave]['fecha'] is None or fila['fecha'] > grupos[clave]['fecha']):
            grupos[clave]['fecha'] = fila['fecha']

    return [grupos[clave] for clave in orden_grupos][:500]


def obtener_renglones(anio, numero):
    """Todos los renglones (filas de `retencion`) de un mismo comprobante
    (año, numero), igual que `retenciones.views._grupo_queryset`."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                SQL_LISTAR_RENGLONES + ' WHERE r.`año` = %s AND r.numero = %s ORDER BY r.id',
                (anio, numero),
            )
            return cur.fetchall()
    finally:
        conn.close()


def tiene_liquidacion(anio, numero):
    """True si algún renglón de este comprobante ya está incluido en una
    Liquidación (tabla `liquidacion_retencion`) -- igual que
    `retenciones.views._tiene_liquidacion`. No hace falta tener el módulo de
    Liquidaciones construido para esta verificación: se consulta la tabla
    directo."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM liquidacion_retencion lr
                   JOIN retencion r ON r.id = lr.id_retencion
                   WHERE r.`año` = %s AND r.numero = %s LIMIT 1""",
                (anio, numero),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Alta / Modificación / Eliminación de un comprobante de retención completo
# ---------------------------------------------------------------------------

def guardar_grupo(cabecera, renglones):
    """Crea los renglones (filas `retencion`) de un comprobante nuevo.
    `cabecera`: dict con id_entidad, entidad_nombre, id_impuesto, id_regimen,
    año, numero. `renglones`: lista de dicts con tipo_comp_origen,
    punto_venta, numero_comprobante, fecha_comp_origen, subtotal,
    porcentaje. Devuelve la lista de ids creados.

    Réplica de `retenciones.views._guardar_grupo`: un id manual por renglón
    (MAX(id)+1 incrementando), comprobante_string = 'AAAA-NNNN',
    comprobante_origen combinado, fecha = fecha_comp_origen,
    monto_comp_origen = subtotal, agregado_desde = 'retenciones_app'."""
    anio = cabecera['año']
    numero = cabecera['numero']
    comprobante_string = f'{anio}-{numero:04d}'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            siguiente_id = _siguiente_id(cur)
            creados = []
            for renglon in renglones:
                subtotal = renglon.get('subtotal')
                porcentaje = renglon.get('porcentaje')
                total = calcular_total(subtotal, porcentaje)
                comprobante_origen = combinar_comprobante_origen(
                    renglon.get('punto_venta'), renglon.get('numero_comprobante')
                )
                cur.execute(
                    """
                    INSERT INTO retencion
                        (id, id_entidad, entidad_nombre, subtotal, porcentaje, total,
                         comprobante_string, fecha, id_impuesto, id_regimen,
                         tipo_comp_origen, comprobante_origen, fecha_comp_origen,
                         monto_comp_origen, `año`, numero, agregado_desde)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        siguiente_id,
                        cabecera.get('id_entidad'), cabecera.get('entidad_nombre'),
                        subtotal, porcentaje, total,
                        comprobante_string, renglon.get('fecha_comp_origen'),
                        cabecera.get('id_impuesto'), cabecera.get('id_regimen'),
                        renglon.get('tipo_comp_origen'), comprobante_origen,
                        renglon.get('fecha_comp_origen'), subtotal,
                        anio, numero, 'retenciones_app',
                    ),
                )
                creados.append(siguiente_id)
                siguiente_id += 1
        conn.commit()
        return creados
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def modificar_grupo(anio_actual, numero_actual, cabecera, renglones):
    """Borra todos los renglones de (anio_actual, numero_actual) y crea los
    nuevos (que pueden quedar con otro año/número, según `cabecera`) --
    igual que `retenciones.views.retencion_modificar`. Devuelve la lista de
    ids creados.

    OJO: llamar primero a `tiene_liquidacion(anio_actual, numero_actual)` y
    no invocar esta función si da True (la UI hace ese chequeo antes)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM retencion WHERE `año` = %s AND numero = %s',
                (anio_actual, numero_actual),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return guardar_grupo(cabecera, renglones)


def eliminar_grupo(anio, numero):
    """Elimina todos los renglones de un comprobante de retención -- igual
    que `retenciones.views.retencion_eliminar`. OJO: llamar primero a
    `tiene_liquidacion(anio, numero)` y no invocar esta función si da True
    (la UI hace ese chequeo antes)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM retencion WHERE `año` = %s AND numero = %s', (anio, numero))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Catálogo: Ret. Impuestos
# ---------------------------------------------------------------------------

def listar_tipos_impuesto():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre FROM retencion_tipo_impuesto ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


def crear_tipo_impuesto(nombre):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM retencion_tipo_impuesto')
            nuevo_id = cur.fetchone()['siguiente']
            cur.execute(
                'INSERT INTO retencion_tipo_impuesto (id, nombre) VALUES (%s, %s)',
                (nuevo_id, nombre),
            )
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar_tipo_impuesto(impuesto_id, nombre):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE retencion_tipo_impuesto SET nombre = %s WHERE id = %s',
                (nombre, impuesto_id),
            )
        conn.commit()
    finally:
        conn.close()


def tipo_impuesto_en_uso(impuesto_id):
    """Igual que `retenciones.views.retencion_tipo_impuesto_eliminar`: se
    bloquea si está referenciado por una retención o por un régimen (la FK
    real está declarada DO_NOTHING y no lo impediría en la base)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM retencion WHERE id_impuesto = %s LIMIT 1', (impuesto_id,))
            if cur.fetchone():
                return True
            cur.execute('SELECT 1 FROM retencion_tipo_regimen WHERE id_impuesto = %s LIMIT 1', (impuesto_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def eliminar_tipo_impuesto(impuesto_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM retencion_tipo_impuesto WHERE id = %s', (impuesto_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Catálogo: Ret. Regímenes
# ---------------------------------------------------------------------------

def listar_tipos_regimen():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT r.id, r.nombre, r.id_impuesto, i.nombre AS impuesto_nombre
                     FROM retencion_tipo_regimen r
                     LEFT JOIN retencion_tipo_impuesto i ON i.id = r.id_impuesto
                    ORDER BY r.nombre"""
            )
            return cur.fetchall()
    finally:
        conn.close()


def crear_tipo_regimen(id_impuesto, nombre):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM retencion_tipo_regimen')
            nuevo_id = cur.fetchone()['siguiente']
            cur.execute(
                'INSERT INTO retencion_tipo_regimen (id, id_impuesto, nombre) VALUES (%s, %s, %s)',
                (nuevo_id, id_impuesto, nombre),
            )
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar_tipo_regimen(regimen_id, id_impuesto, nombre):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE retencion_tipo_regimen SET id_impuesto = %s, nombre = %s WHERE id = %s',
                (id_impuesto, nombre, regimen_id),
            )
        conn.commit()
    finally:
        conn.close()


def tipo_regimen_en_uso(regimen_id):
    """Igual que `retenciones.views.retencion_tipo_regimen_eliminar`."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM retencion WHERE id_regimen = %s LIMIT 1', (regimen_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def eliminar_tipo_regimen(regimen_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM retencion_tipo_regimen WHERE id = %s', (regimen_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Ranking de entidades por monto total de retenciones (con filtro de fecha y
# exclusión opcional de Fontana) -- igual que
# `retenciones.views.retencion_ranking_entidades` /
# `_calcular_ranking_retenciones`.
# ---------------------------------------------------------------------------

ENTIDAD_PROPIA_ID = 100


def ranking_entidades(fecha_desde=None, fecha_hasta=None, excluir_fontana=False):
    condiciones = []
    parametros = []
    if fecha_desde:
        condiciones.append('r.fecha >= %s')
        parametros.append(fecha_desde)
    if fecha_hasta:
        condiciones.append('r.fecha <= %s')
        parametros.append(fecha_hasta)
    if excluir_fontana:
        condiciones.append('(r.id_entidad IS NULL OR r.id_entidad <> %s)')
        parametros.append(ENTIDAD_PROPIA_ID)

    sql = """
        SELECT r.id_entidad, e.nombre AS entidad_nombre,
               SUM(r.total) AS total_monto, COUNT(*) AS cantidad
          FROM retencion r
          LEFT JOIN entidad e ON e.id = r.id_entidad
    """
    if condiciones:
        sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' GROUP BY r.id_entidad, e.nombre ORDER BY total_monto DESC'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            filas = cur.fetchall()
    finally:
        conn.close()

    from decimal import Decimal
    total_general = sum((f['total_monto'] for f in filas if f['total_monto'] is not None), Decimal('0'))
    for posicion, fila in enumerate(filas, start=1):
        fila['posicion'] = posicion
        fila['porcentaje'] = (
            fila['total_monto'] / total_general * 100
            if total_general and fila['total_monto'] is not None else Decimal('0')
        )
    return filas, total_general


def resultado_ranking_para_exportar(filas):
    """Arma el dict {columnas, filas, columnas_numericas, anchos} que espera
    `reportes.exportar_excel/exportar_pdf`, igual criterio que
    `retenciones.views._filas_ranking_retenciones`."""
    columnas = ['#', 'Entidad', 'Retenciones', 'Monto total', 'Participación %']
    filas_tabla = [
        [
            f['posicion'],
            f['entidad_nombre'] or 'Sin nombre',
            f['cantidad'],
            float(f['total_monto']) if f['total_monto'] is not None else None,
            float(f['porcentaje']) if f['porcentaje'] is not None else None,
        ]
        for f in filas
    ]
    return {
        'columnas': columnas,
        'filas': filas_tabla,
        'columnas_numericas': {3, 4},
        'anchos': [0.4, 2.2, 1.0, 1.2, 1.2],
    }
