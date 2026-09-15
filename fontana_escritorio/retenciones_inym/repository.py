"""
Acceso a datos de Retenciones INYM (tabla `retencion_inym`).

Hasta hace poco, el app Django `retenciones_inym` NO tenía vistas de alta/
edición/eliminación ni listado propio (solo `ranking-entidades/` y sus
exportaciones a Excel/PDF) -- eso se agregó recién ahora, tanto acá como
del lado Django (`retenciones_inym/views.py` +
`RetencionInymForm`), a pedido de Gastón. A diferencia de `retencion`
(donde varias filas comparten año+número y forman "un comprobante"), acá
cada fila de `retencion_inym` es un registro completo en sí mismo -- no
hay agrupamiento.

El campo `eliminacion` NO es una baja lógica de esta app: es un dato que
viene tal cual del registro oficial de INYM (la fecha en la que esa
retención fue anulada/eliminada del lado de INYM, según el Excel que
Gastón usa para importar), así que se conserva como cualquier otro campo
-- se puede cargar/editar a mano, y el importador de ese Excel (ver
`importador.py`, agregado el 2026-09-15) lo completa solo cuando corresponde.

`id_certificado_inym` guarda el N° de certificado que trae ese Excel
(columna IDCERTIFICADO). OJO: no es único por sí solo -- INYM lo numera
por separado para cada tipo de tarifa -- así que la clave real de
no-duplicado al importar es (id_certificado_inym, id_tipo_tarifa). Requiere
la columna nueva agregada con
sql/2026-09-15_agregar_id_certificado_inym.sql (ver ese script, y
correrlo en cada base -- primero en la de pruebas, después en producción --
antes de usar el importador o el alta/edición contra esa base).

Las tablas `retencion_inym_no_aplicacion` y `retencion_inym_origen` no se
usan desde ninguna vista Django (la segunda incluso tiene comentarios del
propio autor del modelo diciendo que no está claro para qué se usa), así
que tampoco se replican acá.
"""
from decimal import Decimal, ROUND_HALF_UP

from db import get_connection

ENTIDAD_PROPIA_ID = 100

SQL_LISTAR = """
    SELECT ri.id, ri.fecha, ri.periodo, ri.kgs, ri.total, ri.tarifa, ri.eliminacion,
           ri.id_certificado_inym,
           ri.id_tipo_tarifa, it.nombre AS tipo_tarifa_nombre,
           ri.id_operador_emisor, oe.id_entidad AS emisor_id_entidad,
           ee.nombre AS emisor_nombre,
           ri.id_operador_retenido, orx.id_entidad AS retenido_id_entidad,
           er.nombre AS retenido_nombre
      FROM retencion_inym ri
      LEFT JOIN inym_retencion_tipo it ON it.id = ri.id_tipo_tarifa
      LEFT JOIN inym_operador oe ON oe.id = ri.id_operador_emisor
      LEFT JOIN entidad ee ON ee.id = oe.id_entidad
      LEFT JOIN inym_operador orx ON orx.id = ri.id_operador_retenido
      LEFT JOIN entidad er ON er.id = orx.id_entidad
"""


def _siguiente_id(cur):
    cur.execute('SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM retencion_inym')
    return cur.fetchone()['siguiente']


def calcular_total(kgs, tarifa):
    """total = kgs × tarifa, redondeado a 2 decimales -- mismo criterio que
    `RetencionInymForm.clean()` del lado Django."""
    if kgs is None or tarifa is None:
        return None
    return (Decimal(str(kgs)) * Decimal(str(tarifa))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def listar_tipos_tarifa():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, nombre FROM inym_retencion_tipo ORDER BY nombre')
            return cur.fetchall()
    finally:
        conn.close()


def obtener(retencion_inym_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SQL_LISTAR + ' WHERE ri.id = %s', (retencion_inym_id,))
            return cur.fetchone()
    finally:
        conn.close()


def tiene_liquidacion(retencion_inym_id):
    """True si esta retención INYM ya está incluida en una Liquidación
    (tabla `liquidacion_retencion_inym`, con `ON DELETE RESTRICT` real
    hacia `retencion_inym`) -- mismo criterio que
    `retenciones.repository.tiene_liquidacion`, para no dejar modificar/
    eliminar un registro que una Liquidación ya está usando. No hace falta
    tener el módulo de Liquidaciones construido: se consulta la tabla
    directo."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT 1 FROM liquidacion_retencion_inym WHERE id_retencion_inym = %s LIMIT 1',
                (retencion_inym_id,),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def crear(datos):
    """datos: dict con fecha, periodo, id_tipo_tarifa, id_operador_emisor,
    id_operador_retenido, kgs, tarifa, total, eliminacion. Si vienen kgs y
    tarifa, el total se recalcula acá (kgs × tarifa); si falta alguno de
    los dos, se respeta el total tal como se cargó (por ejemplo un
    registro importado que ya trae el total pero no siempre kgs/tarifa
    desglosados). Devuelve el id asignado (MAX(id)+1, igual que Django)."""
    total = datos.get('total')
    if datos.get('kgs') is not None and datos.get('tarifa') is not None:
        total = calcular_total(datos['kgs'], datos['tarifa'])

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            nuevo_id = _siguiente_id(cur)
            cur.execute(
                """
                INSERT INTO retencion_inym
                    (id, fecha, periodo, id_tipo_tarifa, id_operador_emisor,
                     id_operador_retenido, kgs, tarifa, total, eliminacion,
                     id_certificado_inym, agregado_desde)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    nuevo_id, datos.get('fecha'), datos.get('periodo'),
                    datos.get('id_tipo_tarifa'), datos.get('id_operador_emisor'),
                    datos.get('id_operador_retenido'), datos.get('kgs'),
                    datos.get('tarifa'), total, datos.get('eliminacion'),
                    datos.get('id_certificado_inym'),
                    datos.get('agregado_desde') or 'retenciones_inym_app',
                ),
            )
        conn.commit()
        return nuevo_id
    finally:
        conn.close()


def actualizar(retencion_inym_id, datos):
    total = datos.get('total')
    if datos.get('kgs') is not None and datos.get('tarifa') is not None:
        total = calcular_total(datos['kgs'], datos['tarifa'])

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE retencion_inym SET
                    fecha=%s, periodo=%s, id_tipo_tarifa=%s, id_operador_emisor=%s,
                    id_operador_retenido=%s, kgs=%s, tarifa=%s, total=%s, eliminacion=%s,
                    id_certificado_inym=%s
                WHERE id=%s
                """,
                (
                    datos.get('fecha'), datos.get('periodo'),
                    datos.get('id_tipo_tarifa'), datos.get('id_operador_emisor'),
                    datos.get('id_operador_retenido'), datos.get('kgs'),
                    datos.get('tarifa'), total, datos.get('eliminacion'),
                    datos.get('id_certificado_inym'),
                    retencion_inym_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def eliminar(retencion_inym_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM retencion_inym WHERE id = %s', (retencion_inym_id,))
        conn.commit()
    finally:
        conn.close()


def listar(filtro_fecha='', filtro_retenido=''):
    """Listado con los mismos 2 filtros que la pantalla Django nueva
    (fecha, operador retenido)."""
    condiciones = []
    parametros = []
    if filtro_fecha:
        condiciones.append('ri.fecha = %s')
        parametros.append(filtro_fecha)
    if filtro_retenido:
        comodin = f'%{filtro_retenido}%'
        condiciones.append('er.nombre LIKE %s')
        parametros.append(comodin)

    sql = SQL_LISTAR
    if condiciones:
        sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' ORDER BY ri.fecha DESC, ri.id DESC LIMIT 500'

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            return cur.fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Importador del Excel de INYM -- recibe las filas ya parseadas por
# `importador.leer_filas_excel` (fechas/Decimal/int normalizados, no texto
# crudo) y hace todo el trabajo de aplicarlas contra la base en una sola
# conexión/transacción: descarta las que ya estén cargadas -- por
# (id_certificado_inym, id_tipo_tarifa), la clave real de no-duplicado --,
# crea el operador/entidad/tipo de operador que falte (conservando el
# mismo ID de operador que trae el Excel, igual que el resto del sistema
# ya usa para ese operador), y omite + reporta las filas cuyo tipo de
# tarifa no existe. Misma lógica, en paralelo, que
# fontana_movimientos/retenciones_inym/importador.py del lado Django.
# ---------------------------------------------------------------------------

def importar_lote(filas, fecha_desde=None, fecha_hasta=None):
    resultado = {
        'total_en_archivo': len([f for f in filas if '_error' not in f]),
        'en_rango_fecha': 0,
        'importadas': 0,
        'duplicadas': 0,
        'operadores_creados': [],
        'tipos_tarifa_no_encontrados': set(),
        'filas_con_error': [(f['fila_excel'], f['_error']) for f in filas if '_error' in f],
    }

    filas_validas = [f for f in filas if '_error' not in f]
    filas_en_rango = [
        f for f in filas_validas
        if f['fecha'] is not None
        and (not fecha_desde or f['fecha'] >= fecha_desde)
        and (not fecha_hasta or f['fecha'] <= fecha_hasta)
    ]
    resultado['en_rango_fecha'] = len(filas_en_rango)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id_certificado_inym, id_tipo_tarifa FROM retencion_inym '
                'WHERE id_certificado_inym IS NOT NULL'
            )
            pares_existentes = {(f['id_certificado_inym'], f['id_tipo_tarifa']) for f in cur.fetchall()}

            cur.execute('SELECT id, nombre FROM inym_retencion_tipo')
            tipos_por_id = {f['id']: f['nombre'] for f in cur.fetchall()}

            cur.execute('SELECT id, id_entidad, id_operador_tipo FROM inym_operador')
            operadores_por_id = {f['id']: f for f in cur.fetchall()}

            cur.execute("SELECT id, cuit FROM entidad WHERE cuit IS NOT NULL AND cuit <> ''")
            entidad_id_por_cuit = {f['cuit']: f['id'] for f in cur.fetchall()}

            cur.execute('SELECT id, nombre FROM inym_operador_tipo')
            tipo_operador_id_por_nombre = {(f['nombre'] or '').strip().upper(): f['id'] for f in cur.fetchall()}

            siguiente_id_retencion = _siguiente_id(cur)
            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM entidad")
            siguiente_id_entidad = cur.fetchone()['siguiente']
            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS siguiente FROM inym_operador_tipo")
            siguiente_id_tipo_operador = cur.fetchone()['siguiente']

            def resolver_operador(id_operador, cuit, nombre, tipo_oper_nombre):
                nonlocal siguiente_id_entidad, siguiente_id_tipo_operador
                if id_operador in operadores_por_id:
                    return id_operador

                cuit_normalizado = (cuit or '').strip()
                id_entidad = entidad_id_por_cuit.get(cuit_normalizado) if cuit_normalizado else None
                if id_entidad is None:
                    id_entidad = siguiente_id_entidad
                    cur.execute(
                        'INSERT INTO entidad (id, nombre, cuit, activo) VALUES (%s, %s, %s, 1)',
                        (
                            id_entidad, (nombre or '').strip() or f'Operador INYM {id_operador}',
                            cuit_normalizado or None,
                        ),
                    )
                    siguiente_id_entidad += 1
                    if cuit_normalizado:
                        entidad_id_por_cuit[cuit_normalizado] = id_entidad

                nombre_tipo = (tipo_oper_nombre or '').strip() or 'SIN ESPECIFICAR'
                id_tipo_operador = tipo_operador_id_por_nombre.get(nombre_tipo.upper())
                if id_tipo_operador is None:
                    id_tipo_operador = siguiente_id_tipo_operador
                    cur.execute(
                        'INSERT INTO inym_operador_tipo (id, nombre) VALUES (%s, %s)',
                        (id_tipo_operador, nombre_tipo),
                    )
                    siguiente_id_tipo_operador += 1
                    tipo_operador_id_por_nombre[nombre_tipo.upper()] = id_tipo_operador

                cur.execute(
                    'INSERT INTO inym_operador (id, id_entidad, id_operador_tipo) VALUES (%s, %s, %s)',
                    (id_operador, id_entidad, id_tipo_operador),
                )
                operadores_por_id[id_operador] = {
                    'id': id_operador, 'id_entidad': id_entidad, 'id_operador_tipo': id_tipo_operador,
                }
                resultado['operadores_creados'].append(
                    f"{(nombre or '').strip() or 'Sin nombre'} ({nombre_tipo}) -- "
                    f"CUIT {cuit_normalizado or 'sin CUIT'} -- id operador INYM {id_operador}"
                )
                return id_operador

            for fila in filas_en_rango:
                clave = (fila['id_certificado'], fila['id_tipo_tarifa'])
                if clave in pares_existentes:
                    resultado['duplicadas'] += 1
                    continue

                if fila['id_tipo_tarifa'] not in tipos_por_id:
                    resultado['tipos_tarifa_no_encontrados'].add((fila['id_tipo_tarifa'], fila['tipo_tarifa_nombre']))
                    resultado['filas_con_error'].append((
                        fila['fila_excel'],
                        f"Tipo de tarifa {fila['id_tipo_tarifa']} ({fila['tipo_tarifa_nombre']}) no existe en "
                        "el sistema -- fila omitida, hay que cargarlo a mano primero.",
                    ))
                    continue

                try:
                    id_operador_emisor = (
                        resolver_operador(
                            fila['id_operador_emisor'], fila['cuit_emisor'], fila['nombre_emisor'],
                            fila['tipo_oper_emisor'],
                        ) if fila['id_operador_emisor'] else None
                    )
                    id_operador_retenido = (
                        resolver_operador(
                            fila['id_operador_retenido'], fila['cuit_retenido'], fila['nombre_retenido'],
                            fila['tipo_oper_retenido'],
                        ) if fila['id_operador_retenido'] else None
                    )
                except Exception as exc:
                    resultado['filas_con_error'].append((fila['fila_excel'], f'No se pudo resolver el operador: {exc}'))
                    continue

                total = (
                    calcular_total(fila['kgs'], fila['tarifa'])
                    if fila['kgs'] is not None and fila['tarifa'] is not None else fila['total']
                )
                cur.execute(
                    """
                    INSERT INTO retencion_inym
                        (id, fecha, periodo, id_tipo_tarifa, id_operador_emisor,
                         id_operador_retenido, kgs, tarifa, total, eliminacion,
                         id_certificado_inym, agregado_desde)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        siguiente_id_retencion, fila['fecha'], fila['periodo'], fila['id_tipo_tarifa'],
                        id_operador_emisor, id_operador_retenido, fila['kgs'], fila['tarifa'], total,
                        fila['eliminacion'], fila['id_certificado'], 'importador_excel_inym',
                    ),
                )
                siguiente_id_retencion += 1
                pares_existentes.add(clave)
                resultado['importadas'] += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return resultado


# ---------------------------------------------------------------------------
# Ranking de entidades retenidas por monto total de retenciones INYM (con
# filtro de rango de fecha y exclusión opcional de Fontana) -- igual que
# retenciones_inym.views.retencion_inym_ranking_entidades /
# _calcular_ranking_retenciones_inym.
# ---------------------------------------------------------------------------

def ranking_entidades(fecha_desde=None, fecha_hasta=None, excluir_fontana=False):
    condiciones = ['ri.id_operador_retenido IS NOT NULL']
    parametros = []
    if fecha_desde:
        condiciones.append('ri.fecha >= %s')
        parametros.append(fecha_desde)
    if fecha_hasta:
        condiciones.append('ri.fecha <= %s')
        parametros.append(fecha_hasta)
    if excluir_fontana:
        condiciones.append('(orx.id_entidad IS NULL OR orx.id_entidad <> %s)')
        parametros.append(ENTIDAD_PROPIA_ID)

    sql = """
        SELECT ri.id_operador_retenido, er.nombre AS entidad_nombre,
               SUM(ri.total) AS total_monto, COUNT(*) AS cantidad
          FROM retencion_inym ri
          LEFT JOIN inym_operador orx ON orx.id = ri.id_operador_retenido
          LEFT JOIN entidad er ON er.id = orx.id_entidad
    """
    sql += ' WHERE ' + ' AND '.join(condiciones)
    sql += ' GROUP BY ri.id_operador_retenido, er.nombre ORDER BY total_monto DESC'

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
    """Igual criterio que retenciones_inym.views._filas_ranking_retenciones_inym."""
    columnas = ['#', 'Entidad retenida', 'Retenciones', 'Monto total', 'Participación %']
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
