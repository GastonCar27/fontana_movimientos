"""
Generación de PDF y Excel de una solicitud de compra ("solicitud de
entrega"), reproduciendo el formato del impreso que hoy se le da a los
empleados para retirar mercadería de un proveedor: datos del proveedor,
datos de la propia empresa (solicitante) con el empleado autorizado a
retirar y su DNI, la tabla de renglones pedidos, y la firma de quien
autorizó el pedido al pie.

Cada solicitud se imprime DOS VECES en la misma hoja: una copia completa
para archivar en la empresa y, debajo, una copia para el proveedor,
separadas por una línea de corte para poder separarlas con tijera. Por eso
cada copia usa una versión compacta del diseño (fuente más chica, menos
filas en blanco, sin la caja grande del número): a media hoja no entra el
mismo diseño "grande" que antes ocupaba la hoja completa.

Las dos copias NO muestran lo mismo (a propósito, no es sólo un recorte de
espacio):
- Copia EMPRESA: lleva Sector y Prioridad (uso interno), la hora de emisión
  además de la fecha, quién solicitó el pedido ("Solicitó") y quién generó
  la orden en el sistema ("Creó la orden"). En cambio NO repite los datos
  de la propia empresa (nombre/dirección/CUIT/tel de Fontana) -- ya los
  tiene, es la copia que se queda acá, así se ahorra tinta -- con la única
  excepción del renglón "Autorizado a retirar" (a quién esperar).
- Copia PROVEEDOR: al revés, SÍ lleva los datos de Fontana (el proveedor no
  los tiene de memoria) pero no Sector/Prioridad (no le sirven) ni quién
  solicitó/creó la orden como dato de texto -- en cambio, al pie, tiene DOS
  espacios de firma: uno para quien retira la mercadería y otro para quien
  generó la orden, como constancia de entrega para el proveedor.
"""
import re

from django.http import HttpResponse
from django.utils import timezone as django_timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9, no debería pasar en este proyecto
    ZoneInfo = None

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from entidades.models import Entidad
from services.formato import cuit_con_guiones, fecha_larga, numero_con_puntos

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

# settings.TIME_ZONE del proyecto está en 'UTC' (no en la hora real de
# Misiones), así que para mostrar la hora de emisión tal cual la vería
# alguien ahí se convierte explícitamente a esta zona horaria, sin depender
# de esa configuración global (cambiarla afectaría otras fechas del
# sistema, como el default de 'fecha', y no es parte de este pedido).
ZONA_HORARIA_IMPRESION = ZoneInfo('America/Argentina/Buenos_Aires') if ZoneInfo else None

# Usuario (User.username, en minúsculas) que creó la orden -> nombre EXACTO
# de su Entidad correspondiente en la tabla `entidades` (para buscarla y
# sacarle el DNI), más el apellido y el nombre YA separados (para imprimir
# "Apellido, Nombre" sin tener que adivinar cómo partir el campo libre
# 'nombre' de Entidad, que no sigue un orden fijo). Usernames y split
# Apellido/Nombre confirmados por Gastón. Si en el futuro se suma un
# usuario nuevo que todavía no está acá, no rompe: _creador_info imprime
# el nombre de usuario tal cual (con mayúscula inicial) en vez del DNI.
USUARIO_A_ENTIDAD = {
    'franco': {'entidad_nombre': 'Bongers Walter Franco', 'apellido': 'Bongers', 'nombre': 'Walter Franco'},
    'diego': {'entidad_nombre': 'Genesini Diego', 'apellido': 'Genesini', 'nombre': 'Diego'},
    'gaston': {'entidad_nombre': 'Luis Gastón Carballo', 'apellido': 'Carballo', 'nombre': 'Luis Gastón'},
}


def _entidad_propia():
    return Entidad.objects.filter(id=ENTIDAD_PROPIA_ID).first()


def _nombre_titulo(nombre):
    """Formatea el nombre de una entidad con la primera letra de cada
    palabra en mayúscula y el resto en minúscula (ej. 'EMPLEADO RETIRADOR
    UNO' -> 'Empleado Retirador Uno'), en vez de imprimirlo tal cual está
    cargado en la base (a veces todo en mayúsculas)."""
    return (nombre or '').strip().title()


def _nombre_completo(entidad):
    if not entidad:
        return ''
    return _nombre_titulo(entidad.nombre)


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


def _numero_impreso(solicitud):
    """El número que se imprime en el PDF/Excel es siempre sólo los
    dígitos, sin el prefijo histórico 'OC-' que todavía tienen las
    solicitudes cargadas antes de este cambio (ej. numero='OC-125' imprime
    '125'); las solicitudes nuevas ya se guardan sin prefijo (ver
    siguiente_numero_solicitud en models.py), así que ahí esto no cambia
    nada."""
    numero = solicitud.numero or solicitud.id
    digitos = re.sub(r'\D', '', str(numero))
    return digitos or numero


def _hora_emision(solicitud):
    """Hora (HH:MM) en que se guardó por primera vez la solicitud
    (solicitud.creado, DateTimeField con auto_now_add=True -- no hizo
    falta agregar una columna nueva, ese dato ya se guardaba solo desde
    siempre, sólo faltaba imprimirlo)."""
    if not solicitud.creado:
        return ''
    if not ZONA_HORARIA_IMPRESION:
        return django_timezone.localtime(solicitud.creado).strftime('%H:%M')
    return django_timezone.localtime(solicitud.creado, ZONA_HORARIA_IMPRESION).strftime('%H:%M')


def _creador_info(solicitud):
    """Devuelve (nombre_para_mostrar, dni_con_puntos) del usuario que creó
    la solicitud (solicitud.creado_por), buscando su Entidad correspondiente
    según USUARIO_A_ENTIDAD de acá arriba. Si 'creado_por' es None (dato
    viejo, de antes de que se empezara a guardar), devuelve ('', '') y el
    campo/firma correspondiente simplemente no se imprime (ver _bloque_copia
    / _agregar_bloque_excel). Si 'creado_por' existe pero su username no
    está en el mapeo (usuario nuevo todavía no contemplado), no hay forma de
    resolver su Entidad para el DNI, pero igual se muestra el nombre de
    usuario (con mayúscula inicial, por convención) en vez de dejar el campo
    vacío del todo."""
    if not solicitud.creado_por_id:
        return '', ''
    username = (solicitud.creado_por.username or '').strip()
    datos = USUARIO_A_ENTIDAD.get(username.lower())
    if not datos:
        return (username.capitalize() if username else ''), ''
    entidad_creador = Entidad.objects.filter(nombre=datos['entidad_nombre']).first()
    dni = numero_con_puntos(entidad_creador.documento_nro) if entidad_creador else ''
    return f"{datos['apellido']}, {datos['nombre']}", dni


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


def _tabla_renglones_pdf(renglones, es_copia_empresa):
    """La copia para la empresa lleva Prioridad y Sector; la del proveedor
    no (no le sirven), así que directamente no se incluyen esas dos
    columnas -- no se muestran vacías, se libera ese ancho para el resto."""
    if es_copia_empresa:
        encabezados = ['Cantidad', 'U. de Medida', 'Prioridad', 'Sector', 'Descripción']
        anchos = [1.8 * cm, 2.3 * cm, 1.8 * cm, 2.3 * cm, 10.4 * cm]
    else:
        encabezados = ['Cantidad', 'U. de Medida', 'Descripción']
        anchos = [2.3 * cm, 3.0 * cm, 13.3 * cm]

    datos = [encabezados]
    for renglon in renglones:
        fila = [_formatear_cantidad(renglon.cantidad), renglon.unidad_medida or '']
        if es_copia_empresa:
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


def _bloque_copia(solicitud, entidad, propia, etiqueta, es_copia_empresa, estilos):
    """Devuelve la lista de flowables de UNA copia (empresa o proveedor),
    para apilar dos de éstas en la misma hoja con una línea de corte entre
    medio -- ver generar_pdf_solicitud. Qué lleva cada una está explicado
    en el docstring del módulo."""
    subtitulo = f'{etiqueta} · {fecha_larga(solicitud.fecha)}'
    if es_copia_empresa:
        hora = _hora_emision(solicitud)
        if hora:
            subtitulo += f' · {hora}hs'

    filas_solicitante = []
    if not es_copia_empresa:
        filas_solicitante.extend([
            (
                'Solicitante:', _nombre_titulo(propia.nombre) if propia else '',
                'Cuit:', cuit_con_guiones(propia.cuit) if propia else '',
            ),
            ('Dirección:', propia.direccion if propia else '', 'Tel:', TELEFONO_EMPRESA),
        ])
    filas_solicitante.append((
        'Autorizado a retirar:', _nombre_completo(solicitud.responsable_retiro),
        'DNI:', numero_con_puntos(solicitud.responsable_retiro.documento_nro),
    ))
    # "Solicitó" (quién autorizó/pidió la compra, antes "Autorizado por"):
    # sólo en la copia de la empresa, justo debajo de "Autorizado a retirar".
    if es_copia_empresa:
        filas_solicitante.append(('Solicitó:', _nombre_completo(solicitud.solicitante), '', ''))
    apellido_nombre_creador, dni_creador = _creador_info(solicitud)
    if es_copia_empresa and apellido_nombre_creador:
        filas_solicitante.append(('Creó la orden:', apellido_nombre_creador, 'DNI:', dni_creador))

    bloque = [
        Paragraph(f'SOLICITUD DE ENTREGA — N° {_numero_impreso(solicitud)}', estilos['encabezado']),
        Paragraph(subtitulo, estilos['subtitulo']),
        _tabla_datos_pdf('DATOS DEL PROVEEDOR', [
            ('Proveedor:', _nombre_titulo(entidad.nombre), 'Cuit:', cuit_con_guiones(entidad.cuit)),
            (
                'Dirección:', entidad.direccion or '', '',
                f'{entidad.localidad or ""} ({entidad.codpos or ""})  {entidad.provincia or ""}'.strip(),
            ),
        ]),
        Spacer(1, 0.15 * cm),
        _tabla_datos_pdf('DATOS DEL SOLICITANTE', filas_solicitante),
        Spacer(1, 0.15 * cm),
        _tabla_renglones_pdf(list(solicitud.renglones.select_related('sector').all()), es_copia_empresa),
    ]

    if solicitud.observaciones:
        bloque.append(Spacer(1, 0.1 * cm))
        bloque.append(Paragraph(f'Observaciones: {solicitud.observaciones}', estilos['obs']))

    # Sólo en la copia del proveedor: espacio(s) de firma -- el autorizado a
    # retirar (constancia de que se llevó la mercadería) y, si se pudo
    # resolver, quien generó la orden en el sistema. Con las dos, van una al
    # lado de la otra (izquierda/derecha) en vez de una debajo de la otra,
    # para no alargar la hoja.
    if not es_copia_empresa:
        bloque.append(Spacer(1, 0.4 * cm))
        firma_retira = (
            Paragraph('_' * 30, estilos['firma_linea']),
            Paragraph(f'Firma de quien retira ({_nombre_completo(solicitud.responsable_retiro)})', estilos['firma_label']),
        )
        if apellido_nombre_creador:
            firma_creador = (
                Paragraph('_' * 30, estilos['firma_linea']),
                Paragraph(f'Firma de quien creó la orden ({apellido_nombre_creador})', estilos['firma_label']),
            )
            tabla_firmas = Table(
                [[firma_retira[0], firma_creador[0]], [firma_retira[1], firma_creador[1]]],
                colWidths=[9.3 * cm, 9.3 * cm],
            )
            tabla_firmas.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            bloque.append(tabla_firmas)
        else:
            bloque.append(firma_retira[0])
            bloque.append(firma_retira[1])

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

def _agregar_bloque_excel(ws, solicitud, entidad, propia, etiqueta, es_copia_empresa):
    """Igual que _bloque_copia pero agregando filas directo a la hoja --
    ver generar_excel_solicitud, que llama esto dos veces (una por copia)
    con una fila separadora de corte entre medio."""
    ws.append([f'SOLICITUD DE ENTREGA — N° {_numero_impreso(solicitud)}'])
    fila_encabezado = [etiqueta, '', 'Fecha', fecha_larga(solicitud.fecha)]
    if es_copia_empresa:
        hora = _hora_emision(solicitud)
        if hora:
            fila_encabezado.extend(['Hora', f'{hora}hs'])
    ws.append(fila_encabezado)
    ws.append([])
    ws.append(['Proveedor', _nombre_titulo(entidad.nombre), 'Cuit', cuit_con_guiones(entidad.cuit)])
    ws.append([
        'Dirección', entidad.direccion or '', 'Localidad',
        f'{entidad.localidad or ""} ({entidad.codpos or ""}) {entidad.provincia or ""}'.strip(),
    ])
    ws.append([])

    if not es_copia_empresa:
        ws.append([
            'Solicitante', _nombre_titulo(propia.nombre) if propia else '',
            'Cuit', cuit_con_guiones(propia.cuit) if propia else '',
        ])
        ws.append(['Dirección', propia.direccion if propia else '', 'Tel', TELEFONO_EMPRESA])
    ws.append([
        'Autorizado a retirar', _nombre_completo(solicitud.responsable_retiro),
        'DNI', numero_con_puntos(solicitud.responsable_retiro.documento_nro),
    ])
    # "Solicitó": sólo en la copia de la empresa, justo debajo de
    # "Autorizado a retirar" (mismo criterio que en el PDF).
    if es_copia_empresa:
        ws.append(['Solicitó', _nombre_completo(solicitud.solicitante)])
    apellido_nombre_creador, dni_creador = _creador_info(solicitud)
    if es_copia_empresa and apellido_nombre_creador:
        ws.append(['Creó la orden', apellido_nombre_creador, 'DNI', dni_creador])
    ws.append([])

    if es_copia_empresa:
        ws.append(['Cantidad', 'U. de Medida', 'Prioridad', 'Sector', 'Descripción'])
    else:
        ws.append(['Cantidad', 'U. de Medida', 'Descripción'])
    for renglon in solicitud.renglones.select_related('sector').all():
        fila = [_numero_o_none(renglon.cantidad), renglon.unidad_medida or '']
        if es_copia_empresa:
            fila.append(renglon.get_prioridad_display() if renglon.prioridad else '')
            fila.append(renglon.sector.nombre if renglon.sector_id else '')
        fila.append(renglon.descripcion)
        ws.append(fila)

    ws.append([])
    if solicitud.observaciones:
        ws.append(['Observaciones', solicitud.observaciones])

    # Sólo en el bloque del proveedor: mismos espacios de firma que en el
    # PDF (ver _bloque_copia). Con las dos, van en la misma fila -- una en
    # las primeras dos columnas y la otra en las siguientes dos -- para que
    # queden una al lado de la otra, no una debajo de la otra.
    if not es_copia_empresa:
        ws.append([])
        if apellido_nombre_creador:
            ws.append([
                f'Firma de quien retira ({_nombre_completo(solicitud.responsable_retiro)}):', '______________________________',
                f'Firma de quien creó la orden ({apellido_nombre_creador}):', '______________________________',
            ])
        else:
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
