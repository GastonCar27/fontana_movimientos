"""
Lectura del Excel que exporta el portal de INYM ("Listado Comprobantes de
Retención", hoja única, con 4 filas de encabezado antes de la fila con los
nombres de columna). Mismo parseo que el lado Django
(`fontana_movimientos/retenciones_inym/importador.py`) -- se mantiene acá
una copia en vez de compartir el módulo porque este proyecto y el Django no
comparten código Python entre sí (son dos programas separados que hablan
con la misma base).

Este módulo SOLO lee y normaliza el Excel a una lista de dicts de Python
(fechas, Decimal, int en vez de texto crudo). El trabajo de comparar contra
lo ya cargado, crear operadores que falten e insertar las retenciones
nuevas lo hace `repository.importar_lote`, para tener todo el acceso a la
base de escritorio en un solo lugar (repository.py), igual que el resto del
proyecto.
"""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

COLUMNAS_REQUERIDAS = [
    'IDCERTIFICADO', 'FECHA', 'PERIODO', 'TARIFA', 'IDTIPO_TARIFA', 'TIPO_TARIFA',
    'IDOPERADOR', 'TIPO_OPER', 'IDEMPRESA', 'NOMBRE',
    'OPER_RETENIDO', 'IDEMPRESA_RETENIDO', 'TIPO_OPER_RETENIDO', 'NOMBRE_RETENIDO',
    'KILOS', 'IMPORTE', 'FECHA_ELIMINACION',
]


class ErrorImportacion(Exception):
    """El archivo no se pudo interpretar como el Excel de INYM (no es un
    error de una fila puntual, que se reporta pero no interrumpe el resto)."""


def _valor_texto(valor):
    if valor is None:
        return ''
    return str(valor).strip()


def _valor_documento(valor):
    """Para CUIT/IDEMPRESA: vienen como número (float) en el .xls, y
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


def _leer_filas_xlsx(ruta):
    import openpyxl
    wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    return _procesar_filas(ws.iter_rows(values_only=True))


def _leer_filas_xls(ruta):
    import xlrd
    wb = xlrd.open_workbook(ruta)
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
        celdas = list(fila)
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


def leer_filas_excel(ruta):
    extension = ruta.rsplit('.', 1)[-1].lower()
    if extension == 'xls':
        return _leer_filas_xls(ruta)
    return _leer_filas_xlsx(ruta)
