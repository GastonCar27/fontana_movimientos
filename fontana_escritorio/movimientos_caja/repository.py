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
receptor (`movimiento_caja_banco_cuenta_entidad`) y `movimiento_caja_
reporte`/`movimiento_caja_ranking_entidades`. "Estado de caja" (calcular
normal + "calcular por defecto"), en cambio, sí está: ver más abajo.
"""
from decimal import Decimal

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


# ---------------------------------------------------------------------------
# Estado de caja: mismo alcance que movimientos_caja/views.py del lado
# Django (ver ese archivo, sección "Estado de caja"), calculado a mano por
# SQL en vez de con el ORM -- dos modos:
#
#   - "Calcular" (calcular_estado_caja): saldo del último libro de una o
#     más cajas elegidas a una fecha (saldo inicial + movimientos firmes,
#     con proyección de los movimientos con diferido futuro).
#   - "Calcular por defecto" (calcular_estado_caja_defecto): fórmula
#     específica para Macro (saldo inicial + "cheques en cartera" +
#     proyección de "Pagos Futuros") y Nación (saldo inicial + "cheques en
#     cartera", sin pagos futuros), más un saldo Global = Macro + Nación
#     por fecha. No incluye "vencidos" (omitido a pedido de Gastón).
#
# Convención de signo (igual que en toda la pantalla): negativo = a favor
# nuestro, positivo = le debemos al banco; los montos ya vienen cargados
# así, no hace falta invertir nada.
# ---------------------------------------------------------------------------

NOMBRE_CAJA_MACRO = 'Macro'
NOMBRE_CAJA_NACION = 'Nación'
NOMBRE_CAJA_PAGOS_FUTUROS = 'Pagos Futuros'
NOMBRE_TIPO_CHEQUE = 'Cheque'
NOMBRE_CONCEPTO_CARTERA = 'Cartera'


def _ultimo_libro_de_caja(cur, caja_id):
    """El libro 'vigente' de una caja: el de fecha_creacion más reciente
    (los que todavía no tienen fecha_creacion cargada quedan al final, con
    el id como desempate) -- mismo criterio que
    movimientos_caja.views._ultimo_libro_de_caja."""
    cur.execute(
        """
        SELECT id, nombre, saldo_inicial, fecha_creacion
          FROM banco_cuenta_libro
         WHERE id_bancocuenta = %s
         ORDER BY (fecha_creacion IS NULL) ASC, fecha_creacion DESC, id DESC
         LIMIT 1
        """,
        (caja_id,),
    )
    return cur.fetchone()


def _movimientos_sin_libro(cur, caja_id):
    cur.execute(
        """
        SELECT COUNT(*) AS total
          FROM movimiento_caja mc
          LEFT JOIN bancocuentalibro_movim lm ON lm.id = mc.id
         WHERE mc.idBancoCuenta = %s AND lm.id IS NULL
        """,
        (caja_id,),
    )
    return cur.fetchone()['total']


def _total_firme_de_libro(cur, libro_id, fecha):
    """Suma de los movimientos cargados en ESE libro que ya impactan el
    saldo a la fecha dada: sin diferido, o con diferido <= fecha."""
    cur.execute(
        """
        SELECT SUM(mc.monto) AS total
          FROM movimiento_caja mc
          JOIN bancocuentalibro_movim lm ON lm.id = mc.id
          LEFT JOIN movimiento_caja_diferido d ON d.id = mc.id
         WHERE lm.id_libro = %s AND (d.diferido IS NULL OR d.diferido <= %s)
        """,
        (libro_id, fecha),
    )
    return cur.fetchone()['total'] or Decimal('0')


def _pendientes_de_libro(cur, libro_id, fecha):
    """Movimientos de ESE libro con diferido posterior a la fecha elegida,
    agrupados por día, para la proyección hacia adelante."""
    cur.execute(
        """
        SELECT d.diferido AS fecha, SUM(mc.monto) AS total_dia
          FROM movimiento_caja mc
          JOIN bancocuentalibro_movim lm ON lm.id = mc.id
          JOIN movimiento_caja_diferido d ON d.id = mc.id
         WHERE lm.id_libro = %s AND d.diferido > %s
         GROUP BY d.diferido
         ORDER BY d.diferido
        """,
        (libro_id, fecha),
    )
    return cur.fetchall()


def calcular_estado_caja(caja, fecha):
    """caja: dict con al menos 'id' y 'nombre' (una fila de listar_cajas).
    Devuelve el mismo dict que movimientos_caja.views._calcular_estado_
    caja: libro, saldo_inicial, saldo_a_fecha y la proyección de
    movimientos con diferido futuro."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            libro = _ultimo_libro_de_caja(cur, caja['id'])
            movimientos_sin_libro = _movimientos_sin_libro(cur, caja['id'])
            if libro is None:
                return {
                    'caja': caja, 'libro': None, 'saldo_inicial': None, 'saldo_a_fecha': None,
                    'movimientos_sin_libro': movimientos_sin_libro, 'proyeccion': [],
                }

            saldo_inicial = libro['saldo_inicial'] if libro['saldo_inicial'] is not None else Decimal('0')
            total_firme = _total_firme_de_libro(cur, libro['id'], fecha)
            saldo_a_fecha = saldo_inicial + total_firme

            proyeccion = []
            saldo_corriendo = saldo_a_fecha
            for fila in _pendientes_de_libro(cur, libro['id'], fecha):
                saldo_corriendo = saldo_corriendo + fila['total_dia']
                proyeccion.append({'fecha': fila['fecha'], 'monto_dia': fila['total_dia'], 'saldo': saldo_corriendo})

            return {
                'caja': caja, 'libro': libro, 'saldo_inicial': saldo_inicial, 'saldo_a_fecha': saldo_a_fecha,
                'movimientos_sin_libro': movimientos_sin_libro, 'proyeccion': proyeccion,
            }
    finally:
        conn.close()


def resultado_estado_caja_para_exportar(fecha, resultados):
    """Arma una única tabla (para reportes.exportar_excel/exportar_pdf) con
    la fecha compartida en la primera columna y, por cada caja, un par de
    columnas Movimiento/Saldo -- igual formato que
    movimientos_caja.views._tabla_estado_caja del lado Django."""
    columnas = ['Fecha']
    for r in resultados:
        nombre = f"{r['caja']['id']} - {r['caja']['nombre']}"
        columnas.append(f'{nombre} - Movimiento')
        columnas.append(f'{nombre} - Saldo')

    fila_inicial = [fecha]
    saldo_corriente = []
    for r in resultados:
        fila_inicial.append(None)
        fila_inicial.append(r['saldo_a_fecha'])
        saldo_corriente.append(r['saldo_a_fecha'])
    filas = [fila_inicial]

    proyeccion_por_caja = [{p['fecha']: p for p in r['proyeccion']} for r in resultados]
    fechas_futuras = sorted({p['fecha'] for r in resultados for p in r['proyeccion']})
    for dia in fechas_futuras:
        fila = [dia]
        for indice in range(len(resultados)):
            entrada = proyeccion_por_caja[indice].get(dia)
            if entrada:
                saldo_corriente[indice] = entrada['saldo']
                fila.append(entrada['monto_dia'])
                fila.append(entrada['saldo'])
            else:
                fila.append(None)
                fila.append(saldo_corriente[indice])
        filas.append(fila)

    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': set(range(1, len(columnas))),
        'anchos': [0.9] + [1.1] * (len(columnas) - 1),
    }


def _cajas_por_prefijo(cur, nombre):
    """Cajas cuyo nombre empieza con `nombre` -- las cajas 'Macro' y
    'Nación' están cargadas con la sucursal en el nombre (ej. 'Macro -
    Campo Grande', 'Nación - Oberá'), así que se busca por prefijo, nunca
    por nombre exacto (mismo fix que se aplicó en Django el 2026-09-15)."""
    cur.execute('SELECT id, nombre FROM bancocuenta WHERE nombre LIKE %s', (f'{nombre}%',))
    return cur.fetchall()


def _resolver_caja_o_error(cur, nombre, errores, opcional=False):
    candidatos = _cajas_por_prefijo(cur, nombre)
    if len(candidatos) == 1:
        return candidatos[0]
    if not candidatos:
        sufijo = ' -- no se van a proyectar pagos futuros.' if opcional else '.'
        errores.append(f'No se encontró ninguna caja cuyo nombre empiece con "{nombre}"{sufijo}')
    else:
        nombres = ', '.join(f'"{c["nombre"]}"' for c in candidatos)
        errores.append(
            f'Hay más de una caja cuyo nombre empieza con "{nombre}" ({nombres}); no se pudo elegir cuál usar.'
        )
    return None


def _cheques_en_cartera(cur, caja_id):
    """Suma de los movimientos de esa caja que son tipo 'Cheque', concepto
    'Cartera', sin diferido y todavía sin efectivizar."""
    cur.execute(
        """
        SELECT SUM(mc.monto) AS total
          FROM movimiento_caja mc
          JOIN bancocuenta_tipomovim t ON t.id = mc.id_tipoMov
          JOIN movimiento_caja_concepto mcc ON mcc.id = mc.id
          JOIN movimiento_caja_concepto_tipo ct ON ct.id = mcc.id_concepto
          LEFT JOIN movimiento_caja_diferido d ON d.id = mc.id
         WHERE mc.idBancoCuenta = %s
           AND LOWER(t.nombre) = LOWER(%s)
           AND LOWER(ct.nombre) = LOWER(%s)
           AND mc.efectivizacion IS NULL
           AND (d.id IS NULL OR d.diferido IS NULL)
        """,
        (caja_id, NOMBRE_TIPO_CHEQUE, NOMBRE_CONCEPTO_CARTERA),
    )
    return cur.fetchone()['total'] or Decimal('0')


def _saldo_base_defecto(cur, caja, fecha):
    """Primer renglón del cálculo 'por defecto' para una caja: saldo
    inicial del último libro + los cheques en cartera de esa caja, en una
    fila rotulada 'Cheques en cartera' -- igual que
    movimientos_caja.views._saldo_base_defecto."""
    libro = _ultimo_libro_de_caja(cur, caja['id'])
    if libro is None:
        return {'caja': caja, 'libro': None, 'saldo_inicial': None, 'filas': [], 'saldo_final': None}

    saldo_inicial = libro['saldo_inicial'] if libro['saldo_inicial'] is not None else Decimal('0')
    cartera = _cheques_en_cartera(cur, caja['id'])
    saldo = saldo_inicial + cartera
    return {
        'caja': caja,
        'libro': libro,
        'saldo_inicial': saldo_inicial,
        'filas': [{'fecha': fecha, 'concepto': 'Cheques en cartera', 'monto': cartera, 'saldo': saldo}],
        'saldo_final': saldo,
    }


def _pagos_futuros_pendientes(cur, caja_pagos_futuros, fecha):
    """Movimientos de la caja 'Pagos Futuros' con diferido posterior a la
    elegida, agrupados por día -- los de fecha igual o anterior se ignoran
    (son errores de carga, no pagos pendientes reales, confirmado por
    Gastón)."""
    if caja_pagos_futuros is None:
        return []
    cur.execute(
        """
        SELECT d.diferido AS fecha, SUM(mc.monto) AS total_dia
          FROM movimiento_caja mc
          JOIN movimiento_caja_diferido d ON d.id = mc.id
         WHERE mc.idBancoCuenta = %s AND d.diferido > %s
         GROUP BY d.diferido
         ORDER BY d.diferido
        """,
        (caja_pagos_futuros['id'], fecha),
    )
    return cur.fetchall()


def calcular_estado_caja_defecto(fecha):
    """Réplica exacta, en SQL a mano, de movimientos_caja.views._calcular_
    estado_caja_defecto: ver ese archivo para la explicación completa de la
    fórmula. No incluye "vencidos" (omitido a pedido de Gastón)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            errores = []
            caja_macro = _resolver_caja_o_error(cur, NOMBRE_CAJA_MACRO, errores)
            caja_nacion = _resolver_caja_o_error(cur, NOMBRE_CAJA_NACION, errores)
            caja_pagos_futuros = _resolver_caja_o_error(cur, NOMBRE_CAJA_PAGOS_FUTUROS, errores, opcional=True)

            macro = _saldo_base_defecto(cur, caja_macro, fecha) if caja_macro else None
            nacion = _saldo_base_defecto(cur, caja_nacion, fecha) if caja_nacion else None

            if macro is not None and macro['libro'] is not None:
                saldo_corriendo = macro['saldo_final']
                for pago in _pagos_futuros_pendientes(cur, caja_pagos_futuros, fecha):
                    saldo_corriendo = saldo_corriendo + pago['total_dia']
                    macro['filas'].append({
                        'fecha': pago['fecha'], 'concepto': 'Pagos futuros',
                        'monto': pago['total_dia'], 'saldo': saldo_corriendo,
                    })
                macro['saldo_final'] = saldo_corriendo

            macro_filas_por_fecha = {f['fecha']: f for f in macro['filas']} if macro else {}
            saldo_nacion_constante = nacion['saldo_final'] if nacion else None
            fechas = {fecha} | set(macro_filas_por_fecha.keys())

            filas_global = []
            ultimo_macro = None
            for f in sorted(fechas):
                fila_macro = macro_filas_por_fecha.get(f)
                if fila_macro is not None:
                    ultimo_macro = fila_macro['saldo']
                total = (
                    ultimo_macro + saldo_nacion_constante
                    if ultimo_macro is not None and saldo_nacion_constante is not None else None
                )
                filas_global.append({
                    'fecha': f,
                    'macro_concepto': fila_macro['concepto'] if fila_macro else None,
                    'macro_monto': fila_macro['monto'] if fila_macro else None,
                    'saldo_macro': ultimo_macro,
                    'saldo_nacion': saldo_nacion_constante,
                    'saldo_global': total,
                })

            return {'fecha': fecha, 'macro': macro, 'nacion': nacion, 'filas_global': filas_global, 'errores': errores}
    finally:
        conn.close()


def resultado_estado_caja_defecto_para_exportar(datos):
    columnas = ['Fecha', 'Macro - Concepto', 'Macro - Movimiento', 'Macro - Saldo', 'Nación - Saldo', 'Global - Saldo']
    filas = [
        [f['fecha'], f['macro_concepto'], f['macro_monto'], f['saldo_macro'], f['saldo_nacion'], f['saldo_global']]
        for f in datos['filas_global']
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': {2, 3, 4, 5},
        'anchos': [0.9, 1.6, 1.1, 1.1, 1.1, 1.1],
    }
