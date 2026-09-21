"""
Generación de PDF y Excel de una solicitud de compra ("solicitud de
entrega"), reproduciendo el formato del impreso que hoy se le da a los
empleados para retirar mercadería de un proveedor: datos del proveedor,
datos de la propia empresa (solicitante) con el empleado autorizado a
retirar y su DNI, la tabla de renglones pedidos, y la firma de quien
autorizó el pedido al pie.

Cada solicitud se imprime DOS VECES en la misma hoja: una copia completa
(con Sector y Prioridad, para que quede archivada en la empresa) y, debajo,
una copia reducida para el proveedor (sin esos dos datos, que no le sirven),
separadas por una línea de corte para poder separarlas con tijera. Por eso
cada copia usa una versión compacta del diseño (fuente más chica, menos
filas en blanco, sin la caja grande del número): a media hoja no entra el
mismo diseño "grande" que antes ocupaba la hoja completa. La copia del
proveedor además lleva, al pie, un espacio para que firme el autorizado a
retirar al momento de llevarse la mercadería (constancia de entrega para
el proveedor).
"""
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from entidades.models import Entidad
from services.formato import cuit_con_guiones, fecha_larga

# Entidad que representa a la propia empresa (mismo criterio que
# liquidaciones.views.ENTIDAD_PROPIA_ID / MovimientoCaja.emisor).
ENTIDAD_PROPIA_ID = 100

# La empresa propia no tiene un campo de teléfono en el modelo Entidad, así
# que se deja como constante acá (es un dato institucional fijo). Si cambia
# el número, se edita solo acá.
TELEFONO_EMPRESA = '(3755) 15654287/15413042'

# Cantidad mínima de filas que muestra cada copia de la tabla de renglones
# (se completa con filas en blanco si la solicitud tiene menos). Más chico
# que antes porque ahora cada copia ocupa sólo media hoja.
FILAS_MINIMAS_RENGLONES = 5


def _entidad_propia():
    return Entidad.objects.filter(id=ENTIDAD_PROPIA_ID).first()


def _nombre_completo(entidad):
    if not entidad:
        return ''
    return (entidad.nombre or '').strip().upper()


def _formatear_cantidad(valor):
    if valor is None:
        return ''
    if valor == valor.to_integral_value():
        return str(int(valor))
    return str(valor)


def _numero_o_none(valor):
    if valor is None:
        return None
    return float(valor)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def _estilos_pdf():
    hoja = getSampleStyleSheet()
    return {
        'encabezado': ParagraphStyle(
            'EncabezadoCopia', fontName='Helvetica-Bold', fontSize=11, parent=hoja['Normal'],
            alignment=TA_CENTER, spaceAfter=1,
        ),
        'subtitulo': ParagraphStyle(
            'SubtituloCopia', fontName='Helvetica-Bold', fontSize=8, parent=hoja['Normal'],
            alignment=TA_CENTER, textColor=colors.HexColor('#555555'), spaceAfter=4,
        ),
        'pie': ParagraphStyle(
            'PieAutorizado', fontName='Helvetica-Bold', fontSize=8, parent=hoja['Normal'],
            alignment=TA_RIGHT, spaceBefore=6,
        ),
        'obs': ParagraphStyle('Observaciones', fontName='Helvetica', fontSize=7, parent=hoja['Normal']),
        'corte': ParagraphStyle(
            'TextoCorte', fontName='Helvetica', fontSize=7, parent=hoja['Normal'],
            alignment=TA_CENTER, textColor=colors.HexColor('#777777'),
        ),
        'firma_linea': ParagraphStyle(
            'FirmaLinea', fontName='Helvetica', fontSize=9, parent=hoja['Normal'], alignment=TA_CENTER,
        ),
        'firma_label': ParagraphStyle(
            'FirmaLabel', fontName='Helvetica', fontSize=6.5, parent=hoja['Normal'], alignment=TA_CENTER,
            textColor=colors.HexColor('#555555'),
        ),
    }


def _tabla_datos_pdf(titulo, filas):
    """Arma la grilla "DATOS DEL ..." con una barra de título y filas de
    (label, valor, label2, valor2)."""
    datos = [[titulo, '', '', '']] + [list(fila) for fila in filas]
    tabla = Table(datos, colWidths=[2.6 * cm, 8.0 * cm, 1.9 * cm, 6.1 * cm])
    tabla.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    return tabla


def _tabla_renglones_pdf(renglones, incluir_sector_prioridad):
    """La copia para la empresa lleva Prioridad y Sector; la del proveedor
    no (no le sirven), así que directamente no se incluyen esas dos
    columnas -- no se muestran vacías, se libera ese ancho para el resto."""
    if incluir_sector_prioridad:
        encabezados = ['Cantidad', 'U. de Medida', 'Prioridad', 'Sector', 'Descripción']
        anchos = [1.8 * cm, 2.3 * cm, 1.8 * cm, 2.3 * cm, 10.4 * cm]
    else:
        encabezados = ['Cantidad', 'U. de Medida', 'Descripción']
        anchos = [2.3 * cm, 3.0 * cm, 13.3 * cm]

    datos = [encabezados]
    for renglon in renglones:
        fila = [_formatear_cantidad(renglon.cantidad), renglon.unidad_medida or '']
        if incluir_sector_prioridad:
            fila.append(renglon.get_prioridad_display() if renglon.prioridad else '')
            fila.append(renglon.sector.nombre if renglon.sector_id else '')
        fila.append(renglon.descripcion)
        datos.append(fila)
    while len(datos) - 1 < FILAS_MINIMAS_RENGLONES:
        datos.append([''] * len(encabezados))

    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('ALIGN', (0, 0), (len(encabezados) - 2, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    return tabla


def _bloque_copia(solicitud, entidad, propia, etiqueta, incluir_sector_prioridad, estilos):
    """Devuelve la lista de flowables de UNA copia (empresa o proveedor),
    para apilar dos de éstas en la misma hoja con una línea de corte entre
    medio -- ver generar_pdf_solicitud."""
    numero = solicitud.numero or solicitud.id

    bloque = [
        Paragraph(f'SOLICITUD DE ENTREGA — N° {numero}', estilos['encabezado']),
        Paragraph(f'{etiqueta} · {fecha_larga(solicitud.fecha)}', estilos['subtitulo']),
        _tabla_datos_pdf('DATOS DEL PROVEEDOR', [
            ('Proveedor:', entidad.nombre or '', 'Cuit:', cuit_con_guiones(entidad.cuit)),
            (
                'Dirección:', entidad.direccion or '', '',
                f'{entidad.localidad or ""} ({entidad.codpos or ""})  {entidad.provincia or ""}'.strip(),
            ),
        ]),
        Spacer(1, 0.15 * cm),
        _tabla_datos_pdf('DATOS DEL SOLICITANTE', [
            (
                'Solicitante:', propia.nombre if propia else '',
                'Cuit:', cuit_con_guiones(propia.cuit) if propia else '',
            ),
            ('Dirección:', propia.direccion if propia else '', 'Tel:', TELEFONO_EMPRESA),
            (
                'Autorizado:', _nombre_completo(solicitud.responsable_retiro),
                'DNI:', solicitud.responsable_retiro.documento_nro or '',
            ),
        ]),
        Spacer(1, 0.15 * cm),
        _tabla_renglones_pdf(list(solicitud.renglones.select_related('sector').all()), incluir_sector_prioridad),
    ]

    if solicitud.observaciones:
        bloque.append(Spacer(1, 0.1 * cm))
        bloque.append(Paragraph(f'Observaciones: {solicitud.observaciones}', estilos['obs']))

    bloque.append(Paragraph(f'Autorizado por: {_nombre_completo(solicitud.solicitante)}', estilos['pie']))

    # Sólo en la copia del proveedor: un espacio para que el autorizado a
    # retirar (el nombre que ya figura arriba, en "DATOS DEL SOLICITANTE" ->
    # Autorizado) firme al momento de llevarse la mercadería -- así el
    # proveedor se queda con esa copia como constancia de la entrega.
    if not incluir_sector_prioridad:
        bloque.append(Spacer(1, 0.5 * cm))
        bloque.append(Paragraph('_' * 42, estilos['firma_linea']))
        bloque.append(Paragraph(
            f'Firma de quien retira ({_nombre_completo(solicitud.responsable_retiro)})',
            estilos['firma_label'],
        ))

    return bloque


def _linea_corte(estilos):
    return [
        Spacer(1, 0.3 * cm),
        HRFlowable(width='100%', thickness=0.75, color=colors.HexColor('#999999'), dash=(4, 3)),
        Paragraph('- - - - - - - - - - -  CORTAR POR AQUÍ  - - - - - - - - - - -', estilos['corte']),
        HRFlowable(width='100%', thickness=0.75, color=colors.HexColor('#999999'), dash=(4, 3)),
        Spacer(1, 0.3 * cm),
    ]


def generar_pdf_solicitud(solicitud):
    response = HttpResponse(content_type='application/pdf')
    # 'inline' (no 'attachment'): así el navegador abre el PDF directo en
    # una pestaña con su visor incorporado, desde donde se puede imprimir
    # (Ctrl+P / ícono de impresora del visor) en vez de forzar la descarga.
    response['Content-Disposition'] = f'inline; filename="solicitud_compra_{solicitud.id}.pdf"'

    margen = 1 * cm
    doc = SimpleDocTemplate(
        response, pagesize=A4,
        topMargin=margen, bottomMargin=margen, leftMargin=margen, rightMargin=margen,
    )

    estilos = _estilos_pdf()
    entidad = solicitud.entidad
    propia = _entidad_propia()

    # KeepTogether alrededor de cada copia: si entra, la mantiene entera en
    # el mismo bloque de hoja (para que el corte quede prolijo); si una
    # solicitud tiene tantos renglones que ni una copia entra sola en una
    # hoja, se termina partiendo igual -- no hay forma de evitarlo sin
    # recortar contenido real.
    story = [KeepTogether(_bloque_copia(solicitud, entidad, propia, 'COPIA PARA LA EMPRESA', True, estilos))]
    story.extend(_linea_corte(estilos))
    story.append(KeepTogether(_bloque_copia(solicitud, entidad, propia, 'COPIA PARA EL PROVEEDOR', False, estilos)))

    doc.build(story)
    return response


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def _agregar_bloque_excel(ws, solicitud, entidad, propia, etiqueta, incluir_sector_prioridad):
    """Igual que _bloque_copia pero agregando filas directo a la hoja --
    ver generar_excel_solicitud, que llama esto dos veces (una por copia)
    con una fila separadora de corte entre medio."""
    ws.append([f'SOLICITUD DE ENTREGA — N° {solicitud.numero or solicitud.id}'])
    ws.append([etiqueta, '', 'Fecha', fecha_larga(solicitud.fecha)])
    ws.append([])
    ws.append(['Proveedor', entidad.nombre or '', 'Cuit', cuit_con_guiones(entidad.cuit)])
    ws.append([
        'Dirección', entidad.direccion or '', 'Localidad',
        f'{entidad.localidad or ""} ({entidad.codpos or ""}) {entidad.provincia or ""}'.strip(),
    ])
    ws.append([])
    ws.append([
        'Solicitante', propia.nombre if propia else '',
        'Cuit', cuit_con_guiones(propia.cuit) if propia else '',
    ])
    ws.append(['Dirección', propia.direccion if propia else '', 'Tel', TELEFONO_EMPRESA])
    ws.append([
        'Autorizado a retirar', _nombre_completo(solicitud.responsable_retiro),
        'DNI', solicitud.responsable_retiro.documento_nro or '',
    ])
    ws.append([])

    if incluir_sector_prioridad:
        ws.append(['Cantidad', 'U. de Medida', 'Prioridad', 'Sector', 'Descripción'])
    else:
        ws.append(['Cantidad', 'U. de Medida', 'Descripción'])
    for renglon in solicitud.renglones.select_related('sector').all():
        fila = [_numero_o_none(renglon.cantidad), renglon.unidad_medida or '']
        if incluir_sector_prioridad:
            fila.append(renglon.get_prioridad_display() if renglon.prioridad else '')
            fila.append(renglon.sector.nombre if renglon.sector_id else '')
        fila.append(renglon.descripcion)
        ws.append(fila)

    ws.append([])
    ws.append(['Autorizado por', _nombre_completo(solicitud.solicitante)])
    if solicitud.observaciones:
        ws.append(['Observaciones', solicitud.observaciones])

    # Sólo en el bloque del proveedor: mismo espacio de firma que en el PDF
    # (ver _bloque_copia) para que el autorizado a retirar firme al llevarse
    # la mercadería.
    if not incluir_sector_prioridad:
        ws.append([])
        ws.append([f'Firma de quien retira ({_nombre_completo(solicitud.responsable_retiro)}):', '______________________________'])


def generar_excel_solicitud(solicitud):
    import openpyxl
    from services.gestorexcel import definir_estilo_general

    entidad = solicitud.entidad
    propia = _entidad_propia()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Solicitud'

    _agregar_bloque_excel(ws, solicitud, entidad, propia, 'COPIA PARA LA EMPRESA', True)
    ws.append([])
    ws.append(['- - - - - - - - - - - - -  CORTAR POR AQUÍ  - - - - - - - - - - - - -'])
    ws.append([])
    _agregar_bloque_excel(ws, solicitud, entidad, propia, 'COPIA PARA EL PROVEEDOR', False)

    definir_estilo_general(ws)
    for columna in ws.columns:
        letra = columna[0].column_letter
        largo_max = max((len(str(c.value)) for c in columna if c.value is not None), default=10)
        ws.column_dimensions[letra].width = min(max(largo_max + 2, 10), 50)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="solicitud_compra_{solicitud.id}.xlsx"'
    wb.save(response)
    return response
