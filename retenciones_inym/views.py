from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from entidades.models import Inym_Operador
from services.ordenamiento import aplicar_orden_lista, aplicar_orden_queryset
from services.permisos import requiere_grupo
from services.reportes import excel_response, pdf_response

from .forms import (
    AnalisisKgsInymForm, ImportadorInymForm, ImportadorInymHistoricoForm,
    RankingEntidadesForm, RetencionInymForm, texto_operador_inym,
)
from .importador import ErrorImportacion, importar_filas, leer_filas_excel
from .importador_historico import importar_filas_historico
from .models import InymRetencionTipo, RetencionInym, RetencionInymHistorico


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
    diccionario a lo que espera RetencionInym.objects.create()/save().
    También saca los CharField "_nombre" del buscador de operador (sólo
    existen para la UI -- ver operador_emisor_nombre/operador_retenido_nombre
    en forms.py -- RetencionInym no tiene esos campos)."""
    datos = dict(cleaned_data)
    datos.pop('operador_emisor_nombre', None)
    datos.pop('operador_retenido_nombre', None)
    return datos


def operador_inym_buscar(request):
    """Devuelve, en JSON, hasta 20 operadores INYM (Inym_Operador) cuyo
    nombre de entidad o CUIT contengan el texto buscado, o cuyo id de
    operador coincida exactamente -- buscador para "Operador emisor"/
    "Operador retenido" del alta y modificación de Retención INYM (antes
    un <select> con todos los operadores cargados). Pedido de Gastón,
    24/09/2026; mismo patrón que entidades.views.entidad_buscar /
    retenciones.views.comprobante_buscar_para_retencion."""
    q = request.GET.get('q', '').strip()
    resultados = []
    if len(q) >= 2:
        filtro = Q(entidad__nombre__icontains=q) | Q(entidad__cuit__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))
        operadores = (
            Inym_Operador.objects.select_related('entidad', 'tipo_operador')
            .filter(filtro).order_by('entidad__nombre')[:20]
        )
        resultados = [{'id': op.id, 'text': texto_operador_inym(op)} for op in operadores]
    return JsonResponse({'resultados': resultados})


SUFIJO_EDITADO_POR_APP = ' (editado por app)'
MAX_LEN_AGREGADO_DESDE = 45  # RetencionInym.agregado_desde = CharField(max_length=45)


def _agregado_desde_tras_editar(valor_actual):
    """Pedido de Gastón (24/09/2026): "agregado_desde" no se puede editar a
    mano desde el form (no hay campo para eso), pero si la retención se
    modifica desde esta pantalla, queda marcada como editada por la app --
    sin perder el origen que ya tenía (a mano, Excel, etc.). Idempotente:
    si ya estaba marcada, no duplica el sufijo en ediciones sucesivas."""
    valor_actual = (valor_actual or '').strip()
    if not valor_actual:
        nuevo = 'editado por app'
    elif SUFIJO_EDITADO_POR_APP.strip() in valor_actual:
        return valor_actual
    else:
        nuevo = valor_actual + SUFIJO_EDITADO_POR_APP
    return nuevo[:MAX_LEN_AGREGADO_DESDE]


AGREGADO_DESDE_VACIO = '__vacio__'  # opción del filtro para "sin agregado_desde cargado" (datos viejos, de antes de que este campo se usara)


def _opciones_agregado_desde():
    """Valores de agregado_desde que realmente existen en la tabla (no una
    lista fija a mano) -- así el filtro sirve también para valores viejos
    que puedan quedar de antes de este app (o de una carga manual en la
    base). Ordenados alfabéticamente, sin duplicados."""
    return sorted(
        RetencionInym.objects.exclude(agregado_desde__isnull=True).exclude(agregado_desde='')
        .order_by().values_list('agregado_desde', flat=True).distinct()
    )


def _retencion_inym_listado_filtrado(request):
    """Arma el queryset filtrado de RetencionInym (SIN cortar) según los
    filtros de la pantalla de listado -- lo usan tanto la pantalla como los
    exports a Excel/PDF (con "todos los detalles"), para que exporten
    siempre lo mismo que se está viendo. Pedido de Gastón (24/09/2026):
    poder filtrar por "desde dónde fue agregada" (agregado_desde), tipo de
    tarifa, id y N° de certificado INYM, además de los filtros que ya había
    (fecha, operador retenido). La fecha pasó de ser un filtro exacto a un
    rango "desde/hasta" (mismo pedido, misma conversación), ambos extremos
    opcionales e independientes -- mismo criterio que
    ChequesRecibidosSinPagoFiltroForm en movimientos_caja."""
    q_fecha_desde = request.GET.get('fecha_desde', '').strip()
    q_fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    q_retenido = request.GET.get('retenido', '').strip()
    q_agregado_desde = request.GET.get('agregado_desde', '').strip()
    q_tipo_tarifa = request.GET.get('tipo_tarifa', '').strip()
    q_id = request.GET.get('id', '').strip()
    q_numero = request.GET.get('numero', '').strip()

    qs = RetencionInym.objects.select_related(
        'id_tipo_tarifa',
        'operador_emisor__entidad', 'operador_emisor__tipo_operador',
        'operador_retenido__entidad', 'operador_retenido__tipo_operador',
    )
    # Pedido de Gastón (24/09/2026): filtro de fecha "desde/hasta" en vez de
    # una fecha exacta -- mismo criterio que ChequesRecibidosSinPagoFiltroForm
    # (movimientos_caja), ambos extremos opcionales e independientes.
    if q_fecha_desde:
        qs = qs.filter(fecha__gte=q_fecha_desde)
    if q_fecha_hasta:
        qs = qs.filter(fecha__lte=q_fecha_hasta)
    if q_retenido:
        qs = qs.filter(operador_retenido__entidad__nombre__icontains=q_retenido)
    if q_agregado_desde == AGREGADO_DESDE_VACIO:
        qs = qs.filter(Q(agregado_desde__isnull=True) | Q(agregado_desde=''))
    elif q_agregado_desde:
        qs = qs.filter(agregado_desde=q_agregado_desde)
    if q_tipo_tarifa.isdigit():
        qs = qs.filter(id_tipo_tarifa_id=q_tipo_tarifa)
    if q_id.isdigit():
        qs = qs.filter(id=q_id)
    if q_numero.isdigit():
        qs = qs.filter(id_certificado_inym=q_numero)

    qs = qs.order_by('-fecha', '-id')
    qs = aplicar_orden_queryset(request, qs, {
        'fecha': 'fecha',
        'retenido': 'operador_retenido__entidad__nombre',
        'total': 'total',
    })
    return qs, {
        'fecha_desde': q_fecha_desde, 'fecha_hasta': q_fecha_hasta, 'retenido': q_retenido,
        'agregado_desde': q_agregado_desde, 'tipo_tarifa': q_tipo_tarifa, 'id': q_id, 'numero': q_numero,
    }


def retencion_inym_listado(request):
    qs, filtros = _retencion_inym_listado_filtrado(request)
    registros = list(qs[:500])

    return render(request, 'retenciones_inym/retencion_inym_listado.html', {
        'registros': registros,
        'q_fecha_desde': filtros['fecha_desde'], 'q_fecha_hasta': filtros['fecha_hasta'],
        'q_retenido': filtros['retenido'],
        'q_agregado_desde': filtros['agregado_desde'], 'q_tipo_tarifa': filtros['tipo_tarifa'],
        'q_id': filtros['id'], 'q_numero': filtros['numero'],
        'opciones_agregado_desde': _opciones_agregado_desde(),
        'opciones_tipo_tarifa': InymRetencionTipo.objects.all().order_by('nombre'),
        'AGREGADO_DESDE_VACIO': AGREGADO_DESDE_VACIO,
    })


def _filas_retencion_inym_listado(registros):
    """Columnas/filas para el export "con todos los detalles" (Excel/PDF)
    de la pantalla de listado -- pedido de Gastón (24/09/2026). Trae, además
    de lo que ya se ve en pantalla, el CUIT y tipo de operador de emisor y
    retenido, y de dónde se cargó cada retención (agregado_desde)."""
    columnas = [
        'Fecha', 'Período', 'Tipo de tarifa',
        'CUIT emisor', 'Emisor', 'Tipo oper. emisor',
        'CUIT retenido', 'Retenido', 'Tipo oper. retenido',
        'Kgs', 'Tarifa', 'Total', 'Eliminación (INYM)', 'N° cert. INYM', 'Agregado desde',
    ]
    filas = [
        [
            r.fecha, r.periodo, r.id_tipo_tarifa.nombre if r.id_tipo_tarifa_id else '',
            r.operador_emisor.entidad.cuit if r.operador_emisor_id else '',
            r.operador_emisor.entidad.nombre if r.operador_emisor_id else '',
            r.operador_emisor.tipo_operador.nombre if r.operador_emisor_id else '',
            r.operador_retenido.entidad.cuit if r.operador_retenido_id else '',
            r.operador_retenido.entidad.nombre if r.operador_retenido_id else '',
            r.operador_retenido.tipo_operador.nombre if r.operador_retenido_id else '',
            float(r.kgs) if r.kgs is not None else None,
            float(r.tarifa) if r.tarifa is not None else None,
            float(r.total) if r.total is not None else None,
            r.eliminacion, r.id_certificado_inym, r.agregado_desde or '',
        ]
        for r in registros
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        # Tarifa (índice 10) queda afuera a propósito: columnas_numericas
        # fuerza formato de 2 decimales (moneda, "#,##0.00" / separador de
        # miles), y la Tarifa puede tener hasta 6 (pedido de Gastón,
        # 24/09/2026 -- ver forms.py). Kgs y Total sí son montos/pesos de
        # toda la vida, siguen en 2 decimales.
        'columnas_numericas': {9, 11},  # Kgs, Total
        'anchos': [0.7, 0.7, 1.1, 1.0, 1.6, 1.0, 1.0, 1.6, 1.0, 0.7, 0.7, 0.9, 0.9, 0.8, 1.3],
    }


def retencion_inym_listado_excel(request):
    qs, _filtros = _retencion_inym_listado_filtrado(request)
    resultado = _filas_retencion_inym_listado(qs)
    return excel_response('retenciones_inym', resultado)


def retencion_inym_listado_pdf(request):
    qs, _filtros = _retencion_inym_listado_filtrado(request)
    resultado = _filas_retencion_inym_listado(qs)
    return pdf_response('retenciones_inym', 'Retenciones INYM', resultado)


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
        form = RetencionInymForm(request.POST, instance_id=registro.id)
        if form.is_valid():
            for campo, valor in _form_a_datos(form.cleaned_data).items():
                setattr(registro, campo, valor)
            registro.agregado_desde = _agregado_desde_tras_editar(registro.agregado_desde)
            registro.save()
            messages.success(request, 'La retención INYM se modificó correctamente.')
            return redirect('retenciones_inym:listado')
    else:
        form = RetencionInymForm(instance_id=registro.id, initial={
            'fecha': registro.fecha,
            'periodo': registro.periodo,
            'id_tipo_tarifa': registro.id_tipo_tarifa_id,
            'operador_emisor': registro.operador_emisor_id,
            'operador_emisor_nombre': texto_operador_inym(registro.operador_emisor) if registro.operador_emisor_id else '',
            'operador_retenido': registro.operador_retenido_id,
            'operador_retenido_nombre': texto_operador_inym(registro.operador_retenido) if registro.operador_retenido_id else '',
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


# ---------------------------------------------------------------------------
# Tabla histórica de análisis (RetencionInymHistorico) -- pedido de Gastón
# (24/09/2026): un import aparte (con fecha desde/hasta obligatoria, y sin
# contar retenciones eliminadas) para poder cargar de a poco todo el
# histórico de INYM sin tocar la tabla operativa `retencion_inym`, y armar
# con eso un análisis estadístico de kgs por año/mes/tipo de tarifa. Ver
# retenciones_inym/importador_historico.py y models.py::RetencionInymHistorico.
# ---------------------------------------------------------------------------

def retencion_inym_historico_importar(request):
    resultado = None

    if request.method == 'POST':
        form = ImportadorInymHistoricoForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']
            fecha_desde = form.cleaned_data['fecha_desde']
            fecha_hasta = form.cleaned_data['fecha_hasta']
            try:
                filas = leer_filas_excel(archivo, archivo.name)
                resultado = importar_filas_historico(filas, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
            except ErrorImportacion as exc:
                form.add_error('archivo', str(exc))
            else:
                messages.success(
                    request,
                    f"Se cargaron {resultado['importadas']} retenciones al histórico para el rango "
                    f"{fecha_desde:%d/%m/%Y} - {fecha_hasta:%d/%m/%Y} (se reemplazó lo que hubiera antes "
                    "en ese mismo rango).",
                )
                if resultado['eliminadas_excluidas']:
                    messages.info(
                        request,
                        f"No se contaron {resultado['eliminadas_excluidas']} retención(es) marcadas como "
                        "eliminadas en INYM.",
                    )
    else:
        form = ImportadorInymHistoricoForm()

    return render(request, 'retenciones_inym/retencion_inym_historico_importar.html', {
        'form': form, 'resultado': resultado,
    })


# ---------------------------------------------------------------------------
# Análisis Kgs INYM (histórico) -- pedido de Gastón (24/09/2026): kgs por
# operador y año, análisis de varianza (máximo/mínimo/variación % por
# operador) y análisis mensual (en qué mes se reciben más kgs de cada tipo
# de tarifa). Todo sobre RetencionInymHistorico, no sobre la tabla
# operativa. Qué operador (emisor/retenido) representa "quién
# entregó/recibió" todavía no está definido para todos los tipos de tarifa
# (confirmado sólo para "Hoja verde" = operador retenido), así que la
# pantalla deja elegirlo con AnalisisKgsInymForm.rol_operador en vez de
# asumir uno fijo.
# ---------------------------------------------------------------------------

MESES_NOMBRE = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]


def _tipo_tarifa_por_defecto():
    """"Hoja verde" es el valor por defecto del filtro de tipo de tarifa de
    Análisis Kgs INYM -- se busca por NOMBRE (no por id): el id de cada
    tipo de tarifa lo asigna INYM, no es una constante fija de este
    sistema. None si el catálogo está vacío o todavía no tiene ese nombre
    cargado (el form queda sin default y exige elegir uno a mano)."""
    return (
        InymRetencionTipo.objects.filter(nombre__iexact='Hoja verde').order_by('id').first()
        or InymRetencionTipo.objects.filter(nombre__icontains='hoja verde').order_by('id').first()
    )


def _historico_filtrado(request):
    """Aplica los filtros de AnalisisKgsInymForm sobre RetencionInymHistorico:
    fecha desde/hasta (opcionales) y tipo de tarifa (OBLIGATORIO, por
    defecto "Hoja verde" -- pedido de Gastón, 24/09/2026: "que no me
    permita mezclar los kgs de distintas tarifas"). Devuelve (form,
    queryset, rol_operador, tipo_tarifa) -- centralizado para que la
    pantalla y las 8 exportaciones (Excel/PDF x 4 secciones) usen siempre
    el mismo criterio.

    El default se inyecta en los datos ANTES de bindear el form (no se usa
    'initial', que sólo se ve en un form sin bindear) -- así en la primera
    visita, sin ningún parámetro en la URL, ya queda filtrado por Hoja
    verde en vez de mostrar un error de "campo obligatorio" o mezclar
    todo. Si no hay ningún tipo de tarifa válido elegido (catálogo vacío),
    el queryset queda vacío -- nunca se devuelven datos de varias tarifas
    mezcladas."""
    datos = request.GET.copy()
    if not datos.get('id_tipo_tarifa'):
        tipo_por_defecto = _tipo_tarifa_por_defecto()
        if tipo_por_defecto:
            datos['id_tipo_tarifa'] = str(tipo_por_defecto.id)

    form = AnalisisKgsInymForm(datos)
    qs = RetencionInymHistorico.objects.none()
    rol_operador = 'retenido'
    tipo_tarifa = None
    if form.is_valid():
        fecha_desde = form.cleaned_data.get('fecha_desde')
        fecha_hasta = form.cleaned_data.get('fecha_hasta')
        rol_operador = form.cleaned_data.get('rol_operador') or 'retenido'
        tipo_tarifa = form.cleaned_data['id_tipo_tarifa']
        qs = RetencionInymHistorico.objects.filter(id_tipo_tarifa=tipo_tarifa)
        if fecha_desde:
            qs = qs.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha__lte=fecha_hasta)
    return form, qs, rol_operador, tipo_tarifa


def _campo_operador(rol_operador):
    return 'operador_emisor' if rol_operador == 'emisor' else 'operador_retenido'


def _pivot_operador_anio(qs, rol_operador):
    """Devuelve (filas_pivot, anios): filas_pivot es una lista de dicts
    {'id', 'nombre', 'valores': {año: kgs}}, uno por operador (según
    rol_operador), ordenados por nombre; anios es la lista ordenada de
    años que aparecen en los datos."""
    campo = _campo_operador(rol_operador)
    registros = (
        qs.filter(**{f'{campo}__isnull': False})
        .annotate(anio=ExtractYear('fecha'))
        .values('anio', f'{campo}_id', f'{campo}__entidad__nombre', f'{campo}__tipo_operador__nombre')
        .annotate(kgs_total=Sum('kgs'))
    )

    operadores = {}
    anios = set()
    for r in registros:
        anios.add(r['anio'])
        op_id = r[f'{campo}_id']
        if op_id not in operadores:
            operadores[op_id] = {
                'id': op_id,
                'nombre': f"{r[f'{campo}__entidad__nombre']} ({r[f'{campo}__tipo_operador__nombre']})",
                'valores': {},
            }
        operadores[op_id]['valores'][r['anio']] = r['kgs_total']

    anios_ordenados = sorted(anios)
    filas_pivot = sorted(operadores.values(), key=lambda o: o['nombre'].lower())
    return filas_pivot, anios_ordenados


def _analisis_varianza(filas_pivot, anios):
    """Para cada operador de filas_pivot: año/kgs máximo, año/kgs mínimo,
    variación % entre ambos, y la variación % interanual (año a año)."""
    resultado = []
    for op in filas_pivot:
        valores = [(anio, op['valores'][anio]) for anio in anios if op['valores'].get(anio) is not None]
        if not valores:
            continue
        anio_max, kgs_max = max(valores, key=lambda t: t[1])
        anio_min, kgs_min = min(valores, key=lambda t: t[1])
        variacion_max_min_pct = (
            (kgs_max - kgs_min) / kgs_min * 100 if kgs_min else None
        )
        variacion_interanual = []
        for i in range(1, len(valores)):
            anio_prev, kgs_prev = valores[i - 1]
            anio_act, kgs_act = valores[i]
            pct = (kgs_act - kgs_prev) / kgs_prev * 100 if kgs_prev else None
            variacion_interanual.append({'anio': anio_act, 'pct': pct})
        resultado.append({
            'operador': op['nombre'], 'operador_id': op['id'],
            'anio_max': anio_max, 'kgs_max': kgs_max,
            'anio_min': anio_min, 'kgs_min': kgs_min,
            'variacion_max_min_pct': variacion_max_min_pct,
            'variacion_interanual': variacion_interanual,
        })
    return resultado


def _pivot_tipo_tarifa_mes(qs):
    """Devuelve una lista de dicts {'id', 'nombre', 'valores': {mes: kgs},
    'mes_max', 'kgs_mes_max'}, uno por tipo de tarifa -- kgs totales (de
    todos los años juntos) por mes, para ver en qué mes se recibe más de
    cada tipo. 'mes' es 1-12."""
    registros = (
        qs.filter(id_tipo_tarifa__isnull=False)
        .annotate(mes=ExtractMonth('fecha'))
        .values('id_tipo_tarifa_id', 'id_tipo_tarifa__nombre', 'mes')
        .annotate(kgs_total=Sum('kgs'))
    )

    tipos = {}
    for r in registros:
        tid = r['id_tipo_tarifa_id']
        if tid not in tipos:
            tipos[tid] = {'id': tid, 'nombre': r['id_tipo_tarifa__nombre'] or f'Tipo {tid}', 'valores': {}}
        tipos[tid]['valores'][r['mes']] = r['kgs_total']

    filas_pivot = sorted(tipos.values(), key=lambda t: (t['nombre'] or '').lower())
    for t in filas_pivot:
        if t['valores']:
            mes_max = max(t['valores'], key=lambda m: t['valores'][m])
            t['mes_max'] = mes_max
            t['kgs_mes_max'] = t['valores'][mes_max]
        else:
            t['mes_max'] = None
            t['kgs_mes_max'] = None
    return filas_pivot


def _totales_por_anio(filas_pivot, anios):
    """Suma de kgs de todos los operadores, por año -- fila "Total" al pie
    de la tabla de Kgs por operador y año (pantalla y export). Pedido de
    Gastón, 24/09/2026."""
    return [
        sum((op['valores'].get(a) or 0 for op in filas_pivot), Decimal('0'))
        for a in anios
    ]


def _total_operador(op, anios):
    """Suma de kgs de UN operador, de todos los años juntos -- columna
    "Total" al final de cada fila. Pedido de Gastón, 24/09/2026."""
    return sum((op['valores'].get(a) or 0 for a in anios), Decimal('0'))


def _incidencia_pct(valor, total):
    """% que representa 'valor' sobre 'total' -- None si no hay dato o el
    total es 0 (para no dividir por cero)."""
    if valor is None or not total:
        return None
    return valor / total * 100


def _tabla_incidencia(filas_pivot, anios, totales_por_anio, total_general):
    """Para cada operador: % que representó sobre el total de CADA año, y %
    que representa su total sobre el total general (todos los años juntos).
    Pedido de Gastón, 24/09/2026 -- pantalla y export separados de la tabla
    de Kgs (misma info, en porcentaje en vez de kilos)."""
    filas = []
    for op in filas_pivot:
        valores_pct = [
            _incidencia_pct(op['valores'].get(a), totales_por_anio[i])
            for i, a in enumerate(anios)
        ]
        total_pct = _incidencia_pct(_total_operador(op, anios), total_general)
        filas.append({'nombre': op['nombre'], 'valores': valores_pct, 'total_pct': total_pct})
    return filas


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs(request):
    form, qs, rol_operador, tipo_tarifa = _historico_filtrado(request)
    filas_pivot, anios = _pivot_operador_anio(qs, rol_operador)
    varianza = _analisis_varianza(filas_pivot, anios)
    mensual = _pivot_tipo_tarifa_mes(qs)

    totales_por_anio = _totales_por_anio(filas_pivot, anios)
    total_general = sum(totales_por_anio, Decimal('0'))

    # El template no puede indexar un dict con una variable de loop --
    # se arman acá listas ya ordenadas (mismo orden que 'anios'/1..12) para
    # poder iterarlas en paralelo con un solo {% for %} por fila.
    filas_tabla = [
        {
            'nombre': op['nombre'],
            'valores': [op['valores'].get(a) for a in anios],
            'total': _total_operador(op, anios),
        }
        for op in filas_pivot
    ]
    incidencia_tabla = _tabla_incidencia(filas_pivot, anios, totales_por_anio, total_general)
    mensual_tabla = [
        {
            'nombre': t['nombre'],
            'valores': [t['valores'].get(m) for m in range(1, 13)],
            'mes_max_nombre': MESES_NOMBRE[t['mes_max']] if t['mes_max'] else '',
            'kgs_mes_max': t['kgs_mes_max'],
        }
        for t in mensual
    ]

    return render(request, 'retenciones_inym/retencion_inym_analisis_kgs.html', {
        'form': form,
        'rol_operador': rol_operador,
        'tipo_tarifa': tipo_tarifa,
        'anios': anios,
        'filas_tabla': filas_tabla,
        'totales_por_anio': totales_por_anio,
        'total_general': total_general,
        'incidencia_tabla': incidencia_tabla,
        'varianza': varianza,
        'mensual_tabla': mensual_tabla,
        'meses_nombre_cortos': ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
        'hay_datos': qs.exists(),
    })


def _filas_analisis_kgs_operadores(filas_pivot, anios):
    columnas = ['Operador'] + [str(a) for a in anios] + ['Total']
    filas = [
        [op['nombre']] + [
            float(op['valores'][a]) if op['valores'].get(a) is not None else None
            for a in anios
        ] + [float(_total_operador(op, anios))]
        for op in filas_pivot
    ]
    # Fila "Total" al pie -- pedido de Gastón (24/09/2026), mismo total que
    # ya se mostraba en pantalla (tfoot de la tabla); la última celda (abajo
    # a la derecha) es el total general.
    if filas_pivot:
        totales = _totales_por_anio(filas_pivot, anios)
        total_general = sum(totales, Decimal('0'))
        filas.append(['Total'] + [float(t) for t in totales] + [float(total_general)])
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': set(range(1, len(anios) + 2)),
        'anchos': [2.2] + [0.8] * len(anios) + [0.9],
    }


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs_operadores_excel(request):
    _form, qs, rol_operador, _tipo_tarifa = _historico_filtrado(request)
    filas_pivot, anios = _pivot_operador_anio(qs, rol_operador)
    resultado = _filas_analisis_kgs_operadores(filas_pivot, anios)
    return excel_response('analisis_kgs_inym_operadores', resultado)


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs_operadores_pdf(request):
    _form, qs, rol_operador, _tipo_tarifa = _historico_filtrado(request)
    filas_pivot, anios = _pivot_operador_anio(qs, rol_operador)
    resultado = _filas_analisis_kgs_operadores(filas_pivot, anios)
    return pdf_response('analisis_kgs_inym_operadores', 'Kgs INYM por operador y año', resultado)


def _filas_analisis_kgs_incidencia(filas_pivot, anios):
    totales_por_anio = _totales_por_anio(filas_pivot, anios)
    total_general = sum(totales_por_anio, Decimal('0'))
    incidencia = _tabla_incidencia(filas_pivot, anios, totales_por_anio, total_general)

    columnas = ['Operador'] + [f'{a} (%)' for a in anios] + ['Incidencia total (%)']
    filas = [
        [fila['nombre']] + [
            float(v) if v is not None else None for v in fila['valores']
        ] + [float(fila['total_pct']) if fila['total_pct'] is not None else None]
        for fila in incidencia
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': set(range(1, len(anios) + 2)),
        'anchos': [2.2] + [0.8] * len(anios) + [1.1],
    }


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs_incidencia_excel(request):
    _form, qs, rol_operador, _tipo_tarifa = _historico_filtrado(request)
    filas_pivot, anios = _pivot_operador_anio(qs, rol_operador)
    resultado = _filas_analisis_kgs_incidencia(filas_pivot, anios)
    return excel_response('analisis_kgs_inym_incidencia', resultado)


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs_incidencia_pdf(request):
    _form, qs, rol_operador, _tipo_tarifa = _historico_filtrado(request)
    filas_pivot, anios = _pivot_operador_anio(qs, rol_operador)
    resultado = _filas_analisis_kgs_incidencia(filas_pivot, anios)
    return pdf_response('analisis_kgs_inym_incidencia', 'Incidencia % de kgs INYM por operador y año', resultado)


def _filas_analisis_kgs_varianza(varianza):
    columnas = ['Operador', 'Año máximo', 'Kgs (máximo)', 'Año mínimo', 'Kgs (mínimo)', 'Variación % (máx. vs mín.)']
    filas = [
        [
            v['operador'], v['anio_max'], float(v['kgs_max']), v['anio_min'], float(v['kgs_min']),
            float(v['variacion_max_min_pct']) if v['variacion_max_min_pct'] is not None else None,
        ]
        for v in varianza
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': {2, 4, 5},
        'anchos': [2.2, 1.0, 1.0, 1.0, 1.0, 1.3],
    }


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs_varianza_excel(request):
    _form, qs, rol_operador, _tipo_tarifa = _historico_filtrado(request)
    filas_pivot, anios = _pivot_operador_anio(qs, rol_operador)
    varianza = _analisis_varianza(filas_pivot, anios)
    resultado = _filas_analisis_kgs_varianza(varianza)
    return excel_response('analisis_kgs_inym_varianza', resultado)


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs_varianza_pdf(request):
    _form, qs, rol_operador, _tipo_tarifa = _historico_filtrado(request)
    filas_pivot, anios = _pivot_operador_anio(qs, rol_operador)
    varianza = _analisis_varianza(filas_pivot, anios)
    resultado = _filas_analisis_kgs_varianza(varianza)
    return pdf_response('analisis_kgs_inym_varianza', 'Análisis de varianza por año -- Kgs INYM por operador', resultado)


def _filas_analisis_kgs_mensual(mensual):
    columnas = ['Tipo de tarifa'] + MESES_NOMBRE[1:] + ['Mes con más kgs']
    filas = [
        [t['nombre']] + [
            float(t['valores'][m]) if t['valores'].get(m) is not None else None
            for m in range(1, 13)
        ] + [MESES_NOMBRE[t['mes_max']] if t['mes_max'] else '']
        for t in mensual
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': set(range(1, 13)),
        'anchos': [1.8] + [0.7] * 12 + [1.1],
    }


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs_mensual_excel(request):
    _form, qs, _rol_operador, _tipo_tarifa = _historico_filtrado(request)
    mensual = _pivot_tipo_tarifa_mes(qs)
    resultado = _filas_analisis_kgs_mensual(mensual)
    return excel_response('analisis_kgs_inym_mensual', resultado)


@requiere_grupo('Rankings')
def retencion_inym_analisis_kgs_mensual_pdf(request):
    _form, qs, _rol_operador, _tipo_tarifa = _historico_filtrado(request)
    mensual = _pivot_tipo_tarifa_mes(qs)
    resultado = _filas_analisis_kgs_mensual(mensual)
    return pdf_response('analisis_kgs_inym_mensual', 'Kgs INYM por mes y tipo de tarifa', resultado)
