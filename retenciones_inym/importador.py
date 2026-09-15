"""
Importador del Excel que exporta el portal de INYM ("Listado Comprobantes
de Retención", hoja única, con 4 filas de encabezado antes de la fila con
los nombres de columna). Se agregó el 2026-09-15 a pedido de Gastón, junto
con la columna nueva `retencion_inym.id_certificado_inym` (ver models.py y
sql/2026-09-15_agregar_id_certificado_inym.sql).

Cómo funciona, en criollo:
  1. `leer_filas_excel` abre el archivo (.xls con xlrd, .xlsx con openpyxl)
     y devuelve una lista de dicts, una por fila de datos, ya con los tipos
     de Python que corresponden (fechas, Decimal, int) en vez de texto
     crudo -- el Excel de INYM trae todo como texto, con fecha
     DD/MM/AAAA y decimales con coma.
  2. `importar_filas` recibe esa lista + un rango de fecha (desde/hasta,
     ambos opcionales) y hace el trabajo pesado:
       - Filtra por fecha.
       - Descarta las filas cuyo (id_certificado, id_tipo_tarifa) ya está
         cargado en `retencion_inym` (ese es el par que identifica a una
         retención de INYM sin ambigüedad -- el N° de certificado por sí
         solo NO alcanza, porque INYM lo numera por separado para cada tipo
         de tarifa).
       - Si el operador emisor o retenido de una fila no existe todavía en
         `inym_operador`, lo crea (junto con la entidad y/o el tipo de
         operador, si tampoco existen), usando el mismo ID de operador que
         trae el Excel -- ese ID sí es el mismo que ya usa el resto del
         sistema (por ejemplo, el operador 181 es "Fontana Secadero", igual
         que la constante OPERADOR_FONTANA_SECADERO_ID del lado
         fontana_escritorio), así que hay que conservarlo tal cual, nunca
         asignarle un ID nuevo.
       - Si el tipo de tarifa de una fila no existe en `inym_retencion_tipo`,
         la fila se omite y se reporta (los tipos de tarifa son una lista
         chica y estable a cargo de INYM, no algo que este importador deba
         inventar sobre la marcha).
       - Inserta las retenciones nuevas dentro de una transacción, con el
         mismo criterio de ID manual (MAX(id)+1) que usa el resto del app
         para esta tabla.
     Devuelve un dict-resumen para mostrarle a Gastón: cuántas se
     importaron, cuántas ya estaban, qué operadores se crearon solos, y
     qué filas no se pudieron cargar (con el motivo).

Las columnas OPER_ORIGEN/IDEMPRESA_ORIGEN/NOMBRE_ORIGEN/TIPO_OPER_ORIGEN
(tabla `retencion_inym_origen`), IDCERT_NO_APLICACION/IMPORTE_NO_RETENIDO
(tabla `retencion_inym_no_aplicacion`) y TASA_SINDICAL se ignoran a
propósito, con el mismo criterio que ya document repository.py del lado
escritorio: esas tablas no las usa ninguna vista de este sistema.
"""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max

from entidades.models import Entidad, Inym_Operador, Inym_Operador_Tipo

from .models import InymRetencionTipo, RetencionInym

COLUMNAS_REQUERIDAS = [
    'IDCERTIFICADO', 'FECHA', 'PERIODO', 'TARIFA', 'IDTIPO_TARIFA', 'TIPO_TARIFA',
    'IDOPERADOR', 'TIPO_OPER', 'IDEMPRESA', 'NOMBRE',
    'OPER_RETENIDO', 'IDEMPRESA_RETENIDO', 'TIPO_OPER_RETENIDO', 'NOMBRE_RETENIDO',
    'KILOS', 'IMPORTE', 'FECHA_ELIMINACION',
]


class ErrorImportacion(Exception):
    """Error al leer el archivo (no se pudo interpretar como el Excel de
    INYM) -- distinto de un error puntual en una fila, que se reporta pero
    no interrumpe el resto del import."""


def _valor_texto(valor):
    if valor is None:
        return ''
    return str(valor).strip()


def _valor_documento(valor):
    """Para CUIT/IDEMPRESA: en el .xls vienen como número (float), y
    str(30585569379.0) da '30585569379.0' -- si es un entero exacto, se
    devuelve sin el '.0' para que calce con cómo se guarda el CUIT en
    `entidad.cuit` (texto, solo dígitos)."""
    if valor is None or valor == '':
        return ''
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _parse_fecha(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    if not texto:
        return None
    return datetime.strptime(texto, '%d/%m/%Y').date()


def _parse_decimal(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = str(valor).strip().replace('.', '').replace(',', '.') if ',' in str(valor) else str(valor).strip()
    if not texto:
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ValueError(f'"{valor}" no es un número válido')


def _parse_int(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, str) and not valor.strip():
        return None
    return int(float(valor))


def _fila_desde_valores(valores, numero_fila_excel):
    id_certificado = _parse_int(valores.get('IDCERTIFICADO'))
    if id_certificado is None:
        return None  # fila vacía / de cierre, no es un dato real

    return {
        'fila_excel': numero_fila_excel,
        'id_certificado': id_certificado,
        'fecha': _parse_fecha(valores.get('FECHA')),
        'periodo': _parse_fecha(valores.get('PERIODO')),
        'tarifa': _parse_decimal(valores.get('TARIFA')),
        'id_tipo_tarifa': _parse_int(valores.get('IDTIPO_TARIFA')),
        'tipo_tarifa_nombre': _valor_texto(valores.get('TIPO_TARIFA')),
        'id_operador_emisor': _parse_int(valores.get('IDOPERADOR')),
        'tipo_oper_emisor': _valor_texto(valores.get('TIPO_OPER')),
        'cuit_emisor': _valor_documento(valores.get('IDEMPRESA')),
        'nombre_emisor': _valor_texto(valores.get('NOMBRE')),
        'id_operador_retenido': _parse_int(valores.get('OPER_RETENIDO')),
        'cuit_retenido': _valor_documento(valores.get('IDEMPRESA_RETENIDO')),
        'tipo_oper_retenido': _valor_texto(valores.get('TIPO_OPER_RETENIDO')),
        'nombre_retenido': _valor_texto(valores.get('NOMBRE_RETENIDO')),
        'kgs': _parse_decimal(valores.get('KILOS')),
        'total': _parse_decimal(valores.get('IMPORTE')),
        'eliminacion': _parse_fecha(valores.get('FECHA_ELIMINACION')),
    }


def _leer_filas_xlsx(archivo):
    import openpyxl
    wb = openpyxl.load_workbook(archivo, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    return _procesar_filas(ws.iter_rows(values_only=True))


def _leer_filas_xls(archivo):
    import xlrd
    contenido = archivo.read() if hasattr(archivo, 'read') else archivo
    wb = xlrd.open_workbook(file_contents=contenido)
    ws = wb.sheet_by_index(0)
    filas = (ws.row_values(i) for i in range(ws.nrows))
    return _procesar_filas(filas)


def _procesar_filas(filas_crudas):
    encabezados = None
    indice_encabezado = {}
    resultado = []
    for numero_fila, fila in enumerate(filas_crudas, start=1):
        if fila is None:
            continue
        celdas = [c for c in fila]
        if encabezados is None:
            textos = [_valor_texto(c).upper() for c in celdas]
            if 'IDCERTIFICADO' in textos:
                encabezados = textos
                indice_encabezado = {nombre: i for i, nombre in enumerate(encabezados)}
                faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in indice_encabezado]
                if faltantes:
                    raise ErrorImportacion(
                        'El Excel no tiene el formato esperado -- faltan las columnas: '
                        + ', '.join(faltantes)
                    )
            continue

        valores = {
            nombre: (celdas[i] if i < len(celdas) else None)
            for nombre, i in indice_encabezado.items()
        }
        try:
            fila_datos = _fila_desde_valores(valores, numero_fila)
        except ValueError as exc:
            resultado.append({'fila_excel': numero_fila, '_error': str(exc)})
            continue
        if fila_datos is not None:
            resultado.append(fila_datos)

    if encabezados is None:
        raise ErrorImportacion(
            'No se encontró la fila de encabezados (con la columna "IDCERTIFICADO") en el Excel.'
        )
    return resultado


def leer_filas_excel(archivo, nombre_archivo):
    """archivo: objeto file-like (p.ej. un UploadedFile de Django, o un
    `open(ruta, 'rb')` del lado escritorio). nombre_archivo: solo se usa
    para decidir el formato por la extensión."""
    extension = (nombre_archivo or '').rsplit('.', 1)[-1].lower()
    if extension == 'xls':
        return _leer_filas_xls(archivo)
    return _leer_filas_xlsx(archivo)


def _resolver_operador(id_operador, cuit, nombre, tipo_oper_nombre, contexto):
    """contexto: dict compartido durante todo el import con las claves
    'operadores_por_id', 'entidades_por_cuit', 'tipos_operador_por_nombre',
    'siguiente_id_entidad', 'siguiente_id_tipo_operador', 'operadores_creados'
    (se muta en el lugar). Devuelve la instancia de Inym_Operador (existente
    o recién creada)."""
    operador = contexto['operadores_por_id'].get(id_operador)
    if operador is not None:
        return operador

    cuit_normalizado = (cuit or '').strip()
    entidad = contexto['entidades_por_cuit'].get(cuit_normalizado) if cuit_normalizado else None
    if entidad is None:
        entidad = Entidad.objects.create(
            id=contexto['siguiente_id_entidad'],
            nombre=(nombre or '').strip() or f'Operador INYM {id_operador}',
            cuit=cuit_normalizado or None,
            activo=True,
        )
        contexto['siguiente_id_entidad'] += 1
        if cuit_normalizado:
            contexto['entidades_por_cuit'][cuit_normalizado] = entidad

    nombre_tipo = (tipo_oper_nombre or '').strip() or 'SIN ESPECIFICAR'
    tipo_operador = contexto['tipos_operador_por_nombre'].get(nombre_tipo.upper())
    if tipo_operador is None:
        tipo_operador = Inym_Operador_Tipo.objects.create(
            id=contexto['siguiente_id_tipo_operador'], nombre=nombre_tipo,
        )
        contexto['siguiente_id_tipo_operador'] += 1
        contexto['tipos_operador_por_nombre'][nombre_tipo.upper()] = tipo_operador

    operador = Inym_Operador.objects.create(id=id_operador, entidad=entidad, tipo_operador=tipo_operador)
    contexto['operadores_por_id'][id_operador] = operador
    contexto['operadores_creados'].append(
        f'{entidad.nombre} ({tipo_operador.nombre}) -- CUIT {cuit_normalizado or "sin CUIT"} -- id operador INYM {id_operador}'
    )
    return operador


def importar_filas(filas, fecha_desde=None, fecha_hasta=None):
    """filas: la lista que devuelve leer_filas_excel (puede traer entradas
    con clave '_error', de filas que no se pudieron interpretar -- se
    reportan igual, sin intentar importarlas)."""
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

    pares_existentes = set(
        RetencionInym.objects.exclude(id_certificado_inym__isnull=True)
        .values_list('id_certificado_inym', 'id_tipo_tarifa_id')
    )
    tipos_por_id = {t.id: t for t in InymRetencionTipo.objects.all()}

    contexto = {
        'operadores_por_id': {
            o.id: o for o in Inym_Operador.objects.select_related('entidad', 'tipo_operador').all()
        },
        'entidades_por_cuit': {
            e.cuit: e for e in Entidad.objects.exclude(cuit__isnull=True).exclude(cuit='')
        },
        'tipos_operador_por_nombre': {
            (t.nombre or '').strip().upper(): t for t in Inym_Operador_Tipo.objects.all()
        },
        'siguiente_id_entidad': (Entidad.objects.aggregate(m=Max('id'))['m'] or 0) + 1,
        'siguiente_id_tipo_operador': (Inym_Operador_Tipo.objects.aggregate(m=Max('id'))['m'] or 0) + 1,
        'operadores_creados': resultado['operadores_creados'],
    }
    siguiente_id_retencion = (RetencionInym.objects.aggregate(m=Max('id'))['m'] or 0) + 1

    with transaction.atomic():
        for fila in filas_en_rango:
            clave = (fila['id_certificado'], fila['id_tipo_tarifa'])
            if clave in pares_existentes:
                resultado['duplicadas'] += 1
                continue

            tipo_tarifa = tipos_por_id.get(fila['id_tipo_tarifa'])
            if tipo_tarifa is None:
                resultado['tipos_tarifa_no_encontrados'].add((fila['id_tipo_tarifa'], fila['tipo_tarifa_nombre']))
                resultado['filas_con_error'].append((
                    fila['fila_excel'],
                    f"Tipo de tarifa {fila['id_tipo_tarifa']} ({fila['tipo_tarifa_nombre']}) no existe en el "
                    "sistema -- fila omitida, hay que cargarlo a mano primero.",
                ))
                continue

            try:
                operador_emisor = (
                    _resolver_operador(
                        fila['id_operador_emisor'], fila['cuit_emisor'], fila['nombre_emisor'],
                        fila['tipo_oper_emisor'], contexto,
                    ) if fila['id_operador_emisor'] else None
                )
                operador_retenido = (
                    _resolver_operador(
                        fila['id_operador_retenido'], fila['cuit_retenido'], fila['nombre_retenido'],
                        fila['tipo_oper_retenido'], contexto,
                    ) if fila['id_operador_retenido'] else None
                )
            except Exception as exc:  # noqa: BLE001 -- se reporta cualquier problema puntual de la fila
                resultado['filas_con_error'].append((fila['fila_excel'], f'No se pudo resolver el operador: {exc}'))
                continue

            RetencionInym.objects.create(
                id=siguiente_id_retencion,
                fecha=fila['fecha'], periodo=fila['periodo'],
                id_tipo_tarifa=tipo_tarifa,
                operador_emisor=operador_emisor, operador_retenido=operador_retenido,
                kgs=fila['kgs'], tarifa=fila['tarifa'], total=fila['total'],
                eliminacion=fila['eliminacion'],
                id_certificado_inym=fila['id_certificado'],
                agregado_desde='importador_excel_inym',
            )
            siguiente_id_retencion += 1
            pares_existentes.add(clave)
            resultado['importadas'] += 1

    return resultado
