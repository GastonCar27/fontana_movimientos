from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from comprobantes.models import (
    IDS_UNIDADES_SOLO_REMITOS,
    ComprobanteRenglon,
    ComprobanteUnidadDeMedida,
)
from entidades.models import Entidad
from movimientos.models import Movimiento
from productos.models import ProductoDetalle
from services.ordenamiento import aplicar_orden_lista, aplicar_orden_queryset
from services.reportes import excel_response, pdf_response

from .models import (
    ComprobanteRenglonMovimiento,
    EstadoCuentaMovimiento,
    LiquidacionProducto,
    LiquidacionProductoComprobanteRenglon,
)


# Kilogramos, precarga por defecto en "Vincular por bloques" -- es la
# unidad ampliamente predominante en los movimientos de este negocio (ver
# el mismo id/criterio en fontana_escritorio/movimientos/repository.py).
UNIDAD_MEDIDA_KILOGRAMOS_ID = '01'

# Id de la entidad "Fontana S.A." (la empresa propia) -- mismo criterio que
# comprobantes.views.ENTIDAD_PROPIA_ID / remitos.models.ENTIDAD_PROPIA_ID.
# Se usa solo en "Pendientes por producto" para saber, dado un Movimiento,
# cuál de sus dos entidades (emisor/receptor) es la "contraparte" real
# (proveedor/cliente) a la hora de agrupar por entidad -- el otro lado
# siempre es la propia empresa en el uso normal del sistema.
ENTIDAD_PROPIA_ID = getattr(settings, 'ENTIDAD_PROPIA_ID', 100)


# ---------------------------------------------------------------------------
# Helpers: cuánto Kg (u otra unidad) de un Movimiento sigue sin cubrir por
# ningún ComprobanteRenglonMovimiento, y cuánto de la cantidad facturada en
# un ComprobanteRenglon todavía no se usó para cubrir movimientos.
#
# Se agregaron porque, antes de sumar ComprobanteRenglonMovimiento.cantidad_kg,
# un Movimiento con CUALQUIER vínculo se consideraba 100% cubierto sin
# importar cuánto facturara realmente el renglón vinculado -- si alguien
# vinculaba varios movimientos de una vez a un renglón que facturaba menos
# Kg que la suma de esos movimientos, la diferencia dejaba de aparecer como
# pendiente en cualquier pantalla (caso real: entidad Bukay Olivia Eugenia).
# ---------------------------------------------------------------------------

def _kg_pendiente_movimiento(movimiento, vinculos=None):
    """
    Kg de Movimiento.total que ningún vínculo cubrió todavía. Un vínculo
    viejo con cantidad_kg=null (de antes de agregar ese campo) se
    interpreta como "cubre el movimiento completo" -- mismo comportamiento
    que había antes de este cambio -- así que alcanza con que exista UNO
    así para dar 0 de pendiente.
    """
    if vinculos is None:
        vinculos = list(movimiento.vinculos_comprobante.all())
    total = movimiento.total or Decimal('0')
    if not vinculos:
        return total
    if any(v.cantidad_kg is None for v in vinculos):
        return Decimal('0')
    cubierto = sum((v.cantidad_kg for v in vinculos), Decimal('0'))
    pendiente = total - cubierto
    return pendiente if pendiente > 0 else Decimal('0')


def _kg_disponible_renglon(renglon, vinculos=None):
    """
    Cuánto de ComprobanteRenglonDetalle.cantidad (la cantidad facturada en
    el renglón) todavía no se usó para cubrir movimientos. Si el renglón no
    tiene esa fila/cantidad cargada, no hay con qué comparar y se devuelve
    None (se interpreta como "disponible" solo si todavía no tiene ningún
    vínculo, igual que el comportamiento previo a este cambio).
    """
    detalle = getattr(renglon, 'renglon_detalle_comprobante', None)
    capacidad = detalle.cantidad if detalle and detalle.cantidad is not None else None
    if capacidad is None:
        return None
    if vinculos is None:
        vinculos = list(renglon.vinculos_movimiento.all())
    if not vinculos:
        return capacidad
    if any(v.cantidad_kg is None for v in vinculos):
        return Decimal('0')
    usado = sum((v.cantidad_kg for v in vinculos), Decimal('0'))
    disponible = capacidad - usado
    return disponible if disponible > 0 else Decimal('0')


# Tope de movimientos que puede combinar la búsqueda automática de
# "candidato de vínculo" (ver _buscar_combinacion_exacta_kg) y tope de
# ramas explorado por cada renglón -- son límites para que la búsqueda no
# cuelgue la página cuando el filtro trae muchos movimientos/renglones; no
# encontrar nada dentro de esos límites no significa que no exista ninguna
# combinación posible, solo que no se la buscó exhaustivamente.
CANDIDATO_MAX_MOVIMIENTOS_COMBINADOS = 5
CANDIDATO_MAX_NODOS_POR_RENGLON = 4000
CANDIDATO_MAX_RENGLONES_A_BUSCAR = 150

# Para no hacer la búsqueda tan compleja/lenta (recorrer TODO el
# historial contra TODOS los movimientos cada vez), arranca por el primer
# comprobante del año que se indica acá en adelante (los más viejos
# primero) y, para cada uno, solo prueba movimientos con fecha entre unos
# meses antes y unos días después de la fecha de ESE comprobante -- no
# contra todos los movimientos del filtro. Ajustar estos valores si hace
# falta correrla sobre otro período.
CANDIDATO_ANIO_DESDE = 2026
CANDIDATO_DIAS_ANTES_COMPROBANTE = 90  # "unos meses antes"
CANDIDATO_DIAS_DESPUES_COMPROBANTE = 10


def _buscar_combinacion_exacta_kg(valores, objetivo_centavos,
                                   max_items=CANDIDATO_MAX_MOVIMIENTOS_COMBINADOS,
                                   max_nodos=CANDIDATO_MAX_NODOS_POR_RENGLON):
    """
    Busca, entre `valores` (lista de tuplas (id_movimiento, monto_en_centavos)
    YA ORDENADA ascendente por monto), la primera combinación de 1 a
    `max_items` elementos cuya suma da EXACTO `objetivo_centavos`. Se
    trabaja en centavos (enteros) para comparar montos exactos sin
    arrastrar errores de punto flotante.

    Devuelve la lista de id_movimiento elegidos, o None si no encontró
    ninguna combinación dentro de los límites de búsqueda.
    """
    n = len(valores)
    estado = {'nodos': 0, 'resultado': None}

    def backtrack(desde, restante, actual):
        if restante == 0 and actual:
            estado['resultado'] = list(actual)
            return True
        if len(actual) >= max_items or restante <= 0:
            return False
        estado['nodos'] += 1
        if estado['nodos'] > max_nodos:
            return False
        for i in range(desde, n):
            monto = valores[i][1]
            if monto > restante:
                break  # ascendente: los siguientes son todos más grandes todavía
            actual.append(valores[i][0])
            if backtrack(i + 1, restante - monto, actual):
                return True
            actual.pop()
        return False

    backtrack(0, objetivo_centavos, [])
    return estado['resultado']


def _buscar_combinacion_por_prefijo_kg(valores_por_fecha, objetivo_centavos):
    """
    Segunda estrategia para el candidato automático, pensada para cuando
    hacen falta MUCHOS movimientos para llegar a la cantidad del
    comprobante (caso real: entidad Katz Diego Gabriel, donde
    _buscar_combinacion_exacta_kg no llegaba a encontrarlos porque son más
    de CANDIDATO_MAX_MOVIMIENTOS_COMBINADOS o porque se quedaba sin ramas
    para probar). En vez de probar combinaciones, suma los movimientos EN
    ORDEN DE FECHA (más antiguo primero -- mismo criterio FIFO que se usa
    para repartir Kg al vincular) y corta apenas la suma llega o supera el
    objetivo: si en ese momento dio EXACTO, son candidatos; si se pasó sin
    pasar nunca por el valor exacto, no hay candidato por acá.

    No es exhaustiva (no prueba saltear movimientos sueltos en el medio),
    pero no tiene límite de cantidad de movimientos y es muchísimo más
    rápida -- cubre el caso típico de un comprobante que corresponde a una
    tanda de movimientos seguidos en el tiempo, que es la gran mayoría.

    `valores_por_fecha`: lista de (id_movimiento, monto_en_centavos) YA
    ORDENADA por fecha del movimiento (más antiguo primero). Devuelve la
    lista de id_movimiento elegidos, o None si no encontró.
    """
    acumulado = 0
    elegidos = []
    for id_movimiento, monto in valores_por_fecha:
        acumulado += monto
        elegidos.append(id_movimiento)
        if acumulado >= objetivo_centavos:
            break
    return elegidos if acumulado == objetivo_centavos else None


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

    # Solo para precargar el texto del buscador con el nombre ya elegido
    # (ver entidades:entidad_buscar / productos:buscar); .first() y no
    # get_object_or_404 porque un id inválido en la URL de un listado no
    # debería tirar un error 404, solo no precargar nada.
    entidad_obj = Entidad.objects.filter(pk=q_entidad).first() if q_entidad.isdigit() else None
    producto_obj = ProductoDetalle.objects.filter(pk=q_producto).first() if q_producto.isdigit() else None

    return render(request, 'cuenta_corriente_productos/movimientos_abiertos.html', {
        'movimientos': list(movimientos[:500]),
        'entidad_obj': entidad_obj,
        'producto_obj': producto_obj,
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
# Vincular por bloques: elegir varios movimientos sin vincular y vincularlos
# todos juntos a UN renglón de comprobante sin vincular, por vez.
# ---------------------------------------------------------------------------

def vincular_por_bloques(request):
    """
    Pantalla para vincular movimientos (kg) con renglones de comprobante
    "en bloque".

    Lado movimientos: entidad + producto + unidad de medida, los tres
    obligatorios. Lado renglones de comprobante: producto + unidad de
    medida, obligatorios también, con producto, unidad y fechas
    precargados por defecto con los mismos elegidos del lado de
    movimientos (editable igual, cada campo por separado). La fecha
    desde/hasta es opcional en los dos lados: acota el listado si se
    completa, pero no hace falta para que aparezcan los resultados ni el
    botón de vincular. La entidad es la misma en ambos lados: del lado de
    los renglones se usa como Comprobante.entidad_emisor.

    Con los filtros completos se listan los Movimiento que todavía tienen
    Kg pendientes de vincular (ver _kg_pendiente_movimiento) y los
    ComprobanteRenglon que todavía tienen capacidad libre (ver
    _kg_disponible_renglon) que cumplan cada filtro -- "pendiente" ya NO es
    simplemente "sin ningún vínculo": un movimiento puede seguir teniendo
    Kg pendientes aunque ya tenga algún vínculo, si el/los renglón(es)
    vinculados no llegaban a cubrirlo del todo. Desde ahí se pueden tildar
    varios movimientos y elegir un solo renglón para vincularlos todos
    juntos a ese renglón en un solo POST. Si la cantidad facturada en el
    renglón no alcanza para cubrir todo lo tildado, se cubre lo que entra
    (los movimientos más antiguos primero) y el resto queda pendiente para
    vincularlo después con otro comprobante -- no se pierde ni se marca
    como cubierto de más (bug real detectado con la entidad Bukay Olivia
    Eugenia: un renglón cubría menos Kg que los movimientos vinculados de
    una vez, y esos Kg de diferencia dejaban de aparecer como pendientes).

    Nota: un ComprobanteRenglon sin fila ComprobanteRenglonDetalle (o con
    esa fila pero sin unidad_de_medida cargada) no puede coincidir con
    ningún filtro de unidad de medida, así que no va a aparecer en el
    listado de renglones aunque tenga capacidad libre -- se necesita esa
    fila cargada para poder filtrarlo acá.
    """
    params = request.POST if request.method == 'POST' else request.GET

    entidad_id = params.get('entidad', '').strip()
    producto_mov_id = params.get('producto_movimientos', '').strip()
    # Kg por defecto: es la unidad casi siempre usada en estos movimientos,
    # así el usuario no tiene que elegirla a mano en cada búsqueda; sigue
    # siendo editable (el <select> no queda deshabilitado).
    unidad_mov_id = params.get('unidad_movimientos', '').strip() or UNIDAD_MEDIDA_KILOGRAMOS_ID
    producto_ren_id = params.get('producto_renglones', '').strip() or producto_mov_id
    unidad_ren_id = params.get('unidad_renglones', '').strip() or unidad_mov_id
    # Fecha desde/hasta de movimientos: opcional. La de renglones es
    # obligatoria y por defecto copia la de movimientos (igual criterio
    # que producto/unidad más arriba), pero se puede cambiar aparte.
    fecha_desde_mov = params.get('fecha_desde_movimientos', '').strip()
    fecha_hasta_mov = params.get('fecha_hasta_movimientos', '').strip()
    fecha_desde_ren = params.get('fecha_desde_renglones', '').strip() or fecha_desde_mov
    fecha_hasta_ren = params.get('fecha_hasta_renglones', '').strip() or fecha_hasta_mov

    # Se arma una sola vez (sirve tanto para el redirect después de un POST
    # como para el link "volvé acá" que se le pasa a desvincular_renglon
    # desde la tabla de vínculos existentes más abajo, en un GET).
    querystring = (
        f'entidad={entidad_id}&producto_movimientos={producto_mov_id}'
        f'&unidad_movimientos={unidad_mov_id}&producto_renglones={producto_ren_id}'
        f'&unidad_renglones={unidad_ren_id}'
        f'&fecha_desde_movimientos={fecha_desde_mov}&fecha_hasta_movimientos={fecha_hasta_mov}'
        f'&fecha_desde_renglones={fecha_desde_ren}&fecha_hasta_renglones={fecha_hasta_ren}'
    )
    url_recarga = f"{reverse('cuenta_corriente_productos:vincular_por_bloques')}?{querystring}"

    if request.method == 'POST':
        redirect_url = url_recarga

        renglon_id = request.POST.get('renglon_sel')
        movimiento_ids = request.POST.getlist('movimiento_sel')

        if not renglon_id:
            messages.error(request, 'Debe elegir un renglón de comprobante para vincular.')
        elif not movimiento_ids:
            messages.error(request, 'Debe tildar al menos un movimiento para vincular.')
        else:
            renglon = get_object_or_404(
                ComprobanteRenglon.objects.select_related('renglon_detalle_comprobante'),
                pk=renglon_id,
            )
            # Resguardo por las dudas (la lista de renglones ya excluye los
            # liquidados, ver renglones_qs más abajo): un renglón incluido
            # en una liquidación no debería recibir vínculos nuevos -- esos
            # $ ya están cerrados, agregarle más Kg encima generaría el
            # mismo tipo de descuadre que el caso Bukay, solo que del lado
            # de una liquidación ya hecha en vez de un vínculo suelto.
            if hasattr(renglon, 'liquidacion_producto'):
                messages.error(
                    request,
                    f'El renglón {renglon.id} ya está incluido en una liquidación; no se le puede '
                    'vincular nada más.',
                )
                return redirect(redirect_url)
            disponible = _kg_disponible_renglon(renglon)
            sin_limite = disponible is None  # no hay ComprobanteRenglonDetalle.cantidad cargada

            movimientos_sel = list(Movimiento.objects.filter(pk__in=movimiento_ids))
            # FIFO por fecha: si el renglón no alcanza para cubrir todo lo
            # tildado, lo que queda sin cubrir es de los movimientos más
            # nuevos, y ese resto sigue apareciendo como pendiente en la
            # próxima búsqueda -- no se crea vínculo para lo que no entra.
            movimientos_sel.sort(key=lambda m: (m.fecha or timezone.localdate(), m.id_movimiento))

            creados = 0
            kg_cubiertos = Decimal('0')
            kg_sin_cubrir = Decimal('0')
            for movimiento in movimientos_sel:
                pendiente_mov = _kg_pendiente_movimiento(movimiento)
                if pendiente_mov <= 0:
                    continue  # ya estaba totalmente cubierto (por otro vínculo)
                asignar = pendiente_mov if sin_limite else min(pendiente_mov, disponible)
                if asignar <= 0:
                    kg_sin_cubrir += pendiente_mov
                    continue
                _vinculo, creado = ComprobanteRenglonMovimiento.objects.get_or_create(
                    renglon=renglon, movimiento=movimiento,
                    defaults={'cantidad_kg': asignar},
                )
                if creado:
                    creados += 1
                    kg_cubiertos += asignar
                    if asignar < pendiente_mov:
                        kg_sin_cubrir += (pendiente_mov - asignar)
                    if not sin_limite:
                        disponible -= asignar
                # si ya existía el vínculo, no se lo pisa -- para corregirlo
                # hay que desvincular y volver a vincular.

            if creados == 0:
                messages.error(
                    request,
                    'No se vinculó nada: los movimientos elegidos ya estaban vinculados a ese renglón, '
                    'o no quedaba capacidad disponible en el renglón.',
                )
            else:
                texto = f'{creados} movimiento(s) vinculado(s) al renglón {renglon.id} (cubre {kg_cubiertos:.2f}).'
                if kg_sin_cubrir > 0:
                    texto += (
                        f' El renglón no alcanzó para cubrir todo lo tildado: quedan {kg_sin_cubrir:.2f} '
                        'todavía pendientes de vincular.'
                    )
                elif not sin_limite and disponible > 0:
                    # Caso opuesto al de Bukay: el renglón factura MÁS de lo
                    # que necesitaban los movimientos tildados. No hace
                    # falta hacer nada especial -- la capacidad libre queda
                    # calculada en vivo (_kg_disponible_renglon) y el
                    # renglón va a seguir apareciendo en este mismo listado
                    # la próxima vez, con ese resto disponible -- pero se
                    # avisa para que quede claro que no se perdió nada.
                    texto += f' Al renglón le quedan {disponible:.2f} de capacidad libre para vincular a otro movimiento.'
                messages.success(request, texto)
        return redirect(redirect_url)

    # Solo para precargar el texto de los buscadores con el nombre ya
    # elegido (ver entidades:entidad_buscar / productos:buscar); .first()
    # y no get_object_or_404 porque un id inválido en la URL de un filtro
    # no debería tirar un error 404, solo no precargar/filtrar nada.
    entidad = Entidad.objects.filter(pk=entidad_id).first() if entidad_id.isdigit() else None
    producto_mov = ProductoDetalle.objects.filter(pk=producto_mov_id).first() if producto_mov_id.isdigit() else None
    producto_ren = ProductoDetalle.objects.filter(pk=producto_ren_id).first() if producto_ren_id.isdigit() else None
    unidad_mov = ComprobanteUnidadDeMedida.objects.filter(pk=unidad_mov_id).first() if unidad_mov_id else None
    unidad_ren = ComprobanteUnidadDeMedida.objects.filter(pk=unidad_ren_id).first() if unidad_ren_id else None

    # La fecha (en ambos lados) es opcional: acota el listado si se
    # completa, pero no bloquea el botón de vincular si se deja vacía --
    # entidad + producto + unidad ya alcanzan para no traer un volumen
    # inmanejable (los listados igual se cortan en 300 filas).
    filtro_movimientos_completo = bool(entidad and producto_mov and unidad_mov)
    filtro_renglones_completo = bool(entidad and producto_ren and unidad_ren)

    # "Sin vincular" ya no es simplemente "sin ningún vínculo": un
    # movimiento con vínculos puede seguir teniendo Kg pendientes si el/los
    # renglón(es) vinculados no llegaban a cubrirlo del todo, y un renglón
    # puede seguir teniendo capacidad libre aunque ya tenga algún vínculo.
    # Por eso el filtro real (kg_pendiente/kg_disponible > 0) se calcula en
    # Python fila por fila -- no se puede expresar como un solo filter() de
    # SQL porque depende de sumar cantidad_kg entre varios vínculos y
    # compararlo contra otro campo del mismo movimiento/renglón.
    movimientos = []
    if filtro_movimientos_completo:
        movimientos_qs = (
            Movimiento.objects
            .filter(producto_id=producto_mov.pk, unidad_de_medida_id=unidad_mov.pk)
            .filter(Q(entidad_emisor_id=entidad.pk) | Q(entidad_receptor_id=entidad.pk))
            .select_related('entidad_emisor', 'entidad_receptor', 'producto', 'unidad_de_medida')
            .prefetch_related('vinculos_comprobante')
        )
        if fecha_desde_mov:
            movimientos_qs = movimientos_qs.filter(fecha__gte=fecha_desde_mov)
        if fecha_hasta_mov:
            movimientos_qs = movimientos_qs.filter(fecha__lte=fecha_hasta_mov)
        for mov in movimientos_qs.order_by('-fecha', '-id_movimiento')[:2000]:
            pendiente = _kg_pendiente_movimiento(mov, vinculos=list(mov.vinculos_comprobante.all()))
            if pendiente > 0:
                mov.kg_pendiente = pendiente
                movimientos.append(mov)
                if len(movimientos) >= 300:
                    break

    renglones = []
    if filtro_renglones_completo:
        renglones_qs = (
            ComprobanteRenglon.objects
            .filter(
                producto_id=producto_ren.pk,
                comprobante__entidad_emisor_id=entidad.pk,
                renglon_detalle_comprobante__unidad_de_medida_id=unidad_ren.pk,
            )
            # Un renglón incluido en una liquidación ya está "cerrado":
            # igual que no se lo puede desvincular sin revertir esa
            # liquidación primero (ver desvincular_renglon), tampoco
            # debería poder recibir vínculos nuevos -- si no, se le podría
            # agregar Kg por atrás de una liquidación que ya se hizo con
            # otro número, sin que quede registrado en ningún lado (mismo
            # espíritu que el bug de Bukay, del otro lado).
            .filter(liquidacion_producto__isnull=True)
            .select_related('comprobante', 'comprobante__tipo_comprobante', 'renglon_detalle_comprobante')
            .prefetch_related('vinculos_movimiento')
        )
        if fecha_desde_ren:
            renglones_qs = renglones_qs.filter(comprobante__fecha__gte=fecha_desde_ren)
        if fecha_hasta_ren:
            renglones_qs = renglones_qs.filter(comprobante__fecha__lte=fecha_hasta_ren)
        for ren in renglones_qs.order_by('-comprobante__fecha')[:2000]:
            vinculos = list(ren.vinculos_movimiento.all())
            disponible = _kg_disponible_renglon(ren, vinculos=vinculos)
            if not vinculos or disponible is None or disponible > 0:
                ren.kg_disponible = disponible
                renglones.append(ren)
                if len(renglones) >= 300:
                    break

    # Búsqueda automática de "candidato de vínculo": para cada renglón con
    # capacidad libre CONOCIDA (kg_disponible no None), se busca si la
    # suma de Kg pendientes de uno o más de los movimientos que ya están
    # en este mismo listado da EXACTO esa capacidad. Si la encuentra, el
    # renglón queda "candidateado" con un botón que tilda esos movimientos
    # y elige ese renglón de un solo click en la tabla de abajo -- el
    # usuario sigue teniendo que apretar "Vincular" para confirmarlo, esto
    # no vincula nada solo. Se trabaja en centavos (enteros) para comparar
    # montos exactos sin arrastrar errores de punto flotante con Decimal.
    #
    # Arranca por el primer comprobante de CANDIDATO_ANIO_DESDE en
    # adelante (ascendente, los más viejos primero) y, para cada renglón,
    # solo prueba combinaciones con movimientos cuya fecha esté entre
    # CANDIDATO_DIAS_ANTES_COMPROBANTE días antes y
    # CANDIDATO_DIAS_DESPUES_COMPROBANTE días después de la fecha de ESE
    # comprobante (no contra todos los movimientos del filtro, que podría
    # ser una ventana mucho más amplia e irrelevante).
    #
    # Dos estrategias, en orden (caso real: entidad Katz Diego Gabriel,
    # donde hacían falta muchos movimientos para completar un comprobante
    # y la búsqueda por combinaciones no los encontraba):
    #   1) Por prefijo de fecha (_buscar_combinacion_por_prefijo_kg): suma
    #      los movimientos del más antiguo al más nuevo y corta apenas
    #      llega o se pasa del objetivo -- sin límite de cantidad de
    #      movimientos, cubre la gran mayoría de los casos reales (un
    #      comprobante que corresponde a una tanda de movimientos
    #      seguidos).
    #   2) Si esa no encuentra nada, por combinaciones
    #      (_buscar_combinacion_exacta_kg), acotada a
    #      CANDIDATO_MAX_MOVIMIENTOS_COMBINADOS movimientos -- para los
    #      casos en que el comprobante no corresponde a una tanda seguida
    #      sino a movimientos sueltos salteados en el medio.
    #
    # Un mismo movimiento puede entrar en la "ventana" de más de un
    # renglón (fechas cercanas). Para que dos candidatos mostrados en el
    # mismo listado no terminen ofreciendo EL MISMO movimiento (algo que,
    # si el usuario vincula el primer candidato, deja al segundo
    # candidato mostrando una suma que ya no da exacta -- sus Kg ya se
    # usaron), cada movimiento elegido por el candidato de un renglón
    # queda "reservado" y se excluye de la búsqueda de los renglones
    # siguientes en este mismo recorrido (van en orden de fecha de
    # comprobante, el más antiguo primero, así que ese es el criterio de
    # prioridad: el comprobante más viejo se queda con el movimiento
    # primero). Al recargar la página después de vincular, esto se
    # recalcula desde cero con los vínculos ya guardados, así que el
    # candidato que quedaba pisado va a desaparecer o va a recalcularse
    # con lo que de verdad sigue disponible.
    for ren in renglones:
        ren.candidato_automatico = None
    if movimientos and renglones:
        candidatos_renglones = sorted(
            (
                ren for ren in renglones
                if ren.kg_disponible is not None and ren.kg_disponible > 0
                and ren.comprobante.fecha and ren.comprobante.fecha.year >= CANDIDATO_ANIO_DESDE
            ),
            key=lambda ren: ren.comprobante.fecha,
        )[:CANDIDATO_MAX_RENGLONES_A_BUSCAR]

        movimientos_reservados = set()
        for ren in candidatos_renglones:
            fecha_comprobante = ren.comprobante.fecha
            desde_mov = fecha_comprobante - timedelta(days=CANDIDATO_DIAS_ANTES_COMPROBANTE)
            hasta_mov = fecha_comprobante + timedelta(days=CANDIDATO_DIAS_DESPUES_COMPROBANTE)
            valores_en_ventana = [
                (mov.id_movimiento, int(round(mov.kg_pendiente * 100)), mov.fecha)
                for mov in movimientos
                if mov.kg_pendiente and mov.kg_pendiente > 0
                and mov.fecha and desde_mov <= mov.fecha <= hasta_mov
                and mov.id_movimiento not in movimientos_reservados
            ]
            if not valores_en_ventana:
                continue
            objetivo = int(round(ren.kg_disponible * 100))

            valores_por_fecha = [
                (id_mov, monto)
                for id_mov, monto, _fecha in sorted(valores_en_ventana, key=lambda t: (t[2], t[0]))
            ]
            candidato = _buscar_combinacion_por_prefijo_kg(valores_por_fecha, objetivo)
            if candidato is None:
                valores_por_monto = sorted(
                    ((id_mov, monto) for id_mov, monto, _fecha in valores_en_ventana),
                    key=lambda par: par[1],
                )
                candidato = _buscar_combinacion_exacta_kg(valores_por_monto, objetivo)
            ren.candidato_automatico = candidato
            if candidato:
                movimientos_reservados.update(candidato)

    # Vínculos ya existentes para este mismo filtro del lado movimientos
    # (entidad + producto + unidad + fecha opcional) -- para poder
    # desvincular renglones sueltos desde acá mismo, sin tener que ir uno
    # por uno a "Vincular renglón" de cada movimiento. Se muestran todos,
    # tengan o no capacidad/pendiente libre: desvincular siempre libera Kg
    # (los vuelve a dejar pendientes), esté o no el movimiento en el
    # listado de arriba.
    vinculos_existentes = []
    if filtro_movimientos_completo:
        vinculos_qs = (
            ComprobanteRenglonMovimiento.objects
            .filter(
                movimiento__producto_id=producto_mov.pk,
                movimiento__unidad_de_medida_id=unidad_mov.pk,
            )
            .filter(Q(movimiento__entidad_emisor_id=entidad.pk) | Q(movimiento__entidad_receptor_id=entidad.pk))
            .select_related(
                'movimiento', 'movimiento__entidad_emisor', 'movimiento__entidad_receptor',
                'renglon', 'renglon__comprobante', 'renglon__comprobante__tipo_comprobante',
                'renglon__renglon_detalle_comprobante',
            )
        )
        if fecha_desde_mov:
            vinculos_qs = vinculos_qs.filter(movimiento__fecha__gte=fecha_desde_mov)
        if fecha_hasta_mov:
            vinculos_qs = vinculos_qs.filter(movimiento__fecha__lte=fecha_hasta_mov)
        vinculos_existentes = list(
            vinculos_qs
            .prefetch_related('renglon__vinculos_movimiento__movimiento')
            .order_by('-movimiento__fecha', '-movimiento_id')[:300]
        )

        # Para cada renglón que aparece acá, cuánto suman los Kg de TODOS
        # los movimientos vinculados a él (no solo los de este filtro)
        # contra lo que factura el renglón -- mismo chequeo que hace
        # corregir_vinculos_kg, mostrado en vivo para poder verlo/actuar sin
        # correr el comando. Es exactamente la diferencia que causó el caso
        # Bukay Olivia Eugenia (renglón facturaba menos que lo vinculado) y
        # también detecta el caso opuesto (renglón factura de más).
        capacidad_por_renglon = {}
        suma_por_renglon = {}
        for vinculo in vinculos_existentes:
            renglon_id = vinculo.renglon_id
            if renglon_id in suma_por_renglon:
                continue
            detalle = getattr(vinculo.renglon, 'renglon_detalle_comprobante', None)
            capacidad_por_renglon[renglon_id] = (
                detalle.cantidad if detalle and detalle.cantidad is not None else None
            )
            suma_por_renglon[renglon_id] = sum(
                (v.movimiento.total or Decimal('0')) for v in vinculo.renglon.vinculos_movimiento.all()
            )

        for vinculo in vinculos_existentes:
            capacidad = capacidad_por_renglon[vinculo.renglon_id]
            if capacidad is None:
                vinculo.renglon_diferencia = None
                vinculo.renglon_diferencia_texto = None
            else:
                diferencia = suma_por_renglon[vinculo.renglon_id] - capacidad
                vinculo.renglon_diferencia = diferencia
                signo = '+' if diferencia > 0 else ''
                vinculo.renglon_diferencia_texto = f'{signo}{diferencia:.2f}'

        # Los que tienen una diferencia real (sea de más o de menos)
        # primero; sort() es estable, así que dentro de cada grupo se
        # mantiene el orden por fecha ya traído de la consulta.
        vinculos_existentes.sort(
            key=lambda v: v.renglon_diferencia is None or v.renglon_diferencia == 0
        )

    return render(request, 'cuenta_corriente_productos/vincular_por_bloques.html', {
        'entidad': entidad,
        'producto_mov': producto_mov,
        'producto_ren': producto_ren,
        'unidad_mov': unidad_mov,
        'unidad_ren': unidad_ren,
        'vinculos_existentes': vinculos_existentes,
        'url_recarga': url_recarga,
        'q_entidad': entidad_id,
        'q_producto_mov': producto_mov_id,
        'q_unidad_mov': unidad_mov_id,
        'q_producto_ren': producto_ren_id,
        'q_unidad_ren': unidad_ren_id,
        'fecha_desde_mov': fecha_desde_mov,
        'fecha_hasta_mov': fecha_hasta_mov,
        'fecha_desde_ren': fecha_desde_ren,
        'fecha_hasta_ren': fecha_hasta_ren,
        # Del lado renglones se excluyen las unidades agregadas solo para
        # Remitos (Bolsón/Bolsa, no vienen del padrón AFIP): un renglón de
        # comprobante fiscal real nunca las usa (ver
        # comprobantes.forms.ComprobanteRenglonDetalleForm), así que no
        # tiene sentido ofrecerlas como filtro de ese lado. Del lado
        # movimientos sí se muestra el catálogo completo, porque
        # Movimiento.unidad_de_medida se carga en unidades reales del
        # negocio (kg, bolsón, bolsa) sin esa restricción.
        'unidades_medida_mov': ComprobanteUnidadDeMedida.objects.order_by('nombre'),
        'unidades_medida_ren': ComprobanteUnidadDeMedida.objects.exclude(pk__in=IDS_UNIDADES_SOLO_REMITOS).order_by('nombre'),
        'movimientos': movimientos,
        'renglones': renglones,
        'filtro_movimientos_completo': filtro_movimientos_completo,
        'filtro_renglones_completo': filtro_renglones_completo,
    })


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
            renglon = get_object_or_404(
                ComprobanteRenglon.objects.select_related('renglon_detalle_comprobante'),
                pk=renglon_id,
            )
            # Resguardo por las dudas (la búsqueda de acá abajo ya excluye
            # los renglones liquidados): uno ya incluido en una liquidación
            # no debería recibir vínculos nuevos -- ver mismo comentario en
            # vincular_por_bloques.
            if hasattr(renglon, 'liquidacion_producto'):
                messages.error(
                    request,
                    f'El renglón {renglon.id} ya está incluido en una liquidación; no se le puede '
                    'vincular nada más.',
                )
                return redirect('cuenta_corriente_productos:vincular_renglon', movimiento_id=movimiento.id_movimiento)
            pendiente_mov = _kg_pendiente_movimiento(movimiento)
            disponible = _kg_disponible_renglon(renglon)
            # Igual criterio que "Vincular por bloques": si no hay cantidad
            # cargada en el renglón no hay con qué limitar (cubre entero);
            # si la hay, no se puede cubrir más de lo que le queda libre.
            asignar = pendiente_mov if disponible is None else min(pendiente_mov, disponible)
            _vinculo, creado = ComprobanteRenglonMovimiento.objects.get_or_create(
                renglon=renglon, movimiento=movimiento,
                defaults={'cantidad_kg': asignar},
            )
            if creado:
                texto = f'Renglón {renglon.id} vinculado al movimiento {movimiento.id_movimiento} (cubre {asignar:.2f}).'
                if asignar < pendiente_mov:
                    texto += f' Quedan {(pendiente_mov - asignar):.2f} todavía pendientes de vincular.'
                messages.success(request, texto)
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
            # Igual que en "Vincular por bloques": un renglón ya incluido
            # en una liquidación no se ofrece para vincular más -- ese
            # comprobante ya está cerrado.
            .filter(liquidacion_producto__isnull=True)
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
        'kg_pendiente': _kg_pendiente_movimiento(movimiento),
    })


def desvincular_renglon(request, vinculo_id):
    """
    Elimina un ComprobanteRenglonMovimiento. Como _kg_pendiente_movimiento y
    _kg_disponible_renglon se recalculan en vivo desde los vínculos que
    existen en ese momento, borrar el vínculo alcanza para que esos Kg
    vuelvan a aparecer como pendientes/disponibles en cualquier pantalla --
    no hace falta ningún ajuste extra acá.

    Alcanzable desde "Vincular renglón" (un movimiento a la vez) y desde
    "Vincular por bloques" (tabla de vínculos existentes del filtro
    elegido); en ambos casos se vuelve a la pantalla de origen gracias al
    campo oculto "next" del formulario que llama a esta vista -- si no
    viene (o no es una URL propia del sitio, por las dudas), se cae al
    comportamiento de siempre.
    """
    vinculo = get_object_or_404(ComprobanteRenglonMovimiento, pk=vinculo_id)
    movimiento_id = vinculo.movimiento_id
    next_url = request.POST.get('next') or request.GET.get('next')
    if request.method == 'POST':
        # No se puede desvincular un renglón que ya forma parte de una
        # liquidación cerrada: ahí la baja hay que hacerla revirtiendo esa
        # liquidación primero (ver LiquidacionProductoComprobanteRenglon).
        if hasattr(vinculo.renglon, 'liquidacion_producto'):
            messages.error(request, 'Ese renglón ya está incluido en una liquidación; no se puede desvincular directamente.')
        else:
            vinculo.delete()
            messages.success(request, 'Vínculo eliminado: esos Kg vuelven a estar pendientes de vincular.')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('cuenta_corriente_productos:vincular_renglon', movimiento_id=movimiento_id)


def desvincular_varios(request):
    """
    Versión "de a varios" de desvincular_renglon: recibe una lista de
    ComprobanteRenglonMovimiento.id (checkboxes 'vinculo_sel') y los borra
    de una sola vez, en vez de tener que desvincular uno por uno. Mismo
    resguardo de liquidación que desvincular_renglon, aplicado por cada
    vínculo: los que ya están incluidos en una liquidación no se tocan (se
    informa cuántos quedaron afuera por eso), el resto se elimina.

    Pensada para la tabla "Vínculos ya existentes" de Vincular por
    bloques, donde puede convenir desvincular varios de un filtro de una
    sola vez. Mismo campo oculto "next" que desvincular_renglon para
    volver a la pantalla de origen con el filtro elegido.
    """
    next_url = request.POST.get('next') or request.GET.get('next')
    if request.method == 'POST':
        vinculo_ids = request.POST.getlist('vinculo_sel')
        if not vinculo_ids:
            messages.error(request, 'Debe tildar al menos un vínculo para desvincular.')
        else:
            vinculos = list(
                ComprobanteRenglonMovimiento.objects
                .filter(pk__in=vinculo_ids)
                .select_related('renglon')
            )
            eliminados = 0
            bloqueados = 0
            for vinculo in vinculos:
                if hasattr(vinculo.renglon, 'liquidacion_producto'):
                    bloqueados += 1
                    continue
                vinculo.delete()
                eliminados += 1

            if eliminados:
                texto = f'{eliminados} vínculo(s) eliminado(s): esos Kg vuelven a estar pendientes de vincular.'
                if bloqueados:
                    texto += (
                        f' {bloqueados} no se pudo(ieron) desvincular porque ya '
                        'está(n) incluido(s) en una liquidación.'
                    )
                messages.success(request, texto)
            else:
                messages.error(
                    request,
                    'Ninguno de los vínculos tildados se pudo desvincular: ya están incluidos en una liquidación.',
                )
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('cuenta_corriente_productos:vincular_por_bloques')


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

    return render(request, 'cuenta_corriente_productos/cuenta_corriente.html', {
        'entidad': entidad,
        'producto': producto,
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

    return render(request, 'cuenta_corriente_productos/liquidacion_alta.html', {
        'entidad': entidad,
        'producto': producto,
        'fecha': fecha,
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


# ---------------------------------------------------------------------------
# Pendientes por producto (agregado de "cuánto queda pendiente de vincular",
# agrupado por producto y, dentro de cada uno, por entidad) -- pensado como
# una versión "por producto" del viejo listado alfabético de saldos en papel
# (Fontana S.A. -- "Listado alfabético de saldos"), pero acotado a lo que
# todavía está pendiente de vincular en vez de todo el historial de la
# cuenta corriente.
# ---------------------------------------------------------------------------

def _entidad_contraparte_movimiento(movimiento):
    """
    La entidad "externa" (proveedor/cliente) de un Movimiento. En el uso
    normal del sistema, uno de los dos lados (entidad_emisor / entidad_
    receptor) siempre es la propia empresa (ENTIDAD_PROPIA_ID) y el otro es
    la contraparte real -- igual criterio que ya usa movimientos/views.py
    ("el emisor de una salida es siempre la propia empresa"). Si el emisor
    ya es Fontana, la contraparte es el receptor; si no, es el emisor.
    """
    if movimiento.entidad_emisor_id == ENTIDAD_PROPIA_ID:
        return movimiento.entidad_receptor
    return movimiento.entidad_emisor


def _asignado_por_vinculo_null(renglon_ids):
    """
    Para los ComprobanteRenglonMovimiento con cantidad_kg=null que cuelgan
    de estos renglones, calcula cuánto de cada uno se considera realmente
    cubierto -- EXACTAMENTE el mismo algoritmo que el management command
    `corregir_vinculos_kg` (FIFO por fecha del movimiento, descontando
    primero lo que ya tengan asignado los vínculos con cantidad_kg real),
    pero calculado acá en memoria, SIN GUARDAR NADA. Así "Pendientes por
    producto" ya muestra el Kg realmente pendiente (caso Bukay Olivia
    Eugenia: renglón que factura menos de lo que suman sus movimientos
    vinculados) sin depender de que alguien haya corrido ese comando
    todavía. Devuelve {vinculo_id: Decimal}.
    """
    resultado = {}
    if not renglon_ids:
        return resultado

    vinculos_por_renglon = {}
    vinculos_qs = (
        ComprobanteRenglonMovimiento.objects
        .filter(renglon_id__in=renglon_ids)
        .select_related('movimiento', 'renglon__renglon_detalle_comprobante')
        .order_by('movimiento__fecha', 'movimiento_id')
    )
    for vinculo in vinculos_qs:
        vinculos_por_renglon.setdefault(vinculo.renglon_id, []).append(vinculo)

    for vinculos in vinculos_por_renglon.values():
        renglon = vinculos[0].renglon
        detalle = getattr(renglon, 'renglon_detalle_comprobante', None)
        capacidad = detalle.cantidad if detalle and detalle.cantidad is not None else None

        if capacidad is None:
            # Sin cantidad facturada cargada: no hay con qué comparar, se
            # mantiene el comportamiento de siempre (se asume que cubre
            # completo) -- mismo criterio que corregir_vinculos_kg.
            for vinculo in vinculos:
                if vinculo.cantidad_kg is None:
                    resultado[vinculo.id] = vinculo.movimiento.total or Decimal('0')
            continue

        restante = capacidad
        for vinculo in vinculos:
            if vinculo.cantidad_kg is not None:
                restante -= vinculo.cantidad_kg
        for vinculo in vinculos:
            if vinculo.cantidad_kg is not None:
                continue
            total_mov = vinculo.movimiento.total or Decimal('0')
            asignado = min(restante, total_mov) if restante > 0 else Decimal('0')
            restante -= asignado
            resultado[vinculo.id] = asignado

    return resultado


def _kg_pendiente_movimiento_corregido(movimiento, asignado_null):
    """
    Como _kg_pendiente_movimiento, pero para los vínculos con
    cantidad_kg=null usa lo que dio _asignado_por_vinculo_null en vez de
    asumir "cubre completo" -- ver el docstring de esa función. Usada solo
    en "Pendientes por producto".
    """
    total = movimiento.total or Decimal('0')
    cubierto = Decimal('0')
    for vinculo in movimiento.vinculos_comprobante.all():
        if vinculo.cantidad_kg is not None:
            cubierto += vinculo.cantidad_kg
        else:
            cubierto += asignado_null.get(vinculo.id, Decimal('0'))
    pendiente = total - cubierto
    return pendiente if pendiente > 0 else Decimal('0')


def _diferencia_kg_renglon(renglon):
    """
    Suma de Kg (Movimiento.total) de TODOS los movimientos vinculados a
    este renglón, menos lo que factura el renglón (ComprobanteRenglonDetalle
    .cantidad). None si el renglón no tiene cargada esa cantidad (no hay
    con qué comparar). Mismo cálculo que ya usa "Vincular por bloques" en
    su columna "Diferencia (renglón)".

    Positivo = el renglón tiene vinculado más Kg de los que factura (caso
    Bukay Olivia Eugenia) -- eso ya queda reflejado del lado "pendiente"
    de movimientos (ver _kg_pendiente_movimiento_corregido), así que
    _calcular_pendientes_por_producto lo ignora acá para no contarlo dos
    veces. Negativo = al renglón le sobra capacidad (se facturó más
    cantidad de la que en realidad respaldan sus movimientos vinculados)
    -- este es el caso que SÍ se agrega en "Pendientes por producto", como
    columna aparte "Capacidad de renglón sin usar" (agregado 2026-09-09 a
    pedido del usuario, sin volver a mezclarlo con el saldo pendiente:
    mezclarlos en un solo número fue justamente el bug del caso Bukay).
    """
    detalle = getattr(renglon, 'renglon_detalle_comprobante', None)
    capacidad = detalle.cantidad if detalle and detalle.cantidad is not None else None
    if capacidad is None:
        return None
    suma = sum(
        (v.movimiento.total or Decimal('0')) for v in renglon.vinculos_movimiento.all()
    )
    return suma - capacidad


def _calcular_pendientes_por_producto(fecha_desde=None, fecha_hasta=None, producto_id=None, unidad_id=None):
    """
    Arma, para cada (producto, unidad de medida), dos totales agregados
    por entidad -- deliberadamente SEPARADOS, sin restar uno del otro (esa
    resta fue justamente el bug del caso Bukay Olivia Eugenia):

    - "pendiente"/"saldo": para cada movimiento, cuánto de su total ningún
      vínculo cubre todavía -- usando _kg_pendiente_movimiento_corregido
      (que ya tiene en cuenta, sin necesidad de correr ningún comando
      aparte, los vínculos viejos cuya suma vinculada al renglón supera lo
      que ese renglón factura).
    - "capacidad_sin_usar": para los renglones de ese producto/unidad que
      facturaron MÁS cantidad de la que en realidad respaldan sus
      movimientos vinculados (_diferencia_kg_renglon negativa) -- el caso
      opuesto a Bukay. Se atribuye a la entidad emisora del comprobante.

    fecha_desde/fecha_hasta se aplican a Movimiento.fecha del lado
    pendiente y a Comprobante.fecha del lado capacidad_sin_usar (mismo
    campo que usa cada uno en el resto de la app). producto_id/unidad_id
    acotan el cálculo a un solo producto (y, si se indica, una sola
    unidad) -- se usa para las exportaciones Excel/PDF de un producto
    puntual, sin tener que recalcular todos los demás.
    """
    movimientos_qs = (
        Movimiento.objects
        .select_related('producto', 'unidad_de_medida', 'entidad_emisor', 'entidad_receptor')
        .prefetch_related('vinculos_comprobante')
    )
    if producto_id:
        movimientos_qs = movimientos_qs.filter(producto_id=producto_id)
    if unidad_id:
        movimientos_qs = movimientos_qs.filter(unidad_de_medida_id=unidad_id)
    if fecha_desde:
        movimientos_qs = movimientos_qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        movimientos_qs = movimientos_qs.filter(fecha__lte=fecha_hasta)

    movimientos = list(movimientos_qs)

    # Los vínculos viejos (cantidad_kg=null) de los renglones que tocan
    # estos movimientos se resuelven TODOS juntos acá (no vínculo por
    # vínculo), en memoria y sin guardar nada -- ver _asignado_por_vinculo_null.
    renglon_ids_con_null = set(
        ComprobanteRenglonMovimiento.objects
        .filter(movimiento__in=movimientos, cantidad_kg__isnull=True)
        .values_list('renglon_id', flat=True)
        .distinct()
    )
    asignado_null = _asignado_por_vinculo_null(renglon_ids_con_null)

    datos = {}  # (producto_id, unidad_id o None) -> {'producto', 'unidad', 'entidades': {id: {...}}}

    def _bucket(producto, unidad):
        clave = (producto.id, unidad.id if unidad else None)
        return datos.setdefault(clave, {'producto': producto, 'unidad': unidad, 'entidades': {}})

    def _fila_entidad(bucket, entidad):
        return bucket['entidades'].setdefault(
            entidad.id,
            {'entidad': entidad, 'pendiente': Decimal('0'), 'capacidad_sin_usar': Decimal('0')},
        )

    for mov in movimientos:
        entidad = _entidad_contraparte_movimiento(mov)
        if entidad is None:
            continue
        pendiente = _kg_pendiente_movimiento_corregido(mov, asignado_null)
        if not pendiente:
            continue
        bucket = _bucket(mov.producto, mov.unidad_de_medida)
        _fila_entidad(bucket, entidad)['pendiente'] += pendiente

    # Lado renglones: capacidad facturada de más (ver _diferencia_kg_renglon).
    # El filtro de fechas acá se aplica a Comprobante.fecha (no
    # Movimiento.fecha), igual que hacía el filtro "renglones" de "Vincular
    # por bloques".
    renglones_qs = (
        ComprobanteRenglon.objects
        .filter(vinculos_movimiento__isnull=False)
        .select_related(
            'producto', 'comprobante__entidad_emisor', 'renglon_detalle_comprobante__unidad_de_medida',
        )
        .prefetch_related('vinculos_movimiento__movimiento')
        .distinct()
    )
    if producto_id:
        renglones_qs = renglones_qs.filter(producto_id=producto_id)
    if unidad_id:
        renglones_qs = renglones_qs.filter(renglon_detalle_comprobante__unidad_de_medida_id=unidad_id)
    if fecha_desde:
        renglones_qs = renglones_qs.filter(comprobante__fecha__gte=fecha_desde)
    if fecha_hasta:
        renglones_qs = renglones_qs.filter(comprobante__fecha__lte=fecha_hasta)

    for renglon in renglones_qs:
        diferencia = _diferencia_kg_renglon(renglon)
        if diferencia is None or diferencia >= 0:
            continue  # sin capacidad cargada, exacto, o vinculado de más (ya es "pendiente")
        entidad = renglon.comprobante.entidad_emisor if renglon.comprobante else None
        if entidad is None:
            continue
        detalle = renglon.renglon_detalle_comprobante
        unidad = detalle.unidad_de_medida if detalle else None
        bucket = _bucket(renglon.producto, unidad)
        _fila_entidad(bucket, entidad)['capacidad_sin_usar'] += -diferencia

    filas_producto = []
    for bucket in datos.values():
        entidades = [
            f for f in bucket['entidades'].values()
            if f['pendiente'] or f['capacidad_sin_usar']
        ]
        if not entidades:
            continue
        for fila in entidades:
            fila['saldo'] = fila['pendiente']  # alias: acá "pendiente" y "saldo" coinciden siempre
        entidades.sort(key=lambda f: (f['entidad'].nombre or '').upper())
        saldo_total = sum((f['saldo'] for f in entidades), Decimal('0'))
        capacidad_sin_usar_total = sum((f['capacidad_sin_usar'] for f in entidades), Decimal('0'))
        filas_producto.append({
            'producto': bucket['producto'],
            'unidad': bucket['unidad'],
            'entidades': entidades,
            'saldo_total': saldo_total,
            'favor_total': saldo_total,
            'contra_total': Decimal('0'),
            'capacidad_sin_usar_total': capacidad_sin_usar_total,
        })

    filas_producto.sort(key=lambda f: (f['producto'].nombre or '').upper())
    return filas_producto


def pendientes_por_producto(request):
    """
    Pantalla principal: una fila por (producto, unidad de medida) con
    movimientos pendientes de vincular y/o renglones vinculados de más,
    con el saldo total agregado y, al lado, los botones para exportar el
    detalle por entidad de ESE producto (Excel/PDF).
    """
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()

    filas = _calcular_pendientes_por_producto(fecha_desde or None, fecha_hasta or None)

    return render(request, 'cuenta_corriente_productos/pendientes_por_producto.html', {
        'filas': filas,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    })


def _fila_pendientes_producto_puntual(request):
    """Helper compartido por las dos exportaciones (Excel/PDF) de un solo
    producto: recalcula _calcular_pendientes_por_producto acotado a ese
    producto/unidad/rango de fechas (los mismos query params que la
    pantalla principal, más 'producto' y, opcional, 'unidad') y devuelve
    la única fila resultante (o None si no hay nada que exportar)."""
    producto_id = request.GET.get('producto')
    if not producto_id or not producto_id.isdigit():
        return None, None, None
    # ComprobanteUnidadDeMedida.id es un CharField (ej. '01'), no un
    # número -- se pasa tal cual llega por GET, sin convertir a int (eso
    # le haría perder el cero a la izquierda y ya no matchearía nada).
    unidad_id = request.GET.get('unidad') or None
    fecha_desde = request.GET.get('fecha_desde', '').strip() or None
    fecha_hasta = request.GET.get('fecha_hasta', '').strip() or None

    filas = _calcular_pendientes_por_producto(
        fecha_desde, fecha_hasta, producto_id=int(producto_id), unidad_id=unidad_id,
    )
    fila = filas[0] if filas else None
    return fila, fecha_desde, fecha_hasta


def _resultado_reporte_pendientes_producto(fila):
    # Con el cálculo corregido el saldo pendiente de cada entidad siempre
    # es >= 0 (ver _kg_pendiente_movimiento_corregido), así que ya no tiene
    # sentido desglosar "a favor" vs. "en contra" ahí -- alcanza con el
    # total. La "capacidad de renglón sin usar" es un concepto aparte
    # (renglones facturados de más, no movimientos sin vincular) y se
    # muestra en su propia columna, sin mezclarla con el saldo pendiente.
    unidad_nombre = fila['unidad'].nombre if fila['unidad'] else 'sin unidad'
    columnas = [
        'Entidad',
        f'Saldo pendiente ({unidad_nombre})',
        f'Capacidad de renglón sin usar ({unidad_nombre})',
    ]
    filas_tabla = [
        [str(f['entidad']), float(f['saldo']), float(f['capacidad_sin_usar'])]
        for f in fila['entidades']
    ]
    filas_tabla.append(['', None, None])
    filas_tabla.append([
        'Total', float(fila['saldo_total']), float(fila['capacidad_sin_usar_total']),
    ])
    return {
        'columnas': columnas,
        'filas': filas_tabla,
        'columnas_numericas': {1, 2},
        'anchos': [3, 1.6, 2],
    }


def pendientes_por_producto_excel(request):
    fila, _fecha_desde, _fecha_hasta = _fila_pendientes_producto_puntual(request)
    if not fila:
        messages.error(request, 'No hay datos pendientes para exportar con ese filtro.')
        return redirect('cuenta_corriente_productos:pendientes_por_producto')
    nombre = f"pendientes_{fila['producto'].nombre or fila['producto'].id}".replace(' ', '_')
    return excel_response(nombre, _resultado_reporte_pendientes_producto(fila))


def pendientes_por_producto_pdf(request):
    fila, _fecha_desde, _fecha_hasta = _fila_pendientes_producto_puntual(request)
    if not fila:
        messages.error(request, 'No hay datos pendientes para exportar con ese filtro.')
        return redirect('cuenta_corriente_productos:pendientes_por_producto')
    unidad_nombre = fila['unidad'].nombre if fila['unidad'] else 'sin unidad'
    titulo = f"Pendientes de vincular - {fila['producto'].nombre} ({unidad_nombre})"
    nombre = f"pendientes_{fila['producto'].nombre or fila['producto'].id}".replace(' ', '_')
    return pdf_response(nombre, titulo, _resultado_reporte_pendientes_producto(fila))
