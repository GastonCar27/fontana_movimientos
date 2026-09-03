"""
Generación de PDF y Excel de una solicitud de compra ("solicitud de
entrega"), reproduciendo el formato del impreso que hoy se le da a los
empleados para retirar mercadería de un proveedor: datos del proveedor,
datos de la propia empresa (solicitante) con el empleado autorizado a
retirar y su DNI, la tabla de renglones pedidos, y la firma de quien
autorizó el pedido al pie.
"""
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from entidades.models import Entidad
from services.formato import cuit_con_guiones, fecha_larga

# Entidad que representa a la propia empresa (mismo criterio que
# liquidaciones.views.ENTIDAD_PROPIA_ID / MovimientoCaja.emisor).
ENTIDAD_PROPIA_ID = 100

# La empresa propia no tiene un campo de teléfono en el modelo Entidad, así
# que se deja como constante acá (es un dato institucional fijo). Si cambia
# el número, se edita solo acá.
TELEFONO_EMPRESA = '(3755) 15654287/15413042'

# Cantidad mínima de filas que muestra la tabla de renglones (se completa
# con filas en blanco si la solicitud tiene menos, para que el impreso
# quede con el mismo aire que la planilla en papel que se usaba antes).
FILAS_MINIMAS_RENGLONES = 12


def _entidad_propia():
    return Entidad.objects.filter(id=ENTIDAD_PROPIA_ID).first()


def _nombre_completo(empleado):
    if not empleado:
        return ''
    return f'{empleado.nombre} {empleado.apellido}'.strip().upper()


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

def _tabla_datos(titulo, filas):
    """Arma la grilla "DATOS DEL ..." con una barra de título y filas de
    (label, valor, label2, valor2)."""
    datos = [[titulo, '', '', '']] + [list(fila) for fila in filas]
    tabla = Table(datos, colWidths=[2.6 * cm, 8.2 * cm, 1.6 * cm, 6.1 * cm])
    tabla.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.6, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return tabla


def _tabla_renglones_pdf(renglones):
    datos = [['Cantidad', 'U. de Medida', 'Prioridad', 'Sector', 'Descripción']]
    for renglon in renglones:
        datos.append([
            _formatear_cantidad(renglon.cantidad),
            renglon.unidad_medida or '',
            renglon.get_prioridad_display() if renglon.prioridad else '',
            renglon.sector.nombre if renglon.sector_id else '',
            renglon.descripcion,
        ])
    while len(datos) - 1 < FILAS_MINIMAS_RENGLONES:
        datos.append(['', '', '', '', ''])

    tabla = Table(datos, colWidths=[2 * cm, 2.3 * cm, 1.9 * cm, 2.3 * cm, 9.6 * cm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (3, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.6, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return tabla


def generar_pdf_solicitud(solicitud):
    response = HttpResponse(content_type='application/pdf')
    # 'inline' (no 'attachment'): así el navegador abre el PDF directo en
    # una pestaña con su visor incorporado, desde donde se puede imprimir
    # (Ctrl+P / ícono de impresora del visor) en vez de forzar la descarga.
    response['Content-Disposition'] = f'inline; filename="solicitud_compra_{solicitud.id}.pdf"'

    margen = 1.3 * cm
    doc = SimpleDocTemplate(
        response, pagesize=A4,
        topMargin=margen, bottomMargin=margen, leftMargin=margen, rightMargin=margen,
    )

    estilo_hoja = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'TituloSolicitud', fontName='Helvetica-Bold', fontSize=14, parent=estilo_hoja['Heading1'],
        alignment=TA_CENTER,
    )
    estilo_numero_label = ParagraphStyle(
        'NumeroLabel', fontName='Helvetica-Bold', fontSize=9, parent=estilo_hoja['Normal'], alignment=TA_CENTER,
    )
    estilo_numero_valor = ParagraphStyle(
        'NumeroValor', fontName='Helvetica-Bold', fontSize=16, parent=estilo_hoja['Normal'], alignment=TA_CENTER,
    )
    estilo_fecha = ParagraphStyle(
        'Fecha', fontName='Helvetica', fontSize=9, parent=estilo_hoja['Normal'], alignment=TA_RIGHT,
    )
    estilo_pie = ParagraphStyle(
        'PieAutorizado', fontName='Helvetica-Bold', fontSize=10, parent=estilo_hoja['Normal'], alignment=TA_RIGHT,
        spaceBefore=28,
    )
    estilo_obs = ParagraphStyle('Observaciones', fontName='Helvetica', fontSize=8, parent=estilo_hoja['Normal'])

    entidad = solicitud.entidad
    propia = _entidad_propia()

    caja_numero = Table(
        [
            [Paragraph('N°', estilo_numero_label)],
            [Paragraph(str(solicitud.numero or solicitud.id), estilo_numero_valor)],
        ],
        colWidths=[3.5 * cm],
    )
    caja_numero.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    encabezado = Table(
        [[Paragraph('SOLICITUD DE ENTREGA', estilo_titulo), caja_numero]],
        colWidths=[14.5 * cm, 3.5 * cm],
    )
    encabezado.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))

    story = [
        encabezado,
        Paragraph(fecha_larga(solicitud.fecha), estilo_fecha),
        Spacer(1, 0.4 * cm),
        _tabla_datos('DATOS DEL PROVEEDOR', [
            ('Proveedor:', entidad.nombre or '', 'Cuit:', cuit_con_guiones(entidad.cuit)),
            (
                'Dirección:', entidad.direccion or '', '',
                f'{entidad.localidad or ""} ({entidad.codpos or ""})  {entidad.provincia or ""}'.strip(),
            ),
        ]),
        Spacer(1, 0.3 * cm),
        _tabla_datos('DATOS DEL SOLICITANTE', [
            (
                'Solicitante:', propia.nombre if propia else '',
                'Cuit:', cuit_con_guiones(propia.cuit) if propia else '',
            ),
            ('Dirección:', propia.direccion if propia else '', 'Tel:', TELEFONO_EMPRESA),
            (
                'Autorizado:', _nombre_completo(solicitud.responsable_retiro),
                'DNI:', solicitud.responsable_retiro.documento or '',
            ),
        ]),
        Spacer(1, 0.4 * cm),
        _tabla_renglones_pdf(list(solicitud.renglones.select_related('sector').all())),
        Spacer(1, 0.2 * cm),
    ]

    if solicitud.observaciones:
        story.append(Paragraph(f'Observaciones: {solicitud.observaciones}', estilo_obs))

    story.append(Paragraph(f'Autorizado por: {_nombre_completo(solicitud.solicitante)}', estilo_pie))

    doc.build(story)
    return response


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def generar_excel_solicitud(solicitud):
    import openpyxl
    from services.gestorexcel import definir_estilo_general

    entidad = solicitud.entidad
    propia = _entidad_propia()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Solicitud'

    ws.append(['SOLICITUD DE ENTREGA'])
    ws.append([])
    ws.append(['N°', solicitud.numero or solicitud.id, 'Fecha', fecha_larga(solicitud.fecha)])
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
        'DNI', solicitud.responsable_retiro.documento or '',
    ])
    ws.append([])

    ws.append(['Cantidad', 'U. de Medida', 'Prioridad', 'Sector', 'Descripción'])
    for renglon in solicitud.renglones.select_related('sector').all():
        ws.append([
            _numero_o_none(renglon.cantidad),
            renglon.unidad_medida or '',
            renglon.get_prioridad_display() if renglon.prioridad else '',
            renglon.sector.nombre if renglon.sector_id else '',
            renglon.descripcion,
        ])

    ws.append([])
    ws.append(['Autorizado por', _nombre_completo(solicitud.solicitante)])
    if solicitud.observaciones:
        ws.append(['Observaciones', solicitud.observaciones])

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
