"""
Importador de comprobantes desde el archivo "Mis Comprobantes" de AFIP/ARCA
(recibidos o emitidos), en CSV o Excel. Pedido de Gastón, 06/10/2026.

Reemplaza al importador externo que se usaba antes y que:
  - duplicaba comprobantes ya cargados a mano con otro tipo (caso real:
    Electricidad de Misiones, cargadas a mano como "Factura A" y en AFIP como
    "17 - Liquidación de servicios públicos clase A");
  - a veces los cargaba con la dirección invertida (es_emisor).

Funciona en dos pasos (ver views.comprobante_importar_afip):
  1. analizar_archivo(): lee el archivo y, para cada fila, decide qué haría
     SIN guardar nada (vista previa):
       - "crear": comprobante nuevo;
       - "omitir": ya está cargado igual (misma entidad/CUIT + tipo + punto de
         venta + número), o la fila tiene un error;
       - "actualizar": ya hay uno cargado con la misma entidad + número (y el
         mismo punto de venta, o sin punto de venta) pero de OTRO tipo -- es
         el caso de la carga manual con el tipo equivocado: en vez de
         duplicarlo, se le corrige el tipo y se le completan los datos que le
         falten.
     La entidad se busca por CUIT (no por nombre). La dirección sale del
     archivo: "recibidos" -> la emitió la entidad (es_emisor = 1, se liquida
     en PAGO); "emitidos" -> la emitió Fontana (es_emisor = 0, COBRO). Si el
     archivo trae las dos columnas (emisor y receptor), se decide fila por
     fila según de qué lado está el CUIT de Fontana.
  2. aplicar(): con lo que el usuario confirmó en la vista previa (puede
     cambiar la acción de cada fila), crea / actualiza dentro de una
     transacción y devuelve el detalle.

Columnas: se reconocen por el nombre del encabezado (con o sin acentos/
puntos), así que sirve tanto el formato viejo de "Mis Comprobantes" como el
nuevo (el que separa el neto gravado e IVA por alícuota y agrega "Total IVA").
"""
import csv
import io
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q

from entidades.models import Entidad

from .models import Comprobante, ComprobanteTipo, ComprobanteTipoDeCambio

# 'AFIP importador 2': versión corregida (06/10/2026) que busca el tipo por
# código AFIP. Los cargados por la versión anterior quedaron con
# 'AFIP importador' y los repara el comando reparar_importacion_afip.
AGREGADO_DESDE = 'AFIP importador 2'  # comprobante.agregado_desde (máx. 45)
ENTIDAD_PROPIA_ID = getattr(settings, 'ENTIDAD_PROPIA_ID', 100)

ACCION_CREAR = 'crear'
ACCION_ACTUALIZAR = 'actualizar'
ACCION_OMITIR = 'omitir'


class ErrorImportacion(Exception):
    pass


# ---------------------------------------------------------------------------
# Lectura del archivo
# ---------------------------------------------------------------------------

def _norm(texto):
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r'[^a-z0-9%]+', ' ', texto)
    return ' '.join(texto.split())


# clave interna -> encabezados posibles (normalizados), en orden de prioridad
COLUMNAS = {
    'fecha': ['fecha de emision', 'fecha emision', 'fecha'],
    'tipo': ['tipo de comprobante', 'tipo comprobante', 'tipo'],
    'pv': ['punto de venta', 'pto venta', 'punto venta'],
    'numero': ['numero desde', 'nro desde', 'numero'],
    'numero_hasta': ['numero hasta', 'nro hasta'],
    'cae': ['cod autorizacion', 'codigo autorizacion', 'cae'],
    'tipo_doc_emisor': ['tipo doc emisor'],
    'tipo_doc_receptor': ['tipo doc receptor'],
    'nro_doc_emisor': ['nro doc emisor', 'numero doc emisor', 'nro documento emisor', 'cuit emisor'],
    'denom_emisor': ['denominacion emisor', 'razon social emisor'],
    'nro_doc_receptor': ['nro doc receptor', 'numero doc receptor', 'nro documento receptor', 'cuit receptor'],
    'denom_receptor': ['denominacion receptor', 'razon social receptor'],
    'tipo_cambio': ['tipo cambio', 'tipo de cambio'],
    'moneda': ['moneda'],
    'neto_gravado': ['imp neto gravado total', 'imp neto gravado', 'neto gravado total', 'neto gravado'],
    'neto_no_gravado': ['imp neto no gravado', 'neto no gravado'],
    'exento': ['imp op exentas', 'op exentas', 'exento'],
    'otros_tributos': ['otros tributos', 'imp otros tributos'],
    'iva': ['total iva', 'iva'],
    'total': ['imp total', 'importe total', 'total'],
}
OBLIGATORIAS = ['fecha', 'tipo', 'pv', 'numero', 'total']


def _mapear_encabezado(fila):
    normal = [_norm(c) for c in fila]
    mapa = {}
    for clave, opciones in COLUMNAS.items():
        for opcion in opciones:
            if opcion in normal:
                mapa[clave] = normal.index(opcion)
                break
    return mapa


def _filas_crudas(archivo, nombre):
    """Devuelve una lista de listas (todas las filas del archivo)."""
    nombre = (nombre or '').lower()
    contenido = archivo.read()
    if nombre.endswith('.xlsx') or nombre.endswith('.xlsm'):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
        except Exception as exc:
            raise ErrorImportacion(f'No se pudo abrir el Excel: {exc}')
        return [list(f) for f in wb.worksheets[0].iter_rows(values_only=True)]
    if nombre.endswith('.xls'):
        import xlrd
        try:
            libro = xlrd.open_workbook(file_contents=contenido)
        except Exception as exc:
            raise ErrorImportacion(f'No se pudo abrir el Excel: {exc}')
        hoja = libro.sheet_by_index(0)
        filas = []
        for i in range(hoja.nrows):
            fila = []
            for j, celda in enumerate(hoja.row(i)):
                if celda.ctype == xlrd.XL_CELL_DATE:
                    fila.append(xlrd.xldate.xldate_as_datetime(celda.value, libro.datemode))
                else:
                    fila.append(celda.value)
            filas.append(fila)
        return filas
    # CSV / TXT
    texto = None
    for codificacion in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            texto = contenido.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise ErrorImportacion('No se pudo leer el archivo (codificación desconocida).')
    lineas = texto.splitlines()
    muestra = next((l for l in lineas if 'venta' in l.lower()), lineas[0] if lineas else '')
    delim = max([';', ',', '\t', '|'], key=muestra.count)
    return [fila for fila in csv.reader(lineas, delimiter=delim)]


def _decimal(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    texto = str(valor).strip().replace('$', '').replace(' ', '').replace(' ', '')
    if not texto:
        return None
    negativo = texto.startswith('-') or (texto.startswith('(') and texto.endswith(')'))
    texto = texto.strip('-()')
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'):
            texto = texto.replace('.', '').replace(',', '.')   # 1.234,56
        else:
            texto = texto.replace(',', '')                     # 1,234.56
    elif ',' in texto:
        texto = texto.replace(',', '.')                         # 1234,56
    elif texto.count('.') > 1:
        texto = texto.replace('.', '')                          # 1.234.567
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        raise ValueError(f'número inválido "{valor}"')
    return -numero if negativo else numero


def _entero(valor):
    numero = _decimal(valor)
    return int(numero) if numero is not None else None


def _fecha(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()[:10]
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(f'fecha inválida "{valor}"')


def _solo_digitos(valor):
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r'\D', '', str(valor))


def _moneda(valor):
    texto = _norm(valor).upper().replace(' ', '')
    if texto in ('', '$', 'PES', 'ARS', 'PESOS'):
        return 'PES'
    # Otras monedas: se guarda el código tal como lo trae AFIP (ej. "USD").
    # El total queda en esa moneda y el tipo de cambio va a
    # comprobante_tipo_de_cambio (liquidaciones lo multiplica).
    return texto[:4]


# Códigos viejos de AFIP (CSV hasta mediados de 2025) y los nuevos (ISO): en la
# base conviven "DOL" y "USD", "060" y "EUR". Se consideran la misma moneda al
# comparar con un comprobante ya cargado (no se pisa ni se informa diferencia).
MONEDAS_EQUIVALENTES = {'DOL': 'USD', '060': 'EUR'}


def misma_moneda(a, b):
    a = MONEDAS_EQUIVALENTES.get(str(a or '').strip().upper(), str(a or '').strip().upper())
    b = MONEDAS_EQUIVALENTES.get(str(b or '').strip().upper(), str(b or '').strip().upper())
    return a == b


def leer_filas(archivo, nombre):
    """Lee el archivo y devuelve (filas, columnas_encontradas). Cada fila es
    un dict con los valores ya convertidos, o con 'errores'."""
    crudas = _filas_crudas(archivo, nombre)
    inicio, mapa = None, None
    for i, fila in enumerate(crudas[:30]):
        candidato = _mapear_encabezado(fila)
        if 'pv' in candidato and 'numero' in candidato:
            inicio, mapa = i, candidato
            break
    if mapa is None:
        raise ErrorImportacion(
            'No encontré el encabezado de "Mis Comprobantes" (columnas Punto de Venta / Número Desde). '
            '¿Es el archivo exportado de AFIP/ARCA?'
        )
    faltan = [c for c in OBLIGATORIAS if c not in mapa]
    if faltan:
        raise ErrorImportacion('Al archivo le faltan columnas: ' + ', '.join(faltan))

    filas = []
    for n, cruda in enumerate(crudas[inicio + 1:], start=inicio + 2):
        if not any(str(c).strip() for c in cruda if c is not None):
            continue

        def celda(clave):
            i = mapa.get(clave)
            return cruda[i] if i is not None and i < len(cruda) else None

        fila = {'linea': n, 'errores': []}
        for clave, conv in (('fecha', _fecha), ('pv', _entero), ('numero', _entero), ('numero_hasta', _entero),
                            ('tipo_cambio', _decimal), ('neto_gravado', _decimal), ('neto_no_gravado', _decimal),
                            ('exento', _decimal), ('otros_tributos', _decimal), ('iva', _decimal), ('total', _decimal)):
            try:
                fila[clave] = conv(celda(clave))
            except ValueError as exc:
                fila[clave] = None
                fila['errores'].append(f'{clave}: {exc}')
        tipo_txt = str(celda('tipo') or '').strip()
        m = re.match(r'^\s*(\d+)', tipo_txt)
        fila['tipo_codigo'] = int(m.group(1)) if m else None
        fila['tipo_texto'] = tipo_txt
        cae = _solo_digitos(celda('cae'))
        fila['cae'] = cae or None
        fila['tipodoc_emisor'] = _solo_digitos(celda('tipo_doc_emisor'))
        fila['tipodoc_receptor'] = _solo_digitos(celda('tipo_doc_receptor'))
        fila['cuit_emisor'] = _solo_digitos(celda('nro_doc_emisor'))
        fila['nombre_emisor'] = str(celda('denom_emisor') or '').strip()
        fila['cuit_receptor'] = _solo_digitos(celda('nro_doc_receptor'))
        fila['nombre_receptor'] = str(celda('denom_receptor') or '').strip()
        fila['moneda'] = _moneda(celda('moneda'))
        if fila['fecha'] is None and 'fecha: ' not in ' '.join(fila['errores']):
            fila['errores'].append('sin fecha')
        if fila['numero'] is None:
            fila['errores'].append('sin número')
        if fila['total'] is None:
            fila['errores'].append('sin importe total')
        filas.append(fila)
    return filas, mapa


# ---------------------------------------------------------------------------
# Análisis (vista previa)
# ---------------------------------------------------------------------------

def _vacio(campo, valor):
    if valor is None or valor == '':
        return True
    if campo != 'es_emisor' and isinstance(valor, (int, float, Decimal)) and valor == 0:
        return True
    return False


def tipos_por_codigo_afip():
    """{código AFIP: ComprobanteTipo}. En la tabla de tipos el ID NO siempre
    es el código AFIP (ej. ID 7 = Factura B, código 6; ID 6 = Recibo C, código
    15), así que se busca por la columna id_afip. Si dos tipos tienen el mismo
    código se prefiere el que además tiene ID = código; si no, el de ID menor.
    Un tipo sin id_afip sólo se usa por su ID si ningún otro reclama ese código."""
    por_codigo, sin_codigo = {}, {}
    for t in ComprobanteTipo.objects.all().order_by('id'):
        d = re.sub(r'\D', '', str(t.id_afip or ''))
        if d:
            cod = int(d)
            actual = por_codigo.get(cod)
            if actual is None or (t.id == cod and actual.id != cod):
                por_codigo[cod] = t
        else:
            sin_codigo[t.id] = t
    for tid, t in sin_codigo.items():
        por_codigo.setdefault(tid, t)
    return por_codigo


def _cuit_valido(d):
    return bool(d) and len(d) == 11 and bool(d.strip('0'))


def _str(valor):
    if valor is None:
        return None
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return str(valor)


_PALABRAS_SOCIETARIAS = {'s', 'a', 'sa', 'srl', 'sas', 'saic', 'saci', 'sacif', 'r', 'l', 'sociedad', 'anonima',
                         'de', 'responsabilidad', 'limitada', 'y', 'cia', 'coop', 'ltda'}


def _nombre_clave(nombre):
    """Nombre normalizado para comparar entidades sin CUIT cargado:
    'ELECTRICIDAD DE MISIONES S. A.' == 'Electricidad de Misiones SA'."""
    return ' '.join(p for p in _norm(nombre).split() if p not in _PALABRAS_SOCIETARIAS)


def _cuit_propio_del_archivo(filas, nombre_archivo):
    """CUIT de Fontana deducido del archivo: AFIP lo pone en el nombre
    (comprobantes_consulta_csv_recibidos_<id>_<CUIT>_<fecha>...) y además es
    el que aparece en casi todas las filas (como receptor en recibidos, como
    emisor en emitidos)."""
    from collections import Counter
    conteo = Counter()
    for f in filas:
        for clave in ('cuit_emisor', 'cuit_receptor'):
            if f.get(clave):
                conteo[f[clave]] += 1
    en_nombre = [c for c in re.findall(r'(?<!\d)(\d{11})(?!\d)', nombre_archivo or '') if c in conteo]
    if en_nombre:
        return en_nombre[0]
    if conteo and filas:
        cuit, veces = conteo.most_common(1)[0]
        if veces >= 0.6 * len(filas):
            return cuit
    return ''


def analizar(filas, mapa, sentido='auto', fecha_desde=None, fecha_hasta=None, nombre_archivo=''):
    """Arma la vista previa. 'sentido': 'auto', 'recibidos' o 'emitidos'.
    Devuelve un dict serializable (para guardarlo en la sesión)."""
    propia = Entidad.objects.filter(pk=ENTIDAD_PROPIA_ID).first()
    cuit_propio = _solo_digitos(propia.cuit) if propia and propia.cuit else ''
    if not cuit_propio:
        cuit_propio = _cuit_propio_del_archivo(filas, nombre_archivo)

    tiene_emisor = 'nro_doc_emisor' in mapa
    tiene_receptor = 'nro_doc_receptor' in mapa
    nombre_norm = _norm(nombre_archivo)
    if sentido == 'auto' and 'recibidos' in nombre_norm:
        sentido = 'recibidos'
    elif sentido == 'auto' and 'emitidos' in nombre_norm:
        sentido = 'emitidos'
    if sentido == 'auto':
        if tiene_emisor and not tiene_receptor:
            sentido_archivo = 'recibidos'
        elif tiene_receptor and not tiene_emisor:
            sentido_archivo = 'emitidos'
        elif tiene_emisor and tiene_receptor:
            sentido_archivo = 'por_fila'
        else:
            raise ErrorImportacion('No se puede saber si el archivo es de recibidos o emitidos: elegilo a mano.')
    else:
        sentido_archivo = sentido

    tipos = {t.id: t for t in ComprobanteTipo.objects.all()}
    por_codigo = tipos_por_codigo_afip()

    # Entidades por CUIT (normalizado). Las que tienen el CUIT vacío, en 0 o
    # con un número que no es un CUIT (ej. el DNI cargado en el campo CUIT)
    # se tratan como "sin CUIT": se buscan por nombre y por DNI.
    por_cuit = {}
    sin_cuit_por_nombre = {}
    dni_en_campo_cuit = {}
    for e in Entidad.objects.all():
        d = _solo_digitos(e.cuit)
        if _cuit_valido(d):
            por_cuit.setdefault(d, []).append(e)
            continue
        clave = _nombre_clave(e.nombre)
        if clave:
            sin_cuit_por_nombre.setdefault(clave, []).append(e)
        if d and d.strip("0") and 4 <= len(d) <= 8:
            dni_en_campo_cuit.setdefault(int(d), []).append(e)

    # Clientes identificados sólo con DNI (Factura B): por documento_nro, o
    # por CUIT/CUIL que contenga ese DNI.
    por_dni = {}
    for e in Entidad.objects.exclude(documento_nro__isnull=True):
        if e.documento_nro:
            por_dni.setdefault(int(e.documento_nro), []).append(e)
    for dni, ents in dni_en_campo_cuit.items():
        for e in ents:
            if e not in por_dni.setdefault(dni, []):
                por_dni[dni].append(e)
    for d, ents in por_cuit.items():
        if len(d) == 11 and d[:2] in ('20', '23', '24', '27'):
            for e in ents:
                if e not in por_dni.setdefault(int(d[2:10]), []):
                    por_dni[int(d[2:10])].append(e)
    # Entidad genérica para tiques / consumidor final (pedido de Gastón,
    # 06/10/2026: las ventas sin cliente identificado van todas ahí).
    consumidor_final = next(
        (e for e in Entidad.objects.filter(nombre__icontains='consumidor').order_by('id')
         if 'consumidor final' in _norm(e.nombre)), None)

    # Comprobantes ya cargados con los mismos números (una sola consulta por
    # bloque, en vez de una por fila: los archivos de emitidos traen miles).
    existentes_por_numero = {}
    numeros = sorted({f['numero'] for f in filas if f.get('numero')})
    for i in range(0, len(numeros), 1000):
        for c in Comprobante.objects.filter(numero__in=numeros[i:i + 1000]).order_by('id'):
            existentes_por_numero.setdefault(c.numero, []).append(c)

    resultado = []
    vistos = set()
    for f in filas:
        if fecha_desde and f.get('fecha') and f['fecha'] < fecha_desde:
            continue
        if fecha_hasta and f.get('fecha') and f['fecha'] > fecha_hasta:
            continue
        r = {
            'linea': f['linea'], 'fecha': _str(f.get('fecha')), 'tipo_codigo': f.get('tipo_codigo'),
            'tipo_texto': f.get('tipo_texto'), 'pv': f.get('pv'), 'numero': f.get('numero'),
            'numero_hasta': f.get('numero_hasta'), 'cae': f.get('cae'), 'moneda': f.get('moneda'),
            'tipo_cambio': _str(f.get('tipo_cambio')),
            'neto_gravado': _str(f.get('neto_gravado')), 'neto_no_gravado': _str(f.get('neto_no_gravado')),
            'exento': _str(f.get('exento')), 'otros_tributos': _str(f.get('otros_tributos')),
            'iva': _str(f.get('iva')), 'total': _str(abs(f['total']) if f.get('total') is not None else None),
            'errores': list(f.get('errores', [])), 'avisos': [],
            'accion': ACCION_OMITIR, 'existente_id': None, 'motivo': '',
            'entidad_id': None, 'entidad_texto': '', 'crear_entidad': False,
        }
        # Dirección y contraparte
        if sentido_archivo == 'recibidos':
            lado = 'emisor'
        elif sentido_archivo == 'emitidos':
            lado = 'receptor'
        else:
            lado = 'receptor' if (cuit_propio and f.get('cuit_emisor') == cuit_propio) else 'emisor'
        es_emisor = 0 if lado == 'receptor' else 1
        cuit, nombre, tipodoc = f.get('cuit_' + lado), f.get('nombre_' + lado), f.get('tipodoc_' + lado)
        # Clase de documento de la contraparte:
        #   cf   -> tique / consumidor final (sin documento, documento 0 o tipo 99)
        #   dni  -> persona con DNI u otro documento que no es CUIT/CUIL
        #   cuit -> CUIT / CUIL (80, 86, 87) o sin tipo pero con número
        if not cuit or not cuit.strip('0') or tipodoc == '99':
            clase_doc, cuit = 'cf', ''
            nombre = nombre or 'CONSUMIDOR FINAL'
        elif tipodoc and tipodoc not in ('80', '86', '87'):
            clase_doc = 'dni'
        else:
            clase_doc = 'cuit'
        if cuit_propio and cuit == cuit_propio:
            r['errores'].append('la contraparte es Fontana: ¿elegiste bien recibidos/emitidos?')
        r.update({'es_emisor': es_emisor, 'cuit': cuit or '', 'nombre': nombre or '', 'clase_doc': clase_doc,
                  'clave_entidad': 'cf' if clase_doc == 'cf' else f'{clase_doc}:{int(cuit) if clase_doc == "dni" else cuit}'})

        if f.get('total') is not None and f['total'] < 0:
            r['avisos'].append('importe negativo en el archivo: se toma en positivo')

        tipo = por_codigo.get(r['tipo_codigo'])
        r['tipo_id'] = tipo.id if tipo else None
        if tipo is None:
            r['errores'].append(f'no hay ningún Tipo de comprobante con código AFIP {r["tipo_codigo"]} '
                                f'("{r["tipo_texto"]}"): cargarlo (o completarle el código AFIP) y volver a importar')
        r['tipo_nombre'] = str(tipo) if tipo else r['tipo_texto']

        # Entidad: consumidor final / DNI / CUIT
        if clase_doc == 'cf':
            candidatas = [consumidor_final] if consumidor_final else []
        elif clase_doc == 'dni':
            candidatas = por_dni.get(int(cuit), [])
        else:
            candidatas = por_cuit.get(cuit, []) if cuit else []
        if clase_doc == 'cf' and not candidatas:
            r['crear_entidad'] = True
            r['entidad_texto'] = 'NUEVA: CONSUMIDOR FINAL'
        elif clase_doc == 'dni' and not candidatas and len(sin_cuit_por_nombre.get(_nombre_clave(nombre), [])) == 1:
            ent = sin_cuit_por_nombre[_nombre_clave(nombre)][0]
            candidatas = [ent]
            r['entidad_id'] = ent.id
            r['entidad_texto'] = f'{ent.id} - {ent.nombre}'
            r['completar_dni'] = True
            r['avisos'].append(f'entidad encontrada por nombre (no tenía el DNI cargado): se le carga el DNI {int(cuit)}')
        elif clase_doc == 'dni' and not candidatas:
            r['crear_entidad'] = True
            r['entidad_texto'] = f'NUEVA: {nombre} (DNI {int(cuit)})'
        elif candidatas:
            candidatas = sorted(candidatas, key=lambda e: (not e.activo, e.id))
            ent = candidatas[0]
            r['entidad_id'] = ent.id
            r['entidad_texto'] = f'{ent.id} - {ent.nombre}'
            if len(candidatas) > 1:
                r['avisos'].append('hay varias entidades con ese CUIT: ' +
                                   ', '.join(f'{e.id}' for e in candidatas) + f' (se usa la {ent.id})')
        elif cuit and len(sin_cuit_por_nombre.get(_nombre_clave(nombre), [])) == 1:
            ent = sin_cuit_por_nombre[_nombre_clave(nombre)][0]
            candidatas = [ent]
            r['entidad_id'] = ent.id
            r['entidad_texto'] = f'{ent.id} - {ent.nombre}'
            r['completar_cuit'] = True
            r['avisos'].append(f'entidad encontrada por nombre (no tenía CUIT cargado): se le carga el CUIT {cuit}')
        elif cuit:
            r['crear_entidad'] = True
            r['entidad_texto'] = f'NUEVA: {nombre} (CUIT {cuit})'
        else:
            r['errores'].append('la fila no trae CUIT de la contraparte')

        if r['errores']:
            r['motivo'] = '; '.join(r['errores'])
            resultado.append(r)
            continue

        # Repetida dentro del mismo archivo
        clave = (r['clave_entidad'], r['tipo_codigo'], r['pv'], r['numero'])
        if clave in vistos:
            r['motivo'] = 'fila repetida en el archivo'
            resultado.append(r)
            continue
        vistos.add(clave)

        # ¿Ya está cargado? Misma entidad (cualquiera con ese CUIT) o sin
        # entidad con el mismo nombre; mismo número; mismo punto de venta o
        # sin punto de venta cargado.
        ids_ent = {e.id for e in candidatas}
        nombre_l = (nombre or '').strip().lower()
        existentes = [
            c for c in existentes_por_numero.get(r['numero'], [])
            if (c.entidad_emisor_id in ids_ent
                or (c.entidad_emisor_id is None and nombre_l and (c.entidad_nombre or '').strip().lower() == nombre_l))
            and (c.punto_de_venta in (None, 0) or c.punto_de_venta == r['pv'])
        ]
        if not existentes:
            # Última red contra duplicados: mismo número, punto de venta, fecha
            # y total aunque esté cargado con otra entidad (ej. una entidad
            # vieja con otro nombre o sin documento).
            existentes = [
                c for c in existentes_por_numero.get(r['numero'], [])
                if (c.punto_de_venta in (None, 0) or c.punto_de_venta == r['pv'])
                and _str(c.fecha) == r['fecha'] and c.total is not None and r['total'] is not None
                and abs(Decimal(str(c.total)) - Decimal(r['total'])) < Decimal('0.01')
            ]
            for c in existentes:
                r['avisos'].append(f'ya hay un comprobante igual (id {c.id}) cargado con otra entidad '
                                   f'({c.entidad_emisor_id} - {c.entidad_nombre or ""}): no se duplica')
        mismo_tipo = [c for c in existentes if c.tipo_comprobante_id == r['tipo_id']]
        otro_tipo = [c for c in existentes if c.tipo_comprobante_id != r['tipo_id']]
        for c in existentes:
            if c.es_emisor != es_emisor:
                r['avisos'].append(
                    f'el comprobante {c.id} está cargado como emitido por '
                    f'{"Fontana" if c.es_emisor == 0 else "la entidad"} y AFIP dice que lo emitió '
                    f'{"Fontana" if es_emisor == 0 else "la entidad"}: al actualizar se corrige')
        if mismo_tipo:
            c = mismo_tipo[0]
            r['existente_id'] = c.id
            r['motivo'] = f'ya está cargado (comprobante {c.id})'
            faltantes = _campos_a_completar(c, r)
            if faltantes or c.es_emisor != es_emisor:
                r['accion'] = ACCION_ACTUALIZAR
                partes = []
                if faltantes:
                    partes.append('completarle ' + ', '.join(faltantes))
                if c.es_emisor != es_emisor:
                    partes.append('corregir quién lo emitió')
                r['motivo'] += ': se sugiere actualizar para ' + ' y '.join(partes)
        elif len(otro_tipo) == 1:
            c = otro_tipo[0]
            r['accion'] = ACCION_ACTUALIZAR
            r['existente_id'] = c.id
            tipo_c = tipos.get(c.tipo_comprobante_id)
            r['motivo'] = (f'ya estaba cargado como "{tipo_c or "sin tipo"}" (comprobante {c.id}, '
                           f'probablemente a mano): se le corrige el tipo y se completan datos, sin duplicarlo')
        elif len(otro_tipo) > 1:
            r['motivo'] = ('hay varios comprobantes con ese número y otro tipo (' +
                           ', '.join(str(c.id) for c in otro_tipo) + '): revisar a mano')
        else:
            r['accion'] = ACCION_CREAR
            r['motivo'] = 'nuevo'
        resultado.append(r)

    resumen = {
        'total': len(resultado),
        'crear': sum(1 for r in resultado if r['accion'] == ACCION_CREAR),
        'actualizar': sum(1 for r in resultado if r['accion'] == ACCION_ACTUALIZAR),
        'omitir': sum(1 for r in resultado if r['accion'] == ACCION_OMITIR),
        'errores': sum(1 for r in resultado if r['errores']),
        'entidades_nuevas': len({r['clave_entidad'] for r in resultado if r['crear_entidad'] and not r['errores']}),
    }
    return {'filas': resultado, 'resumen': resumen,
            'sentido': sentido_archivo, 'fecha_desde': _str(fecha_desde), 'fecha_hasta': _str(fecha_hasta)}


# Campos que se completan en un comprobante existente al "actualizar"
CAMPOS_DATOS = [
    ('fecha', 'fecha'), ('punto_de_venta', 'pv'), ('numero_hasta', 'numero_hasta'),
    ('codigo_autorizacion', 'cae'), ('moneda', 'moneda'), ('neto_gravado', 'neto_gravado'),
    ('neto_no_gravado', 'neto_no_gravado'), ('exento', 'exento'), ('otros_tributos', 'otros_tributos'),
    ('iva', 'iva'), ('total', 'total'), ('entidad_nombre', 'nombre'),
]


def _valor_modelo(campo, valor):
    if valor is None or valor == '':
        return None
    if campo == 'fecha':
        return date.fromisoformat(valor) if isinstance(valor, str) else valor
    if campo in ('punto_de_venta', 'numero_hasta'):
        return int(valor)
    if campo in ('neto_gravado', 'codigo_autorizacion'):
        return float(valor)
    if campo in ('neto_no_gravado', 'exento', 'otros_tributos', 'iva', 'total'):
        return Decimal(str(valor))
    return valor


def _campos_a_completar(c, r):
    faltan = []
    for campo, clave in CAMPOS_DATOS:
        nuevo = _valor_modelo(campo, r.get(clave))
        if _vacio(campo, getattr(c, campo)) and not _vacio(campo, nuevo):
            faltan.append(campo)
    return faltan


def _comprobante_string(tipo, pv, numero):
    prefijo = (getattr(tipo, 'abreviatura', None) or getattr(tipo, 'nombre', None) or '').strip()
    return f'{prefijo} {int(pv or 0):05d}-{int(numero or 0):08d}'.strip()[:145]


# ---------------------------------------------------------------------------
# Aplicar
# ---------------------------------------------------------------------------

@transaction.atomic
def aplicar(analisis, acciones, crear_entidades=True):
    """'acciones': {linea: 'crear'|'actualizar'|'omitir'} elegido en la vista
    previa (si falta una línea, se usa la acción sugerida)."""
    from entidades.views import siguiente_id_entidad

    from liquidaciones.models import LiquidacionComprobante

    por_codigo = tipos_por_codigo_afip()
    siguiente_id = (Comprobante.objects.aggregate(Max('id'))['id__max'] or 0) + 1
    entidades_creadas = {}
    por_cuit = {}
    for e in Entidad.objects.exclude(cuit__isnull=True).exclude(cuit='').order_by('id'):
        if _cuit_valido(_solo_digitos(e.cuit)):
            por_cuit.setdefault(_solo_digitos(e.cuit), e.id)
    detalle = {'creados': [], 'actualizados': [], 'omitidos': [], 'diferencias': [], 'entidades_creadas': []}

    # Comprobantes ya existentes (re-chequeo de duplicados exactos al guardar,
    # en bloque) y los que se van a crear (se insertan con bulk_create).
    ya_cargados = {}
    numeros = sorted({r['numero'] for r in analisis['filas'] if r.get('numero')})
    for i in range(0, len(numeros), 1000):
        for cid, ent, tip, pv, num in Comprobante.objects.filter(numero__in=numeros[i:i + 1000]).values_list(
                'id', 'entidad_emisor_id', 'tipo_comprobante_id', 'punto_de_venta', 'numero'):
            ya_cargados[(ent, tip, pv, num)] = cid
    nuevos, tipos_de_cambio = [], []

    for r in analisis['filas']:
        accion = acciones.get(str(r['linea']), r['accion'])
        if r['errores'] or accion == ACCION_OMITIR:
            detalle['omitidos'].append({'linea': r['linea'], 'numero': r['numero'], 'nombre': r['nombre'],
                                        'motivo': r['motivo'] if accion == r['accion'] else 'omitido a mano'})
            continue
        tipo = por_codigo.get(r['tipo_codigo'])
        if tipo is None:
            detalle['omitidos'].append({'linea': r['linea'], 'numero': r['numero'], 'nombre': r['nombre'],
                                        'motivo': f'no hay Tipo de comprobante con código AFIP {r["tipo_codigo"]}'})
            continue

        # Entidad
        entidad_id = r['entidad_id']
        clave_ent = r.get('clave_entidad') or f"cuit:{r['cuit']}"
        if entidad_id is None and clave_ent in entidades_creadas:
            entidad_id = entidades_creadas[clave_ent]
        if entidad_id is None and crear_entidades and clave_ent == 'cf':
            nueva = Entidad(id=siguiente_id_entidad(), nombre='CONSUMIDOR FINAL', activo=True)
            nueva.save(force_insert=True)
            entidad_id = entidades_creadas['cf'] = nueva.id
            detalle['entidades_creadas'].append(f'{nueva.id} - CONSUMIDOR FINAL')
        elif entidad_id is None and crear_entidades and clave_ent.startswith('dni:'):
            dni = int(clave_ent[4:])
            nueva = Entidad(id=siguiente_id_entidad(), nombre=(r['nombre'] or '')[:105], documento_nro=dni, activo=True)
            nueva.save(force_insert=True)
            entidad_id = entidades_creadas[clave_ent] = nueva.id
            detalle['entidades_creadas'].append(f'{nueva.id} - {nueva.nombre} (DNI {dni})')
        if entidad_id and r.get('completar_cuit') and r['cuit']:
            ent = Entidad.objects.filter(pk=entidad_id).first()
            if ent and not _cuit_valido(_solo_digitos(ent.cuit)):
                Entidad.objects.filter(pk=entidad_id).update(cuit=r['cuit'])
                detalle['entidades_creadas'].append(f'{entidad_id} - se le cargó el CUIT {r["cuit"]} (ya existía)')
        if entidad_id and r.get('completar_dni') and clave_ent.startswith('dni:'):
            if Entidad.objects.filter(pk=entidad_id, documento_nro__isnull=True).update(documento_nro=int(clave_ent[4:])):
                detalle['entidades_creadas'].append(f'{entidad_id} - se le cargó el DNI {int(clave_ent[4:])} (ya existía)')
        if entidad_id is None and r['cuit'] and clave_ent.startswith('cuit:'):
            if r['cuit'] in entidades_creadas:
                entidad_id = entidades_creadas[r['cuit']]
            elif crear_entidades:
                if r['cuit'] in por_cuit:
                    entidad_id = por_cuit[r['cuit']]
                else:
                    nueva = Entidad(id=siguiente_id_entidad(), nombre=(r['nombre'] or '')[:105],
                                    cuit=r['cuit'], activo=True)
                    nueva.save(force_insert=True)
                    entidad_id = nueva.id
                    detalle['entidades_creadas'].append(f'{nueva.id} - {nueva.nombre} (CUIT {nueva.cuit})')
                entidades_creadas[r['cuit']] = entidad_id

        if accion == ACCION_CREAR:
            # Re-chequeo por si cambió algo entre la vista previa y el guardado.
            llave = (entidad_id, tipo.id, r['pv'], r['numero'])
            ya = ya_cargados.get(llave) if entidad_id else None
            if ya:
                detalle['omitidos'].append({'linea': r['linea'], 'numero': r['numero'], 'nombre': r['nombre'],
                                            'motivo': f'ya está cargado (comprobante {ya})'})
                continue
            c = Comprobante(
                id=siguiente_id,
                entidad_emisor_id=entidad_id,
                tipo_comprobante_id=tipo.id,
                numero=r['numero'],
                es_emisor=r['es_emisor'],
                agregado_desde=AGREGADO_DESDE,
                comprobante_string=_comprobante_string(tipo, r['pv'], r['numero']),
            )
            for campo, clave in CAMPOS_DATOS:
                setattr(c, campo, _valor_modelo(campo, r.get(clave)))
            nuevos.append(c)
            if entidad_id:
                ya_cargados[llave] = c.id
            siguiente_id += 1
            if c.moneda and c.moneda != 'PES' and r.get('tipo_cambio'):
                tipos_de_cambio.append(ComprobanteTipoDeCambio(comprobante=c, tipo_de_cambio=Decimal(r['tipo_cambio'])))
            detalle['creados'].append({'id': c.id, 'linea': r['linea'], 'texto': f'{c.comprobante_string} - {r["nombre"]}',
                                       'total': r['total']})

        elif accion == ACCION_ACTUALIZAR and r['existente_id']:
            c = Comprobante.objects.filter(pk=r['existente_id']).first()
            if c is None:
                detalle['omitidos'].append({'linea': r['linea'], 'numero': r['numero'], 'nombre': r['nombre'],
                                            'motivo': f'el comprobante {r["existente_id"]} ya no existe'})
                continue
            cambios = {}
            if c.tipo_comprobante_id != tipo.id:
                cambios['tipo_comprobante_id'] = tipo.id
            nuevo_string = _comprobante_string(tipo, r['pv'] or c.punto_de_venta, r['numero'])
            if c.comprobante_string != nuevo_string:
                cambios['comprobante_string'] = nuevo_string
            if c.entidad_emisor_id is None and entidad_id:
                cambios['entidad_emisor_id'] = entidad_id
            for campo, clave in CAMPOS_DATOS:
                actual = getattr(c, campo)
                nuevo = _valor_modelo(campo, r.get(clave))
                if _vacio(campo, actual) and not _vacio(campo, nuevo):
                    cambios[campo] = nuevo
                elif not _vacio(campo, actual) and not _vacio(campo, nuevo) and actual != nuevo:
                    if campo == 'moneda' and misma_moneda(actual, nuevo):
                        continue
                    try:
                        igual = abs(Decimal(str(actual)) - Decimal(str(nuevo))) < Decimal('0.01')
                    except (InvalidOperation, ValueError, TypeError):
                        igual = str(actual).strip().lower() == str(nuevo).strip().lower()
                    if not igual:
                        detalle['diferencias'].append({'id': c.id, 'campo': campo, 'guardado': str(actual),
                                                       'afip': str(nuevo)})
            if c.es_emisor != r['es_emisor']:
                # La dirección del archivo de AFIP es confiable (sale del CUIT):
                # se corrige, salvo que el comprobante ya esté en una
                # liquidación del tipo que corresponde a la dirección vieja.
                tipo_viejo = 'cobro' if c.es_emisor == 0 else 'pago'
                liq_vieja = list(LiquidacionComprobante.objects.filter(comprobante_id=c.id, liquidacion__tipo=tipo_viejo)
                                 .values_list('liquidacion_id', flat=True))
                if liq_vieja:
                    detalle['diferencias'].append({
                        'id': c.id, 'campo': 'quién lo emitió (es_emisor)', 'guardado': str(c.es_emisor),
                        'afip': f'{r["es_emisor"]} -- NO se corrigió: está en la liquidación de {tipo_viejo} '
                                + ', '.join(str(x) for x in liq_vieja)})
                else:
                    cambios['es_emisor'] = r['es_emisor']
            if cambios:
                Comprobante.objects.filter(pk=c.pk).update(**cambios)
            detalle['actualizados'].append({'id': c.id, 'linea': r['linea'],
                                            'campos': [k.replace('_id', '') for k in cambios] or ['sin cambios']})
        else:
            detalle['omitidos'].append({'linea': r['linea'], 'numero': r['numero'], 'nombre': r['nombre'],
                                        'motivo': 'acción no válida para esta fila'})
    # Inserción en bloque (bulk_create sigue completando fecha_agregado,
    # auto_now_add): un archivo de emitidos de un año trae miles de filas.
    Comprobante.objects.bulk_create(nuevos, batch_size=500)
    ComprobanteTipoDeCambio.objects.bulk_create(tipos_de_cambio, batch_size=500)
    return detalle
