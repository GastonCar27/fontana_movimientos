from decimal import Decimal

from django.db.models import Count, Sum
from django.shortcuts import render

from services.ordenamiento import aplicar_orden_lista
from services.permisos import requiere_grupo
from services.reportes import excel_response, pdf_response

from .forms import RankingEntidadesForm
from .models import RetencionInym


# ---------------------------------------------------------------------------
# Ranking de entidades retenidas (por monto total de retenciones INYM,
# filtrando por un lapso de fecha) — mismo patrón que
# comprobantes.views.comprobante_ranking_entidades /
# movimientos_caja.views.movimiento_caja_ranking_entidades. Se ranquea por
# 'operador_retenido' (a quién se le retuvo), mismo criterio direccional
# que movimientos_caja.views usa con 'receptor'.
# ---------------------------------------------------------------------------

# Entidad que representa a la propia empresa (Fontana); mismo id que usan
# comprobantes.views.ENTIDAD_PROPIA_ID, movimientos_caja.views.ENTIDAD_PROPIA_ID,
# liquidaciones.views.ENTIDAD_PROPIA_ID y retenciones.views.ENTIDAD_PROPIA_ID.
ENTIDAD_PROPIA_ID = 100


def _retenciones_inym_ranking_filtrados(request):
    """Aplica a RetencionInym los filtros de RankingEntidadesForm (fecha y,
    opcionalmente, excluir a Fontana). Devuelve (form, queryset,
    filtros_activos), centralizado para que la pantalla y las
    exportaciones (Excel / PDF) usen siempre los mismos criterios."""
    form = RankingEntidadesForm(request.GET or None)
    retenciones = RetencionInym.objects.filter(operador_retenido__isnull=False)

    filtros_activos = False
    if form.is_valid():
        fecha_desde = form.cleaned_data.get('fecha_desde')
        fecha_hasta = form.cleaned_data.get('fecha_hasta')
        excluir_fontana = form.cleaned_data.get('excluir_fontana')
        if fecha_desde:
            retenciones = retenciones.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            retenciones = retenciones.filter(fecha__lte=fecha_hasta)
        if excluir_fontana:
            retenciones = retenciones.exclude(operador_retenido__entidad_id=ENTIDAD_PROPIA_ID)
        filtros_activos = bool(fecha_desde or fecha_hasta or excluir_fontana)

    return form, retenciones, filtros_activos


def _calcular_ranking_retenciones_inym(retenciones):
    """A partir de un queryset de RetencionInym, arma el ranking de
    entidades retenidas por monto total (de mayor a menor) y el total
    general. Devuelve (ranking, total_general)."""
    ranking = list(
        retenciones.values('operador_retenido_id', 'operador_retenido__entidad__nombre')
        .annotate(total_monto=Sum('total'), cantidad=Count('id'))
        .order_by('-total_monto')
    )

    total_general = sum(
        (fila['total_monto'] for fila in ranking if fila['total_monto'] is not None), Decimal('0')
    )
    for posicion, fila in enumerate(ranking, start=1):
        fila['posicion'] = posicion
        fila['porcentaje'] = (
            fila['total_monto'] / total_general * 100
            if total_general and fila['total_monto'] is not None else Decimal('0')
        )

    return ranking, total_general


@requiere_grupo('Rankings')
def retencion_inym_ranking_entidades(request):
    """Ranking de entidades retenidas según la suma de montos de sus
    retenciones INYM, de mayor a menor, filtrando opcionalmente por un
    rango de fecha (y excluyendo, si se pide, a Fontana)."""
    form, retenciones, filtros_activos = _retenciones_inym_ranking_filtrados(request)
    ranking, total_general = _calcular_ranking_retenciones_inym(retenciones)
    ranking = aplicar_orden_lista(request, ranking, {
        'posicion': lambda f: f['posicion'],
        'entidad': lambda f: (f['operador_retenido__entidad__nombre'] or '').lower(),
        'cantidad': lambda f: f['cantidad'],
        'monto': lambda f: f['total_monto'] if f['total_monto'] is not None else Decimal('0'),
        'porcentaje': lambda f: f['porcentaje'],
    })

    return render(request, 'retenciones_inym/retencion_inym_ranking_entidades.html', {
        'form': form,
        'ranking': ranking,
        'total_general': total_general,
        'filtros_activos': filtros_activos,
    })


def _filas_ranking_retenciones_inym(ranking):
    columnas = ['#', 'Entidad retenida', 'Retenciones', 'Monto total', 'Participación %']
    filas = [
        [
            fila['posicion'],
            fila['operador_retenido__entidad__nombre'] or 'Sin nombre',
            fila['cantidad'],
            float(fila['total_monto']) if fila['total_monto'] is not None else None,
            float(fila['porcentaje']) if fila['porcentaje'] is not None else None,
        ]
        for fila in ranking
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': {3, 4},  # Monto total, Participación %
        'anchos': [0.4, 2.2, 1.0, 1.2, 1.2],
    }


@requiere_grupo('Rankings')
def retencion_inym_ranking_entidades_excel(request):
    _form, retenciones, _filtros_activos = _retenciones_inym_ranking_filtrados(request)
    ranking, _total_general = _calcular_ranking_retenciones_inym(retenciones)
    resultado = _filas_ranking_retenciones_inym(ranking)
    return excel_response('ranking_entidades_retenciones_inym', resultado)


@requiere_grupo('Rankings')
def retencion_inym_ranking_entidades_pdf(request):
    _form, retenciones, _filtros_activos = _retenciones_inym_ranking_filtrados(request)
    ranking, _total_general = _calcular_ranking_retenciones_inym(retenciones)
    resultado = _filas_ranking_retenciones_inym(ranking)
    return pdf_response(
        'ranking_entidades_retenciones_inym', 'Ranking de entidades por monto de retenciones INYM', resultado
    )
