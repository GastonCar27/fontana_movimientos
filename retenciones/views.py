from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from comprobantes.models import ComprobanteTipo
from entidades.models import Entidad
from services.ordenamiento import aplicar_orden_lista, aplicar_orden_queryset

from .forms import (
    RetencionHeaderForm,
    RetencionRenglonFormSet,
    RetencionTipoImpuestoForm,
    RetencionTipoRegimenForm,
)
from .models import Retencion, RetencionTipoImpuesto, RetencionTipoRegimen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _siguiente_id_retencion():
    """La tabla 'retencion' no tiene AUTO_INCREMENT en 'id', así que el
    próximo id se calcula a mano (mismo patrón que
    liquidaciones.views._siguiente_id_liquidacion)."""
    ultimo = Retencion.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


def _siguiente_numero_retencion(anio):
    ultimo = Retencion.objects.filter(año=anio).aggregate(Max('numero'))['numero__max'] or 0
    return ultimo + 1


def _formatear_cuit(cuit):
    """Devuelve el CUIT separado como XX-XXXXXXXX-X. Si no tiene el formato
    esperado (11 dígitos), lo muestra tal cual está guardado."""
    if not cuit:
        return ''
    digitos = ''.join(c for c in str(cuit) if c.isdigit())
    if len(digitos) == 11:
        return f'{digitos[:2]}-{digitos[2:10]}-{digitos[10:]}'
    return str(cuit)


def _formatear_domicilio(entidad):
    if not entidad:
        return ''
    partes = [entidad.direccion, entidad.localidad, entidad.provincia]
    domicilio = ' - '.join(p for p in partes if p)
    if entidad.codpos:
        domicilio = f'{domicilio} ({entidad.codpos})' if domicilio else f'({entidad.codpos})'
    return domicilio


def _combinar_comprobante_origen(punto_venta, numero_comprobante):
    if punto_venta is None or numero_comprobante is None:
        return ''
    return f'{int(punto_venta):05d}-{int(numero_comprobante):08d}'


def _parsear_comprobante_origen(valor):
    """Inverso de _combinar_comprobante_origen, para precargar el form de
    Modificación a partir de lo guardado en comprobante_origen."""
    if not valor or '-' not in valor:
        return None, None
    izquierda, derecha = valor.split('-', 1)
    try:
        return int(izquierda), int(derecha)
    except ValueError:
        return None, None


def _calcular_total(subtotal, porcentaje):
    if subtotal is None or porcentaje is None:
        return None
    return (Decimal(str(subtotal)) * Decimal(str(porcentaje)) / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def _grupo_queryset(anio, numero):
    return (
        Retencion.objects
        .filter(año=anio, numero=numero)
        .select_related('entidad', 'id_impuesto', 'id_regimen')
        .order_by('id')
    )


def _tiene_liquidacion(anio, numero):
    """True si alguno de los renglones de este comprobante ya está incluido
    en una liquidación (liquidacion_retencion tiene ON DELETE RESTRICT hacia
    retencion: borrar esos renglones para 'reemplazarlos' en una
    modificación rompería esa liquidación, así que no se permite)."""
    from liquidaciones.models import LiquidacionRetencion
    return LiquidacionRetencion.objects.filter(
        retencion__año=anio, retencion__numero=numero
    ).exists()


def _tipos_comprobante_por_id():
    return {t.id: t for t in ComprobanteTipo.objects.all()}


def _regimen_impuesto_map():
    """Mapa {id_regimen: id_impuesto} para que el JS del form condicione el
    combo de Régimen según el Impuesto elegido (y viceversa)."""
    return {
        str(r.id): r.impuesto_id
        for r in RetencionTipoRegimen.objects.all()
    }


def _texto_comprobante_origen(retencion, tipos_por_id):
    tipo = tipos_por_id.get(retencion.tipo_comp_origen)
    abreviatura = tipo.abreviatura if tipo and tipo.abreviatura else ''
    origen = retencion.comprobante_origen or ''
    return f'{abreviatura} {origen}'.strip()


def _armar_formset_inicial(lineas, tipos_por_id):
    inicial = []
    for r in lineas:
        punto_venta, numero_comprobante = _parsear_comprobante_origen(r.comprobante_origen)
        inicial.append({
            'tipo_comp_origen': r.tipo_comp_origen,
            'punto_venta': punto_venta,
            'numero_comprobante': numero_comprobante,
            'fecha_comp_origen': r.fecha_comp_origen,
            'subtotal': r.subtotal,
            'porcentaje': r.porcentaje,
            'total': r.total,
        })
    return inicial


# ---------------------------------------------------------------------------
# Alta / Modificación (comparten casi toda la lógica de guardado)
# ---------------------------------------------------------------------------

def _guardar_grupo(request, header_form, formset, entidad_nombre_snapshot):
    """Crea los renglones (Retencion) de un comprobante a partir del header
    form y el formset ya validados. Devuelve la lista de ids creados."""
    entidad = header_form.cleaned_data.get('entidad')
    entidad_nombre = header_form.cleaned_data.get('entidad_nombre') or (entidad.nombre if entidad else '')
    id_impuesto = header_form.cleaned_data.get('id_impuesto')
    id_regimen = header_form.cleaned_data.get('id_regimen')
    anio = header_form.cleaned_data['año']
    numero = header_form.cleaned_data['numero']

    siguiente_id = _siguiente_id_retencion()
    creados = []
    comprobante_string = f'{anio}-{numero:04d}'

    for form in formset:
        datos = form.cleaned_data
        if not datos or datos.get('_vacio'):
            continue
        punto_venta = datos.get('punto_venta')
        numero_comprobante = datos.get('numero_comprobante')
        subtotal = datos.get('subtotal')
        porcentaje = datos.get('porcentaje')
        total = _calcular_total(subtotal, porcentaje)

        Retencion.objects.create(
            id=siguiente_id,
            entidad=entidad,
            entidad_nombre=entidad_nombre,
            subtotal=subtotal,
            porcentaje=porcentaje,
            total=total,
            comprobante_string=comprobante_string,
            fecha=datos.get('fecha_comp_origen'),
            id_impuesto=id_impuesto,
            id_regimen=id_regimen,
            tipo_comp_origen=datos.get('tipo_comp_origen').id if datos.get('tipo_comp_origen') else None,
            comprobante_origen=_combinar_comprobante_origen(punto_venta, numero_comprobante),
            fecha_comp_origen=datos.get('fecha_comp_origen'),
            monto_comp_origen=subtotal,
            año=anio,
            numero=numero,
            agregado_desde='retenciones_app',
        )
        creados.append(siguiente_id)
        siguiente_id += 1

    return creados


def retencion_alta(request):
    if request.method == 'POST':
        header_form = RetencionHeaderForm(request.POST)
        formset = RetencionRenglonFormSet(request.POST, prefix='form')

        if header_form.is_valid() and formset.is_valid():
            lineas_validas = [f for f in formset if f.cleaned_data and not f.cleaned_data.get('_vacio')]
            if not lineas_validas:
                messages.error(request, 'Cargá al menos un renglón con los datos de la operación.')
            else:
                with transaction.atomic():
                    creados = _guardar_grupo(request, header_form, formset, None)

                anio = header_form.cleaned_data['año']
                numero = header_form.cleaned_data['numero']
                accion = request.POST.get('accion')
                messages.success(
                    request,
                    f'El comprobante de retención {anio}-{numero:04d} se guardó correctamente '
                    f'({len(creados)} renglón{"es" if len(creados) != 1 else ""}).'
                )
                if accion == 'pdf':
                    return retencion_pdf(request, anio, numero)
                if accion == 'excel':
                    return retencion_excel(request, anio, numero)
                return redirect('retenciones:listado')
    else:
        anio_actual = __import__('datetime').date.today().year
        header_form = RetencionHeaderForm(initial={
            'año': anio_actual,
            'numero': _siguiente_numero_retencion(anio_actual),
        })
        formset = RetencionRenglonFormSet(prefix='form')

    return render(request, 'retenciones/retencion_form.html', {
        'header_form': header_form,
        'formset': formset,
        'modo': 'alta',
        'regimen_impuesto_map': _regimen_impuesto_map(),
    })


def retencion_modificar(request, anio, numero):
    lineas = list(_grupo_queryset(anio, numero))
    if not lineas:
        messages.error(request, f'No se encontró el comprobante de retención {anio}-{numero:04d}.')
        return redirect('retenciones:listado')

    if _tiene_liquidacion(anio, numero):
        messages.error(
            request,
            f'El comprobante {anio}-{numero:04d} ya tiene retenciones incluidas en una '
            'liquidación y no se puede modificar desde acá.'
        )
        return redirect('retenciones:listado')

    primera = lineas[0]
    tipos_por_id = _tipos_comprobante_por_id()

    if request.method == 'POST':
        header_form = RetencionHeaderForm(request.POST)
        formset = RetencionRenglonFormSet(request.POST, prefix='form')

        if header_form.is_valid() and formset.is_valid():
            lineas_validas = [f for f in formset if f.cleaned_data and not f.cleaned_data.get('_vacio')]
            if not lineas_validas:
                messages.error(request, 'Cargá al menos un renglón con los datos de la operación.')
            else:
                with transaction.atomic():
                    Retencion.objects.filter(año=anio, numero=numero).delete()
                    _guardar_grupo(request, header_form, formset, None)

                nuevo_anio = header_form.cleaned_data['año']
                nuevo_numero = header_form.cleaned_data['numero']
                accion = request.POST.get('accion')
                messages.success(
                    request,
                    f'El comprobante de retención {nuevo_anio}-{nuevo_numero:04d} se modificó correctamente.'
                )
                if accion == 'pdf':
                    return retencion_pdf(request, nuevo_anio, nuevo_numero)
                if accion == 'excel':
                    return retencion_excel(request, nuevo_anio, nuevo_numero)
                return redirect('retenciones:listado')
    else:
        header_form = RetencionHeaderForm(initial={
            'entidad': primera.entidad,
            'entidad_nombre': primera.entidad_nombre or (primera.entidad.nombre if primera.entidad else ''),
            'id_impuesto': primera.id_impuesto,
            'id_regimen': primera.id_regimen,
            'año': primera.año,
            'numero': primera.numero,
        })
        formset = RetencionRenglonFormSet(
            prefix='form',
            initial=_armar_formset_inicial(lineas, tipos_por_id),
        )
        formset.extra = 1

    return render(request, 'retenciones/retencion_form.html', {
        'header_form': header_form,
        'formset': formset,
        'modo': 'modificar',
        'anio': anio,
        'numero': numero,
        'entidad_texto': primera.entidad_nombre or (str(primera.entidad) if primera.entidad else ''),
        'regimen_impuesto_map': _regimen_impuesto_map(),
    })


def retencion_eliminar(request, anio, numero):
    lineas = list(_grupo_queryset(anio, numero))
    if not lineas:
        messages.error(request, f'No se encontró el comprobante de retención {anio}-{numero:04d}.')
        return redirect('retenciones:listado')

    if request.method == 'POST':
        if _tiene_liquidacion(anio, numero):
            messages.error(
                request,
                f'El comprobante {anio}-{numero:04d} ya tiene retenciones incluidas en una '
                'liquidación y no se puede eliminar desde acá.'
            )
            return redirect('retenciones:listado')

        Retencion.objects.filter(año=anio, numero=numero).delete()
        messages.success(request, f'El comprobante de retención {anio}-{numero:04d} se eliminó correctamente.')
        return redirect('retenciones:listado')

    total = sum((l.total or Decimal('0')) for l in lineas)
    return render(request, 'retenciones/retencion_eliminar_confirm.html', {
        'anio': anio,
        'numero': numero,
        'lineas': lineas,
        'total': total,
        'entidad_nombre': lineas[0].entidad_nombre or (str(lineas[0].entidad) if lineas[0].entidad else ''),
    })


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------

def retencion_listado(request):
    q_anio = request.GET.get('anio', '').strip()
    q_numero = request.GET.get('numero', '').strip()
    q_entidad = request.GET.get('entidad', '').strip()

    qs = Retencion.objects.select_related('entidad')
    if q_anio.isdigit():
        qs = qs.filter(año=int(q_anio))
    if q_numero.isdigit():
        qs = qs.filter(numero=int(q_numero))
    if q_entidad:
        qs = qs.filter(Q(entidad_nombre__icontains=q_entidad) | Q(entidad__nombre__icontains=q_entidad))

    grupos = {}
    for r in qs.order_by('-año', '-numero'):
        clave = (r.año, r.numero)
        if clave not in grupos:
            grupos[clave] = {
                'año': r.año,
                'numero': r.numero,
                'entidad_nombre': r.entidad_nombre or (str(r.entidad) if r.entidad else ''),
                'fecha': r.fecha,
                'cantidad_renglones': 0,
                'total': Decimal('0'),
            }
        grupos[clave]['cantidad_renglones'] += 1
        grupos[clave]['total'] += (r.total or Decimal('0'))
        if r.fecha and (grupos[clave]['fecha'] is None or r.fecha > grupos[clave]['fecha']):
            grupos[clave]['fecha'] = r.fecha

    campos_orden = {
        'anio': lambda g: g['año'] or 0,
        'numero': lambda g: g['numero'] or 0,
        'entidad': lambda g: (g['entidad_nombre'] or '').lower(),
        'fecha': lambda g: g['fecha'],
        'renglones': lambda g: g['cantidad_renglones'],
        'total': lambda g: g['total'],
    }
    if request.GET.get('orden') in campos_orden:
        lista = aplicar_orden_lista(request, list(grupos.values()), campos_orden)
    else:
        # Sin orden pedido por columna: más recientes primero (año y número
        # descendente), mismo criterio que antes de poder ordenar por columna.
        lista = sorted(grupos.values(), key=lambda g: (g['año'] or 0, g['numero'] or 0), reverse=True)
    lista = lista[:500]

    return render(request, 'retenciones/retencion_listado.html', {
        'grupos': lista,
        'q_anio': q_anio,
        'q_numero': q_numero,
        'q_entidad': q_entidad,
    })


# ---------------------------------------------------------------------------
# Impresión (PDF / Excel), formato "Constancia de Retención"
# ---------------------------------------------------------------------------

def _contexto_impresion(anio, numero):
    lineas = list(_grupo_queryset(anio, numero))
    if not lineas:
        return None
    primera = lineas[0]
    tipos_por_id = _tipos_comprobante_por_id()

    for l in lineas:
        l.texto_factura = _texto_comprobante_origen(l, tipos_por_id)

    total = sum((l.total or Decimal('0')) for l in lineas)

    return {
        'anio': anio,
        'numero': numero,
        'entidad': primera.entidad,
        'entidad_nombre': primera.entidad_nombre or (str(primera.entidad) if primera.entidad else ''),
        'domicilio': _formatear_domicilio(primera.entidad),
        'cuit': _formatear_cuit(primera.entidad.cuit) if primera.entidad else '',
        'regimen': primera.id_regimen,
        'lineas': lineas,
        'total': total,
    }


def retencion_pdf(request, anio, numero):
    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from movimientos.templatetags.movimientos_extras import separador_miles

    contexto = _contexto_impresion(anio, numero)
    if contexto is None:
        messages.error(request, f'No se encontró el comprobante de retención {anio}-{numero:04d}.')
        return redirect('retenciones:listado')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=retencion_{anio}_{numero:04d}.pdf'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    estilos = getSampleStyleSheet()
    titulo_estilo = ParagraphStyle('titulo_retencion', parent=estilos['Title'], fontSize=13)
    subtitulo_estilo = ParagraphStyle('subtitulo_retencion', parent=estilos['Normal'], alignment=1, fontSize=9)

    regimen_nombre = str(contexto['regimen']) if contexto['regimen'] else ''

    elementos = [
        Paragraph('CONSTANCIA DE RETENCIÓN', titulo_estilo),
    ]
    if regimen_nombre:
        elementos.append(Paragraph(regimen_nombre, subtitulo_estilo))
    elementos.append(Paragraph(
        f"<b>COMPROBANTE Nº</b> {anio}- {numero:04d}", subtitulo_estilo
    ))
    elementos.append(Spacer(1, 0.5 * cm))

    datos_proveedor = [
        ['Proveedor', contexto['entidad_nombre']],
        ['Domicilio', contexto['domicilio']],
        ['CUIT Nº', contexto['cuit']],
    ]
    tabla_proveedor = Table(datos_proveedor, colWidths=[3 * cm, 14 * cm])
    tabla_proveedor.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla_proveedor)
    elementos.append(Spacer(1, 0.5 * cm))
    elementos.append(Paragraph('<b>DETALLE DE LAS OPERACIONES</b>', estilos['Normal']))
    elementos.append(Spacer(1, 0.2 * cm))

    filas = [['Fecha', 'Factura', 'Importe', 'Porcentaje', 'Retención']]
    for l in contexto['lineas']:
        filas.append([
            l.fecha_comp_origen.strftime('%d/%m/%Y') if l.fecha_comp_origen else '-',
            l.texto_factura or '-',
            separador_miles(l.subtotal) if l.subtotal is not None else '-',
            f'{l.porcentaje:g}%' if l.porcentaje is not None else '-',
            separador_miles(l.total) if l.total is not None else '-',
        ])

    tabla_detalle = Table(filas, colWidths=[2.5 * cm, 5 * cm, 4 * cm, 3 * cm, 4.5 * cm], repeatRows=1)
    tabla_detalle.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(tabla_detalle)
    elementos.append(Spacer(1, 0.3 * cm))

    tabla_total = Table([['TOTAL $', separador_miles(contexto['total'])]], colWidths=[15 * cm, 4 * cm])
    tabla_total.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOX', (1, 0), (1, 0), 0.75, colors.black),
    ]))
    elementos.append(tabla_total)
    elementos.append(Spacer(1, 1.2 * cm))
    elementos.append(Paragraph('_' * 30, estilos['Normal']))
    elementos.append(Paragraph('FIRMA', ParagraphStyle('firma', parent=estilos['Normal'], alignment=1)))

    doc.build(elementos)
    return response


def retencion_excel(request, anio, numero):
    import openpyxl
    from django.http import HttpResponse
    from openpyxl.styles import Font, Alignment
    from services.gestorexcel import definir_estilo_general, formatear_celda_fecha, formatear_celda_numero

    contexto = _contexto_impresion(anio, numero)
    if contexto is None:
        messages.error(request, f'No se encontró el comprobante de retención {anio}-{numero:04d}.')
        return redirect('retenciones:listado')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Constancia de Retención'

    regimen_nombre = str(contexto['regimen']) if contexto['regimen'] else ''
    ws.append(['CONSTANCIA DE RETENCIÓN'])
    if regimen_nombre:
        ws.append([regimen_nombre])
    ws.append([f'COMPROBANTE Nº {anio}- {numero:04d}'])
    ws.append([''])
    ws.append(['Proveedor', contexto['entidad_nombre']])
    ws.append(['Domicilio', contexto['domicilio']])
    ws.append(['CUIT Nº', contexto['cuit']])
    ws.append([''])
    fila_encabezado = ws.max_row + 1
    ws.append(['Fecha', 'Factura', 'Importe', 'Porcentaje', 'Retención'])

    for l in contexto['lineas']:
        ws.append([
            l.fecha_comp_origen,
            l.texto_factura or '',
            float(l.subtotal) if l.subtotal is not None else None,
            l.porcentaje,
            float(l.total) if l.total is not None else None,
        ])

    fila_totales = ws.max_row + 1
    ws.append(['', '', '', 'Total', float(contexto['total'])])

    formatear_celda_fecha(wb, ws, 'A')
    for columna in ('C', 'E'):
        for cell in ws[columna]:
            if cell.row > fila_encabezado:
                cell.number_format = '#,##0.00'
    for cell in ws['D']:
        if cell.row > fila_encabezado:
            cell.number_format = '0.00"%"'

    definir_estilo_general(ws)

    fuente_titulo = Font(name='Arial', size=12, bold=True)
    ws['A1'].font = fuente_titulo
    for fila in range(1, fila_encabezado):
        for cell in ws[fila]:
            cell.font = Font(name='Arial', size=9, bold=(cell.column_letter == 'A'))

    fuente_total = Font(name='Arial', size=9, bold=True)
    for cell in ws[fila_totales]:
        cell.font = fuente_total

    ws.column_dimensions['B'].width = 30
    for cell in ws['B']:
        cell.alignment = Alignment(wrap_text=True, vertical='top')

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=retencion_{anio}_{numero:04d}.xlsx'
    wb.save(response)
    return response


# ---------------------------------------------------------------------------
# Ret. Impuestos: alta / modificación / listado
# ---------------------------------------------------------------------------

def _siguiente_id_tipo_impuesto():
    ultimo = RetencionTipoImpuesto.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


def retencion_tipo_impuesto_listado(request):
    impuestos = RetencionTipoImpuesto.objects.all().order_by('nombre')
    impuestos = aplicar_orden_queryset(request, impuestos, {
        'id': 'id',
        'nombre': 'nombre',
    })
    return render(request, 'retenciones/retencion_tipo_impuesto_listado.html', {
        'impuestos': impuestos,
    })


def retencion_tipo_impuesto_alta(request):
    if request.method == 'POST':
        form = RetencionTipoImpuestoForm(request.POST)
        if form.is_valid():
            impuesto = form.save(commit=False)
            impuesto.id = _siguiente_id_tipo_impuesto()
            impuesto.save(force_insert=True)
            messages.success(request, f'El impuesto "{impuesto.nombre}" se creó correctamente.')
            return redirect('retenciones:tipo_impuesto_listado')
    else:
        form = RetencionTipoImpuestoForm()

    return render(request, 'retenciones/retencion_tipo_impuesto_form.html', {
        'form': form,
        'modo': 'alta',
    })


def retencion_tipo_impuesto_modificar(request, pk):
    impuesto = get_object_or_404(RetencionTipoImpuesto, pk=pk)

    if request.method == 'POST':
        form = RetencionTipoImpuestoForm(request.POST, instance=impuesto)
        if form.is_valid():
            form.save()
            messages.success(request, f'El impuesto "{impuesto.nombre}" se modificó correctamente.')
            return redirect('retenciones:tipo_impuesto_listado')
    else:
        form = RetencionTipoImpuestoForm(instance=impuesto)

    return render(request, 'retenciones/retencion_tipo_impuesto_form.html', {
        'form': form,
        'modo': 'modificar',
        'impuesto': impuesto,
    })


def retencion_tipo_impuesto_eliminar(request, pk):
    """Confirmación + baja de un RetencionTipoImpuesto. Se bloquea si está en
    uso (por una retención directamente, o por un régimen que lo referencia),
    ya que la FK está declarada DO_NOTHING y no lo impediría en la base."""
    impuesto = get_object_or_404(RetencionTipoImpuesto, pk=pk)

    en_uso = (
        Retencion.objects.filter(id_impuesto=impuesto).exists()
        or RetencionTipoRegimen.objects.filter(impuesto=impuesto).exists()
    )
    if en_uso:
        messages.error(
            request,
            f'El impuesto "{impuesto.nombre}" está siendo usado en una retención o en un '
            'régimen y no se puede eliminar.'
        )
        return redirect('retenciones:tipo_impuesto_listado')

    if request.method == 'POST':
        nombre = impuesto.nombre
        impuesto.delete()
        messages.success(request, f'El impuesto "{nombre}" se eliminó correctamente.')
        return redirect('retenciones:tipo_impuesto_listado')

    return render(request, 'retenciones/retencion_tipo_impuesto_eliminar_confirm.html', {
        'impuesto': impuesto,
    })


# ---------------------------------------------------------------------------
# Ret. Regimenes: alta / modificación / listado
# ---------------------------------------------------------------------------

def _siguiente_id_tipo_regimen():
    ultimo = RetencionTipoRegimen.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


def retencion_tipo_regimen_listado(request):
    regimenes = RetencionTipoRegimen.objects.select_related('impuesto').order_by('nombre')
    regimenes = aplicar_orden_queryset(request, regimenes, {
        'id': 'id',
        'nombre': 'nombre',
        'impuesto': 'impuesto__nombre',
    })
    return render(request, 'retenciones/retencion_tipo_regimen_listado.html', {
        'regimenes': regimenes,
    })


def retencion_tipo_regimen_alta(request):
    if request.method == 'POST':
        form = RetencionTipoRegimenForm(request.POST)
        if form.is_valid():
            regimen = form.save(commit=False)
            regimen.id = _siguiente_id_tipo_regimen()
            regimen.save(force_insert=True)
            messages.success(request, f'El régimen "{regimen.nombre}" se creó correctamente.')
            return redirect('retenciones:tipo_regimen_listado')
    else:
        form = RetencionTipoRegimenForm()

    return render(request, 'retenciones/retencion_tipo_regimen_form.html', {
        'form': form,
        'modo': 'alta',
    })


def retencion_tipo_regimen_modificar(request, pk):
    regimen = get_object_or_404(RetencionTipoRegimen, pk=pk)

    if request.method == 'POST':
        form = RetencionTipoRegimenForm(request.POST, instance=regimen)
        if form.is_valid():
            form.save()
            messages.success(request, f'El régimen "{regimen.nombre}" se modificó correctamente.')
            return redirect('retenciones:tipo_regimen_listado')
    else:
        form = RetencionTipoRegimenForm(instance=regimen)

    return render(request, 'retenciones/retencion_tipo_regimen_form.html', {
        'form': form,
        'modo': 'modificar',
        'regimen': regimen,
    })


def retencion_tipo_regimen_eliminar(request, pk):
    """Confirmación + baja de un RetencionTipoRegimen. Se bloquea si está en
    uso por alguna retención, ya que la FK está declarada DO_NOTHING y no lo
    impediría en la base."""
    regimen = get_object_or_404(RetencionTipoRegimen, pk=pk)

    if Retencion.objects.filter(id_regimen=regimen).exists():
        messages.error(
            request,
            f'El régimen "{regimen.nombre}" está siendo usado en una retención y no se puede eliminar.'
        )
        return redirect('retenciones:tipo_regimen_listado')

    if request.method == 'POST':
        nombre = regimen.nombre
        regimen.delete()
        messages.success(request, f'El régimen "{nombre}" se eliminó correctamente.')
        return redirect('retenciones:tipo_regimen_listado')

    return render(request, 'retenciones/retencion_tipo_regimen_eliminar_confirm.html', {
        'regimen': regimen,
    })
