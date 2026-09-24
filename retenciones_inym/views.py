from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Max, Sum
from django.shortcuts import render, redirect, get_object_or_404

from services.ordenamiento import aplicar_orden_lista, aplicar_orden_queryset
from services.permisos import requiere_grupo
from services.reportes import excel_response, pdf_response

from .forms import ImportadorInymForm, RankingEntidadesForm, RetencionInymForm
from .importador import ErrorImportacion, importar_filas, leer_filas_excel
from .models import RetencionInym


# ---------------------------------------------------------------------------
# Alta / Modificación / Eliminación / Listado de un registro de Retención
# INYM. A diferencia de `retenciones` (agrupado por año+número), acá cada
# fila de `retencion_inym` es un registro completo en sí mismo.
# ---------------------------------------------------------------------------

def _siguiente_id_retencion_inym():
    """La tabla 'retencion_inym' no tiene AUTO_INCREMENT en 'id', así que el
    próximo id se calcula a mano, mismo patrón que
    retenciones.views._siguiente_id_retencion."""
    ultimo = RetencionInym.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


def _tiene_liquidacion_inym(retencion_inym_id):
    """True si esta retención INYM ya está incluida en una Liquidación
    (tabla `liquidacion_retencion_inym`) -- mismo criterio que
    retenciones.views._tiene_liquidacion, para no dejar modificar/eliminar
    un registro que una Liquidación ya está usando."""
    from liquidaciones.models import LiquidacionRetencionInym
    return LiquidacionRetencionInym.objects.filter(retencion_inym_id=retencion_inym_id).exists()


def _form_a_datos(cleaned_data):
    """Los ModelChoiceField del form devuelven instancias -- achica el
    diccionario a lo que espera RetencionInym.objects.create()/save()."""
    return dict(cleaned_data)


def retencion_inym_listado(request):
    q_fecha = request.GET.get('fecha', '').strip()
    q_retenido = request.GET.get('retenido', '').strip()

    qs = RetencionInym.objects.select_related(
        'id_tipo_tarifa', 'operador_emisor__entidad', 'operador_retenido__entidad',
    )
    if q_fecha:
        qs = qs.filter(fecha=q_fecha)
    if q_retenido:
        qs = qs.filter(operador_retenido__entidad__nombre__icontains=q_retenido)

    qs = qs.order_by('-fecha', '-id')
    qs = aplicar_orden_queryset(request, qs, {
        'fecha': 'fecha',
        'retenido': 'operador_retenido__entidad__nombre',
        'total': 'total',
    })
    registros = list(qs[:500])

    return render(request, 'retenciones_inym/retencion_inym_listado.html', {
        'registros': registros, 'q_fecha': q_fecha, 'q_retenido': q_retenido,
    })


def retencion_inym_alta(request):
    if request.method == 'POST':
        form = RetencionInymForm(request.POST)
        if form.is_valid():
            nuevo_id = _siguiente_id_retencion_inym()
            RetencionInym.objects.create(
                id=nuevo_id, agregado_desde='retenciones_inym_app',
                **_form_a_datos(form.cleaned_data),
            )
            messages.success(request, 'La retención INYM se guardó correctamente.')
            return redirect('retenciones_inym:listado')
    else:
        form = RetencionInymForm()

    return render(request, 'retenciones_inym/retencion_inym_form.html', {'form': form, 'modo': 'alta'})


def retencion_inym_modificar(request, pk):
    registro = get_object_or_404(RetencionInym, pk=pk)

    if _tiene_liquidacion_inym(registro.id):
        messages.error(
            request,
            f'La retención INYM {registro.id} ya está incluida en una liquidación y no se '
            'puede modificar desde acá.',
        )
        return redirect('retenciones_inym:listado')

    if request.method == 'POST':
        form = RetencionInymForm(request.POST)
        if form.is_valid():
            for campo, valor in _form_a_datos(form.cleaned_data).items():
                setattr(registro, campo, valor)
            registro.save()
            messages.success(request, 'La retención INYM se modificó correctamente.')
            return redirect('retenciones_inym:listado')
    else:
        form = RetencionInymForm(initial={
            'fecha': registro.fecha,
            'periodo': registro.periodo,
            'id_tipo_tarifa': registro.id_tipo_tarifa_id,
            'operador_emisor': registro.operador_emisor_id,
            'operador_retenido': registro.operador_retenido_id,
            'kgs': registro.kgs,
            'tarifa': registro.tarifa,
            'total': registro.total,
            'eliminacion': registro.eliminacion,
            'id_certificado_inym': registro.id_certificado_inym,
        })

    return render(request, 'retenciones_inym/retencion_inym_form.html', {
        'form': form, 'modo': 'modificar', 'registro': registro,
    })


def retencion_inym_eliminar(request, pk):
    registro = get_object_or_404(RetencionInym, pk=pk)

    if request.method == 'POST':
        if _tiene_liquidacion_inym(registro.id):
            messages.error(
                request,
                f'La retención INYM {registro.id} ya está incluida en una liquidación y no se '
                'puede eliminar desde acá.',
            )
            return redirect('retenciones_inym:listado')
        registro.delete()
        messages.success(request, f'La retención INYM {registro.id} se eliminó correctamente.')
        return redirect('retenciones_inym:listado')

    return render(request, 'retenciones_inym/retencion_inym_eliminar_confirm.html', {'registro': registro})


# ---------------------------------------------------------------------------
# Importador del Excel de INYM ("Listado Comprobantes de Retención") -- ver
# retenciones_inym/importador.py para el detalle de cómo se lee el archivo,
# cómo se arma la clave de no-duplicado y qué hace cuando un operador del
# Excel todavía no existe en el sistema.
# ---------------------------------------------------------------------------

def retencion_inym_importar(request):
    resultado = None

    if request.method == 'POST':
        form = ImportadorInymForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']
            try:
                filas = leer_filas_excel(archivo, archivo.name)
                resultado = importar_filas(
                    filas,
                    fecha_desde=form.cleaned_data.get('fecha_desde'),
                    fecha_hasta=form.cleaned_data.get('fecha_hasta'),
                )
            except ErrorImportacion as exc:
                form.add_error('archivo', str(exc))
            else:
                if resultado['importadas']:
                    messages.success(
                        request,
                        f"Se importaron {resultado['importadas']} retenciones INYM nuevas.",
                    )
                else:
                    messages.info(request, 'No se importó ninguna retención nueva (revisá el detalle abajo).')
                if resultado['modificadas']:
                    messages.info(
                        request,
                        f"Se completaron datos que faltaban en {resultado['modificadas']} retención(es) "
                        "que ya estaban cargadas a mano.",
                    )
                if resultado['con_diferencias']:
                    messages.warning(
                        request,
                        f"Se encontraron diferencias en {resultado['con_diferencias']} retención(es) que ya "
                        "tenían datos cargados -- no se modificaron, revisá el detalle abajo (y el Excel/PDF).",
                    )
                # Se guarda en la sesión para que los botones de descarga
                # (Excel/PDF, ver más abajo) funcionen con un GET aparte,
                # sin tener que volver a subir el archivo ni recalcular nada.
                if resultado['diferencias']:
                    request.session['inym_import_diferencias'] = resultado['diferencias']
                else:
                    request.session.pop('inym_import_diferencias', None)
    else:
        form = ImportadorInymForm()

    return render(request, 'retenciones_inym/retencion_inym_importar.html', {
        'form': form, 'resultado': resultado,
    })


def _filas_diferencias_import_inym(diferencias):
    columnas = ['Retención', 'Certificado INYM', 'Tipo de tarifa', 'Receptor', 'Campo', 'Valor guardado', 'Valor del Excel']
    filas = [
        [
            d['id'], d['id_certificado'], d['tipo_tarifa'], d['receptor'],
            d['campo'], d['valor_guardado'], d['valor_excel'],
        ]
        for d in diferencias
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'anchos': [0.6, 0.9, 1.2, 1.8, 1.0, 1.3, 1.3],
    }


def retencion_inym_importar_diferencias_excel(request):
    diferencias = request.session.get('inym_import_diferencias') or []
    resultado = _filas_diferencias_import_inym(diferencias)
    return excel_response('diferencias_import_inym', resultado)


def retencion_inym_importar_diferencias_pdf(request):
    diferencias = request.session.get('inym_import_diferencias') or []
    resultado = _filas_diferencias_import_inym(diferencias)
    return pdf_response(
        'diferencias_import_inym',
        'Diferencias encontradas al importar Excel INYM (no aplicadas)',
        resultado,
    )


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
