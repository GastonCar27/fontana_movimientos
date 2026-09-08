from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from comprobantes.models import ComprobanteRenglon
from entidades.models import Entidad
from movimientos.models import Movimiento
from productos.models import ProductoDetalle
from services.ordenamiento import aplicar_orden_lista, aplicar_orden_queryset

from .models import (
    ComprobanteRenglonMovimiento,
    EstadoCuentaMovimiento,
    LiquidacionProducto,
    LiquidacionProductoComprobanteRenglon,
)


# ---------------------------------------------------------------------------
# Movimientos abiertos
# ---------------------------------------------------------------------------

def movimientos_abiertos(request):
    """
    Lista los Movimiento (kg) que siguen "abiertos" -- es decir, que no
    tienen una fila EstadoCuentaMovimiento con estado='cerrado' (o no
    tienen fila, que equivale a "abierto") -- junto con la suma de $ ya
    vinculados (ComprobanteRenglonMovimiento) hasta ahora, estén o no
    todavía incluidos en una liquidación cerrada.
    """
    movimientos = (
        Movimiento.objects
        .exclude(estado_cuenta__estado=EstadoCuentaMovimiento.CERRADO)
        .select_related('producto', 'entidad_emisor', 'entidad_receptor', 'unidad_de_medida')
        .annotate(
            pesos_vinculados=Coalesce(
                Sum('vinculos_comprobante__renglon__total'),
                Value(Decimal('0')),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            ),
            cantidad_vinculos=Count('vinculos_comprobante', distinct=True),
        )
    )

    q_entidad = request.GET.get('entidad', '').strip()
    q_producto = request.GET.get('producto', '').strip()
    q_fecha_desde = request.GET.get('fecha_desde', '').strip()
    q_fecha_hasta = request.GET.get('fecha_hasta', '').strip()

    if q_entidad and q_entidad.isdigit():
        movimientos = movimientos.filter(
            Q(entidad_emisor_id=int(q_entidad)) | Q(entidad_receptor_id=int(q_entidad))
        )
    if q_producto and q_producto.isdigit():
        movimientos = movimientos.filter(producto_id=int(q_producto))
    if q_fecha_desde:
        movimientos = movimientos.filter(fecha__gte=q_fecha_desde)
    if q_fecha_hasta:
        movimientos = movimientos.filter(fecha__lte=q_fecha_hasta)

    movimientos = aplicar_orden_queryset(request, movimientos, {
        'id': 'id_movimiento',
        'fecha': 'fecha',
        'numero': 'numero',
        'producto': 'producto__nombre',
        'emisor': 'entidad_emisor__nombre',
        'receptor': 'entidad_receptor__nombre',
        'total': 'total',
        'pesos_vinculados': 'pesos_vinculados',
    }, default='-fecha')

    entidades = Entidad.objects.filter(activo=True).order_by('nombre')
    productos = ProductoDetalle.objects.order_by('nombre')

    return render(request, 'cuenta_corriente_productos/movimientos_abiertos.html', {
        'movimientos': list(movimientos[:500]),
        'entidades': entidades,
        'productos': productos,
        'q_entidad': q_entidad,
        'q_producto': q_producto,
        'q_fecha_desde': q_fecha_desde,
        'q_fecha_hasta': q_fecha_hasta,
    })


def cerrar_movimiento(request, movimiento_id):
    movimiento = get_object_or_404(Movimiento, pk=movimiento_id)
    if request.method == 'POST':
        estado, _creado = EstadoCuentaMovimiento.objects.get_or_create(movimiento=movimiento)
        estado.cerrar()
        messages.success(request, f'Movimiento {movimiento.id_movimiento} marcado como cerrado.')
    return redirect('cuenta_corriente_productos:movimientos_abiertos')


def reabrir_movimiento(request, movimiento_id):
    movimiento = get_object_or_404(Movimiento, pk=movimiento_id)
    if request.method == 'POST':
        estado, _creado = EstadoCuentaMovimiento.objects.get_or_create(movimiento=movimiento)
        estado.reabrir()
        messages.success(request, f'Movimiento {movimiento.id_movimiento} reabierto.')
    return redirect('cuenta_corriente_productos:movimientos_abiertos')


# ---------------------------------------------------------------------------
# Vincular / desvincular un renglón de comprobante a un movimiento
# ---------------------------------------------------------------------------

def vincular_renglon(request, movimiento_id):
    """
    Busca renglones de comprobante del mismo producto que el movimiento (por
    número de comprobante o nombre de entidad emisora) y permite vincular
    uno de ellos a este movimiento (crea ComprobanteRenglonMovimiento).

    El vínculo NO clasifica todavía el monto como debe/haber -- eso se
    define recién al incluir el renglón en una LiquidacionProducto (ver
    liquidacion_alta). Mientras tanto, el renglón vinculado aparece como
    "pendiente de liquidar" en la cuenta corriente de la entidad.
    """
    movimiento = get_object_or_404(
        Movimiento.objects.select_related('producto', 'entidad_emisor', 'entidad_receptor'),
        pk=movimiento_id,
    )

    if request.method == 'POST':
        renglon_id = request.POST.get('renglon_id')
        if renglon_id:
            renglon = get_object_or_404(ComprobanteRenglon, pk=renglon_id)
            _vinculo, creado = ComprobanteRenglonMovimiento.objects.get_or_create(
                renglon=renglon, movimiento=movimiento,
            )
            if creado:
                messages.success(request, f'Renglón {renglon.id} vinculado al movimiento {movimiento.id_movimiento}.')
            else:
                messages.info(request, 'Ese renglón ya estaba vinculado a este movimiento.')
        else:
            messages.error(request, 'Debe elegir un renglón.')
        return redirect('cuenta_corriente_productos:vincular_renglon', movimiento_id=movimiento.id_movimiento)

    q = request.GET.get('q', '').strip()
    renglones = ComprobanteRenglon.objects.none()
    if q:
        filtro = Q(comprobante__numero__icontains=q) | Q(comprobante__entidad_emisor__nombre__icontains=q)
        renglones = (
            ComprobanteRenglon.objects
            .filter(filtro, producto=movimiento.producto)
            .exclude(vinculos_movimiento__movimiento=movimiento)
            .select_related('comprobante', 'comprobante__entidad_emisor', 'comprobante__tipo_comprobante')
            .order_by('-comprobante__fecha')[:50]
        )

    vinculos_actuales = (
        movimiento.vinculos_comprobante
        .select_related('renglon', 'renglon__comprobante', 'renglon__comprobante__entidad_emisor', 'renglon__comprobante__tipo_comprobante')
    )

    return render(request, 'cuenta_corriente_productos/vincular_renglon.html', {
        'movimiento': movimiento,
        'q': q,
        'renglones': renglones,
        'vinculos_actuales': vinculos_actuales,
    })


def desvincular_renglon(request, vinculo_id):
    vinculo = get_object_or_404(ComprobanteRenglonMovimiento, pk=vinculo_id)
    movimiento_id = vinculo.movimiento_id
    if request.method == 'POST':
        # No se puede desvincular un renglón que ya forma parte de una
        # liquidación cerrada: ahí la baja hay que hacerla revirtiendo esa
        # liquidación primero (ver LiquidacionProductoComprobanteRenglon).
        if hasattr(vinculo.renglon, 'liquidacion_producto'):
            messages.error(request, 'Ese renglón ya está incluido en una liquidación; no se puede desvincular directamente.')
        else:
            vinculo.delete()
            messages.success(request, 'Vínculo eliminado.')
    return redirect('cuenta_corriente_productos:vincular_renglon', movimiento_id=movimiento_id)


# ---------------------------------------------------------------------------
# Cuenta corriente por entidad + producto
# ---------------------------------------------------------------------------

def cuenta_corriente_entidad(request):
    """
    Kg: siempre en vivo, calculado directamente desde Movimiento (nunca se
    "consume" ni se guarda aparte). Debe = kg recibidos por la entidad
    (Movimiento.entidad_receptor = entidad); Haber = kg enviados por la
    entidad (Movimiento.entidad_emisor = entidad).

    Pesos: solo de LiquidacionProducto ya cerradas (debe_pesos/haber_pesos),
    más un total aparte de lo "pendiente de liquidar" (renglones ya
    vinculados a algún movimiento de esta cuenta, pero todavía sin incluir
    en ninguna liquidación) -- ver diseño de cuotas actualizables (anticipo
    + ajustes de precio).
    """
    entidad = None
    producto = None
    entidad_id = request.GET.get('entidad')
    producto_id = request.GET.get('producto')

    if entidad_id:
        entidad = get_object_or_404(Entidad, pk=entidad_id)
    if producto_id:
        producto = get_object_or_404(ProductoDetalle, pk=producto_id)

    resumen = None
    detalle_liquidaciones = None

    if entidad and producto:
        movimientos_qs = Movimiento.objects.filter(producto=producto).filter(
            Q(entidad_emisor=entidad) | Q(entidad_receptor=entidad)
        )

        decimal_kg = DecimalField(max_digits=14, decimal_places=2)
        kg = movimientos_qs.aggregate(
            debe_kg=Coalesce(
                Sum(Case(When(entidad_receptor=entidad, then=F('total')), default=Value(0), output_field=decimal_kg)),
                Value(Decimal('0')), output_field=decimal_kg,
            ),
            haber_kg=Coalesce(
                Sum(Case(When(entidad_emisor=entidad, then=F('total')), default=Value(0), output_field=decimal_kg)),
                Value(Decimal('0')), output_field=decimal_kg,
            ),
        )

        decimal_pesos = DecimalField(max_digits=20, decimal_places=2)
        liquidaciones_qs = LiquidacionProducto.objects.filter(entidad=entidad, producto=producto)
        pesos = liquidaciones_qs.aggregate(
            debe_pesos=Coalesce(Sum('debe_pesos'), Value(Decimal('0')), output_field=decimal_pesos),
            haber_pesos=Coalesce(Sum('haber_pesos'), Value(Decimal('0')), output_field=decimal_pesos),
        )

        pendiente_pesos = (
            ComprobanteRenglonMovimiento.objects
            .filter(movimiento__in=movimientos_qs)
            .exclude(renglon__liquidacion_producto__isnull=False)
            .aggregate(total=Coalesce(Sum('renglon__total'), Value(Decimal('0')), output_field=decimal_pesos))
        )['total']

        resumen = {
            'debe_kg': kg['debe_kg'],
            'haber_kg': kg['haber_kg'],
            'saldo_kg': kg['debe_kg'] - kg['haber_kg'],
            'debe_pesos': pesos['debe_pesos'],
            'haber_pesos': pesos['haber_pesos'],
            'saldo_pesos': pesos['debe_pesos'] - pesos['haber_pesos'],
            'pendiente_pesos': pendiente_pesos,
        }
        detalle_liquidaciones = liquidaciones_qs.order_by('-fecha', '-id')

    entidades = Entidad.objects.filter(activo=True).order_by('nombre')
    productos = ProductoDetalle.objects.order_by('nombre')

    return render(request, 'cuenta_corriente_productos/cuenta_corriente.html', {
        'entidad': entidad,
        'producto': producto,
        'entidades': entidades,
        'productos': productos,
        'resumen': resumen,
        'detalle_liquidaciones': detalle_liquidaciones,
    })


# ---------------------------------------------------------------------------
# Alta de LiquidacionProducto
# ---------------------------------------------------------------------------

@transaction.atomic
def liquidacion_alta(request):
    entidad = None
    producto = None
    fecha = None

    if request.method == 'POST':
        fecha = request.POST.get('fecha')
        entidad_id = request.POST.get('entidad')
        producto_id = request.POST.get('producto')
        entidad = get_object_or_404(Entidad, pk=entidad_id) if entidad_id else None
        producto = get_object_or_404(ProductoDetalle, pk=producto_id) if producto_id else None

        if not fecha or not entidad or not producto:
            messages.error(request, 'Debe indicar fecha, entidad y producto.')
        else:
            a_crear = []
            for renglon_id in request.POST.getlist('renglon_sel'):
                tipo = request.POST.get(f'tipo_{renglon_id}')
                if tipo not in ('debe', 'haber'):
                    continue
                a_crear.append((int(renglon_id), tipo))

            if not a_crear:
                messages.error(request, 'Debe seleccionar al menos un renglón para liquidar.')
            else:
                liquidacion = LiquidacionProducto.objects.create(entidad=entidad, producto=producto, fecha=fecha)
                liquidacion.numero = f'CTA-{liquidacion.id}'
                liquidacion.save(update_fields=['numero'])

                for renglon_id, tipo in a_crear:
                    LiquidacionProductoComprobanteRenglon.objects.create(
                        liquidacion=liquidacion, renglon_id=renglon_id, tipo=tipo,
                    )

                # Única fuente de verdad para debe_pesos/haber_pesos: se
                # recalcula desde la base, no se suma a mano acá arriba.
                liquidacion.recalcular_totales()

                messages.success(request, f'Liquidación {liquidacion.numero} guardada correctamente.')
                return redirect(
                    f"{reverse('cuenta_corriente_productos:cuenta_corriente')}?entidad={entidad.id}&producto={producto.id}"
                )

    else:
        entidad_id = request.GET.get('entidad')
        producto_id = request.GET.get('producto')
        if entidad_id:
            entidad = get_object_or_404(Entidad, pk=entidad_id)
        if producto_id:
            producto = get_object_or_404(ProductoDetalle, pk=producto_id)
        fecha = request.GET.get('fecha') or timezone.localdate().isoformat()

    renglones_pendientes = []
    if entidad and producto:
        movimientos_qs = Movimiento.objects.filter(producto=producto).filter(
            Q(entidad_emisor=entidad) | Q(entidad_receptor=entidad)
        )
        renglones_pendientes = list(
            ComprobanteRenglonMovimiento.objects
            .filter(movimiento__in=movimientos_qs)
            .exclude(renglon__liquidacion_producto__isnull=False)
            .select_related(
                'renglon', 'renglon__comprobante', 'renglon__comprobante__tipo_comprobante', 'movimiento',
            )
            .order_by('-renglon__comprobante__fecha')
        )

    entidades = Entidad.objects.filter(activo=True).order_by('nombre')
    productos = ProductoDetalle.objects.order_by('nombre')

    return render(request, 'cuenta_corriente_productos/liquidacion_alta.html', {
        'entidad': entidad,
        'producto': producto,
        'fecha': fecha,
        'entidades': entidades,
        'productos': productos,
        'renglones_pendientes': renglones_pendientes,
    })


# ---------------------------------------------------------------------------
# Diferencias (debe/haber guardado vs. recalculado desde los renglones)
# ---------------------------------------------------------------------------

def diferencias(request):
    """
    Compara, para cada LiquidacionProducto, el debe_pesos/haber_pesos
    guardado contra lo que da recalcularlo desde los renglones vinculados
    -- mismo espíritu que liquidaciones.liquidacion_diferencias, resuelto
    acá con un recalculo en memoria (sin guardar) por cada fila, ya que el
    volumen esperado de liquidaciones de producto es bajo.
    """
    filas = []
    for liquidacion in LiquidacionProducto.objects.select_related('entidad', 'producto').order_by('-fecha', '-id'):
        debe_guardado = liquidacion.debe_pesos or Decimal('0')
        haber_guardado = liquidacion.haber_pesos or Decimal('0')
        debe_calculado, haber_calculado = liquidacion.recalcular_totales(guardar=False)
        if debe_guardado != debe_calculado or haber_guardado != haber_calculado:
            filas.append({
                'liquidacion': liquidacion,
                'debe_guardado': debe_guardado,
                'haber_guardado': haber_guardado,
                'debe_calculado': debe_calculado,
                'haber_calculado': haber_calculado,
                'diferencia_debe': debe_guardado - debe_calculado,
                'diferencia_haber': haber_guardado - haber_calculado,
            })

    filas = aplicar_orden_lista(request, filas, {
        'numero': lambda f: f['liquidacion'].numero or '',
        'fecha': lambda f: f['liquidacion'].fecha,
        'entidad': lambda f: str(f['liquidacion'].entidad or '').lower(),
        'diferencia_debe': lambda f: f['diferencia_debe'],
        'diferencia_haber': lambda f: f['diferencia_haber'],
    })

    return render(request, 'cuenta_corriente_productos/diferencias.html', {'filas': filas})


def recalcular_liquidacion(request, pk):
    liquidacion = get_object_or_404(LiquidacionProducto, pk=pk)
    if request.method == 'POST':
        liquidacion.recalcular_totales()
        messages.success(request, f'Liquidación {liquidacion.numero} recalculada y actualizada.')
    return redirect('cuenta_corriente_productos:diferencias')
