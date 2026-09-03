from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from comprobantes.models import ComprobanteRenglon
from services.forms import BuscarConFechasForm
from services.ordenamiento import aplicar_orden_queryset
from services.reportes import excel_response, pdf_response

from .forms import ProductoDetalleForm
from .models import ProductoDetalle


def producto_buscar(request):
    """
    Devuelve, en JSON, hasta 20 productos del catálogo (producto_detalle)
    cuyo nombre o ID coincidan con el texto buscado. Usado por el buscador
    de "producto de catálogo" de los renglones de Solicitud de Compra.
    """
    q = request.GET.get('q', '').strip()
    resultados = []
    if q:
        filtro = Q(nombre__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))
        productos = ProductoDetalle.objects.filter(filtro).order_by('nombre')[:20]
        resultados = [{'id': p.id, 'text': str(p)} for p in productos]
    return JsonResponse({'resultados': resultados})


# ---------------------------------------------------------------------------
# Alta / Modificar / Reportes de ProductoDetalle (menú Tipos > Productos)
# ---------------------------------------------------------------------------

def _siguiente_id_producto_detalle():
    """Igual que en comprobantes.views: producto_detalle.id no tiene
    AUTO_INCREMENT (ver estructura_bd.sql), así que el próximo id se
    calcula a mano."""
    ultimo = ProductoDetalle.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


def producto_alta(request):
    """Alta de un producto/ítem del catálogo (producto_detalle). Usa el
    mismo formulario (ProductoDetalleForm) que reusa comprobantes.forms.
    ProductoDetalleCrearForm para el alta rápida embebida en el renglón de
    comprobante."""
    if request.method == 'POST':
        form = ProductoDetalleForm(request.POST)
        if form.is_valid():
            producto = form.save(commit=False)
            producto.id = _siguiente_id_producto_detalle()
            producto.save(force_insert=True)
            messages.success(request, f'Producto "{producto}" se creó correctamente.')
            return redirect('productos:producto_modificar')
    else:
        form = ProductoDetalleForm()

    return render(request, 'productos/producto_form.html', {'form': form, 'modo': 'alta'})


def producto_listado(request):
    """Listado/búsqueda de productos; puerta de entrada de 'Modificación'."""
    productos = ProductoDetalle.objects.select_related('item_tipo').order_by('nombre')

    q = request.GET.get('q', '').strip()
    if q:
        filtro = Q(nombre__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))
        productos = productos.filter(filtro)

    productos = aplicar_orden_queryset(request, productos, {
        'id': 'id',
        'nombre': 'nombre',
        'categoria': 'item_tipo__nombre',
    })

    return render(request, 'productos/producto_listado.html', {
        'productos': productos[:500],
        'q': q,
    })


def producto_editar(request, pk):
    producto = get_object_or_404(ProductoDetalle, pk=pk)

    if request.method == 'POST':
        form = ProductoDetalleForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Producto "{producto}" se modificó correctamente.')
            return redirect('productos:producto_modificar')
    else:
        form = ProductoDetalleForm(instance=producto)

    return render(request, 'productos/producto_form.html', {
        'form': form, 'modo': 'modificar', 'producto': producto,
    })


# --- Reporte: totales por producto en un intervalo de fechas de renglones ---

def _renglones_reporte_producto_filtrados(request):
    """Aplica a ComprobanteRenglon el filtro de fecha (BuscarConFechasForm,
    sobre comprobante.fecha). Centralizado para que la pantalla y las
    exportaciones (Excel/PDF) usen siempre el mismo criterio."""
    form = BuscarConFechasForm(request.GET or None)
    renglones = ComprobanteRenglon.objects.all()

    filtros_activos = False
    if form.is_valid():
        fecha_desde = form.cleaned_data.get('fecha_desde')
        fecha_hasta = form.cleaned_data.get('fecha_hasta')
        if fecha_desde:
            renglones = renglones.filter(comprobante__fecha__gte=fecha_desde)
        if fecha_hasta:
            renglones = renglones.filter(comprobante__fecha__lte=fecha_hasta)
        filtros_activos = bool(fecha_desde or fecha_hasta)

    return form, renglones, filtros_activos


def _totales_por_producto(renglones):
    """A partir de un queryset de ComprobanteRenglon (ya filtrado por
    fecha), suma 'total' agrupando por producto."""
    return (
        renglones.values('producto_id', 'producto__nombre', 'producto__item_tipo__nombre')
        .annotate(
            cantidad_renglones=Count('id'),
            total_monto=Coalesce(
                Sum('total'), Value(Decimal('0')), output_field=DecimalField(max_digits=20, decimal_places=2)
            ),
        )
        .order_by('-total_monto')
    )


def producto_reporte(request):
    """Listado de totales por producto (suma de 'total' de sus renglones de
    comprobante), en un intervalo de fechas opcional."""
    form, renglones, filtros_activos = _renglones_reporte_producto_filtrados(request)
    resultados = _totales_por_producto(renglones)
    resultados = aplicar_orden_queryset(request, resultados, {
        'producto': 'producto__nombre',
        'categoria': 'producto__item_tipo__nombre',
        'cantidad': 'cantidad_renglones',
        'total': 'total_monto',
    })

    total_general = resultados.aggregate(
        total=Coalesce(
            Sum('total_monto'), Value(Decimal('0')), output_field=DecimalField(max_digits=20, decimal_places=2)
        )
    )['total']

    return render(request, 'productos/producto_reporte.html', {
        'form': form,
        'resultados': resultados,
        'total_general': total_general,
        'filtros_activos': filtros_activos,
    })


def _filas_reporte_producto(resultados):
    columnas = ['Producto', 'Categoría', 'Renglones', 'Total']
    filas = [
        [
            fila['producto__nombre'] or f"#{fila['producto_id']}",
            fila['producto__item_tipo__nombre'] or '-',
            fila['cantidad_renglones'],
            float(fila['total_monto']) if fila['total_monto'] is not None else None,
        ]
        for fila in resultados
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': {3},
        'anchos': [2.4, 1.4, 1.0, 1.2],
    }


def producto_reporte_excel(request):
    _form, renglones, _filtros_activos = _renglones_reporte_producto_filtrados(request)
    resultado = _filas_reporte_producto(_totales_por_producto(renglones))
    return excel_response('totales_por_producto', resultado)


def producto_reporte_pdf(request):
    _form, renglones, _filtros_activos = _renglones_reporte_producto_filtrados(request)
    resultado = _filas_reporte_producto(_totales_por_producto(renglones))
    return pdf_response('totales_por_producto', 'Totales por producto', resultado)
