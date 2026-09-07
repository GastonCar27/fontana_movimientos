from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from entidades.forms import EntidadRolRapidoForm
from entidades.models import Entidad, Rol
from productos.models import ProductoDetalle
from movimientos.models import Movimiento
from services.buscadores import texto_entidad_buscador
from services.ordenamiento import aplicar_orden_queryset
from services.reportes import excel_response, pdf_response

from . import forms
from .models import Acoplado, CondicionVenta, ObservacionEstandar, Remito, RemitoRenglon, Vehiculo

ENTIDAD_PROPIA_ID = getattr(settings, 'ENTIDAD_PROPIA_ID', 100)


# ---------------------------------------------------------------------------
# Helpers comunes
# ---------------------------------------------------------------------------

def _texto_producto(producto):
    if not producto:
        return ''
    return f'{producto.id} - {producto.nombre}' if producto.nombre else str(producto.id)


def _texto_remito(remito):
    if not remito:
        return ''
    return f'{remito} - {texto_entidad_buscador(remito.contraparte)}'


def _siguiente_numero_movimiento(producto):
    """El 'numero' de Movimiento es un campo de referencia interno (no viene
    del remito): se calcula como el siguiente disponible PARA ESE PRODUCTO,
    porque la tabla movimiento tiene una restricción única (numero,
    producto). No se reusa directamente el número del remito acá porque el
    de Remito es único sólo por emisor (puede repetirse entre distintos
    emisores) y chocaría con esa restricción."""
    ultimo = Movimiento.objects.filter(producto=producto).aggregate(Max('numero'))['numero__max'] or 0
    return ultimo + 1


@transaction.atomic
def _sincronizar_movimiento_renglon(renglon):
    """Crea o actualiza el Movimiento de productos vinculado a este renglón
    de remito: se crea la primera vez que se guarda el renglón (con el peso
    definitivo disponible en ese momento) y, si más tarde se completa
    'kilogramos_confirmados' (el peso que se pesó/facturó en destino, que
    puede diferir del enviado) o se cambia el producto del renglón, se
    actualiza el MISMO movimiento en vez de crear uno nuevo, para no
    duplicar el saldo del producto."""
    remito = renglon.remito
    total = renglon.kilogramos_definitivos

    if renglon.movimiento_id:
        movimiento = renglon.movimiento
        if movimiento.producto_id != renglon.producto_id:
            # Cambió el producto del renglón: 'numero' es un correlativo
            # POR PRODUCTO (ver _siguiente_numero_movimiento y la
            # restricción única (numero, producto) de la tabla movimiento),
            # así que el que tenía asignado para el producto viejo puede
            # coincidir con uno ya usado por otro movimiento del producto
            # nuevo (ej. "Duplicate entry '1-1037' for key
            # 'movimiento.uq_numero_producto'"). Se recalcula para el
            # producto nuevo.
            movimiento.numero = _siguiente_numero_movimiento(renglon.producto)
    else:
        movimiento = Movimiento(numero=_siguiente_numero_movimiento(renglon.producto))

    movimiento.producto = renglon.producto
    movimiento.fecha = remito.fecha
    movimiento.total = total
    movimiento.unidad_de_medida = renglon.unidad_de_medida
    if remito.es_salida:
        movimiento.entidad_emisor_id = ENTIDAD_PROPIA_ID
        movimiento.entidad_receptor = remito.contraparte
    else:
        movimiento.entidad_emisor = remito.contraparte
        movimiento.entidad_receptor_id = ENTIDAD_PROPIA_ID
    movimiento.save()

    if not renglon.movimiento_id:
        renglon.movimiento = movimiento
        renglon.save(update_fields=['movimiento'])


# ---------------------------------------------------------------------------
# Alta / Modificación / Reportes de Remito (cabecera)
# ---------------------------------------------------------------------------

@transaction.atomic
def remito_form(request, pk=None):
    """Alta y modificación de la cabecera de un Remito (misma vista, pk=None
    para alta)."""
    remito = get_object_or_404(Remito, pk=pk) if pk else None

    if request.method == 'POST':
        form = forms.RemitoForm(request.POST, instance=remito)
        if form.is_valid():
            contraparte = form.cleaned_data['contraparte']
            tipo = form.cleaned_data['tipo']
            punto_venta = form.cleaned_data['punto_venta']
            numero = form.cleaned_data['numero']

            emisor_id = ENTIDAD_PROPIA_ID if tipo == Remito.TIPO_SALIDA else contraparte.id

            # Chequeo manual de unicidad (emisor, punto_venta, numero): no
            # alcanza con la validación automática del ModelForm porque
            # 'emisor' no es un campo del formulario (se arma acá, a partir
            # de 'tipo' + 'contraparte'; ver RemitoForm.contraparte).
            conflicto = Remito.objects.filter(
                emisor_id=emisor_id, punto_venta=punto_venta, numero=numero,
            )
            if remito is not None:
                conflicto = conflicto.exclude(pk=remito.pk)
            if conflicto.exists():
                form.add_error('numero', 'Ya existe un remito con ese punto de venta y número para este emisor.')

            if not form.errors:
                nuevo = form.save(commit=False)
                if tipo == Remito.TIPO_SALIDA:
                    nuevo.emisor_id = ENTIDAD_PROPIA_ID
                    nuevo.receptor = contraparte
                else:
                    nuevo.emisor = contraparte
                    nuevo.receptor_id = ENTIDAD_PROPIA_ID
                nuevo.save()

                observacion_elegida = form.cleaned_data.get('observacion_estandar')
                if observacion_elegida:
                    separador = '\n' if nuevo.observaciones and not nuevo.observaciones.endswith('\n') else ''
                    nuevo.observaciones = f'{nuevo.observaciones}{separador}{observacion_elegida.texto}'
                    nuevo.save(update_fields=['observaciones'])

                if form.cleaned_data.get('guardar_observacion_estandar') and nuevo.observaciones.strip():
                    ObservacionEstandar.objects.get_or_create(texto=nuevo.observaciones.strip())

                messages.success(request, f'Remito {nuevo} guardado correctamente.')
                if remito is None:
                    # Igual que en comprobantes: después de crear la
                    # cabecera se vuelve al alta de renglón con este remito
                    # ya elegido, para poder seguir cargando líneas sin
                    # tener que volver a buscarlo.
                    url_alta = reverse('remitos:remito_renglon_alta')
                    return redirect(f'{url_alta}?remito={nuevo.pk}')
                return redirect('remitos:remito_modificar')
    else:
        contraparte_inicial = remito.contraparte if remito else None
        initial = {'contraparte': contraparte_inicial.id} if contraparte_inicial else {}
        if remito is None:
            # Alta nueva: sugerir como default el punto de venta y el
            # próximo número, tomando como base el último remito que
            # Fontana emitió (tipo Salida -- ahí 'emisor' es siempre
            # Fontana, así que sí hay un talonario propio del que "seguir
            # la numeración"; en los de Entrada el punto de venta/número
            # son del talonario de la OTRA empresa, uno distinto por cada
            # proveedor, así que no hay un "próximo" razonable que
            # adivinar). Es sólo un valor sugerido: se puede cambiar antes
            # de guardar, y la unicidad (emisor, punto_venta, numero) se
            # sigue validando igual al guardar.
            ultimo_propio = Remito.objects.filter(emisor_id=ENTIDAD_PROPIA_ID).order_by('-fecha', '-id').first()
            if ultimo_propio:
                initial['punto_venta'] = ultimo_propio.punto_venta
                initial['numero'] = ultimo_propio.numero + 1
        form = forms.RemitoForm(instance=remito, initial=initial)

    return render(request, 'remitos/remito_form.html', {
        'form': form,
        'remito': remito,
        'modo': 'alta' if remito is None else 'modificar',
        'contraparte_texto': texto_entidad_buscador(remito.contraparte) if remito else '',
        'transportista_texto': texto_entidad_buscador(remito.transportista) if remito else '',
        'chofer_texto': texto_entidad_buscador(remito.chofer, campo_documento='documento_nro') if remito else '',
        'vehiculo_texto': str(remito.vehiculo) if remito and remito.vehiculo_id else '',
        'acoplado_texto': str(remito.acoplado) if remito and remito.acoplado_id else '',
        'renglones_del_remito': remito.renglones.select_related('producto', 'unidad_de_medida').all() if remito else [],
        # 'prefix': VehiculoCrearRapidoForm, AcopladoCrearRapidoForm y
        # EntidadRolRapidoForm (más abajo) comparten nombres de campo entre
        # sí ('nombre', 'patente'): sin un prefijo distinto, Django les
        # arma el mismo id HTML a los dos (ej. 'id_nombre') y el JS de acá
        # abajo (que busca el campo por ese id) termina siempre agarrando
        # el de OTRO de los tres mini-formularios en vez del que
        # corresponde. El prefijo sólo cambia el id/name con el que se
        # RENDERIZAN estos campos; el POST que arma el JS sigue mandando
        # las claves sin prefijo ('nombre', 'patente', etc.), que es lo que
        # esperan vehiculo_crear_rapido/acoplado_crear_rapido/
        # entidad_crear_rapido -- no hace falta tocar esas vistas.
        'vehiculo_crear_form': forms.VehiculoCrearRapidoForm(prefix='vehiculo_crear'),
        'acoplado_crear_form': forms.AcopladoCrearRapidoForm(prefix='acoplado_crear'),
        # Un único mini-formulario de alta rápida de entidad, reusado tanto
        # para transportista como para chofer (ver template: el JS le pone
        # el id de Rol correspondiente en el campo oculto 'rol' según cuál
        # de los dos botones "+ Crear" se haya usado).
        'entidad_rapida_form': EntidadRolRapidoForm(prefix='entidad_rapida'),
        'rol_transportista_id': _rol_id(forms.ROL_TRANSPORTISTA),
        'rol_chofer_id': _rol_id(forms.ROL_CHOFER),
    })


def _rol_id(nombre_rol):
    rol = Rol.objects.filter(nombre=nombre_rol).first()
    return rol.id if rol else ''


def _remitos_filtrados(request):
    """Aplica los filtros de búsqueda usados tanto por el listado/
    modificación como por los reportes de Remito."""
    remitos = Remito.objects.select_related(
        'emisor', 'receptor', 'condicion_venta', 'transportista', 'chofer', 'vehiculo', 'acoplado',
    )

    q = request.GET.get('q', '').strip()
    if q:
        filtro = (
            Q(numero__icontains=q)
            | Q(emisor__nombre__icontains=q)
            | Q(receptor__nombre__icontains=q)
        )
        if q.isdigit():
            filtro |= Q(id=int(q)) | Q(numero=int(q))
        remitos = remitos.filter(filtro)

    tipo = request.GET.get('tipo', '').strip()
    if tipo in (Remito.TIPO_SALIDA, Remito.TIPO_ENTRADA):
        remitos = remitos.filter(tipo=tipo)

    fecha_desde = request.GET.get('fecha_desde', '').strip()
    if fecha_desde:
        remitos = remitos.filter(fecha__gte=fecha_desde)

    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    if fecha_hasta:
        remitos = remitos.filter(fecha__lte=fecha_hasta)

    return remitos.distinct(), q, tipo, fecha_desde, fecha_hasta


def remito_listado(request):
    """Listado/búsqueda de remitos; puerta de entrada de 'Modificación'."""
    remitos, q, tipo, fecha_desde, fecha_hasta = _remitos_filtrados(request)
    remitos = aplicar_orden_queryset(request, remitos, {
        'id': 'id',
        'fecha': 'fecha',
        'numero': 'numero',
    })
    return render(request, 'remitos/remito_listado.html', {
        'remitos': remitos[:500],
        'q': q, 'tipo': tipo, 'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
    })


def remito_eliminar(request, pk):
    remito = get_object_or_404(Remito, pk=pk)
    with transaction.atomic():
        for renglon in remito.renglones.all():
            if renglon.movimiento_id:
                renglon.movimiento.delete()
        remito.delete()
    messages.success(request, f'Remito {remito} eliminado correctamente.')
    return redirect('remitos:remito_modificar')


def remito_reporte(request):
    remitos, q, tipo, fecha_desde, fecha_hasta = _remitos_filtrados(request)
    remitos = aplicar_orden_queryset(request, remitos, {'id': 'id', 'fecha': 'fecha', 'numero': 'numero'})
    return render(request, 'remitos/remito_reporte.html', {
        'remitos': remitos[:500],
        'q': q, 'tipo': tipo, 'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
        'filtros_activos': bool(q or tipo or fecha_desde or fecha_hasta),
    })


def _filas_reporte_remito(remitos):
    columnas = ['ID', 'Fecha', 'Tipo', 'Punto Venta', 'Número', 'Emisor', 'Receptor', 'Transportista', 'Vehículo', 'Valor declarado']
    filas = [
        [
            r.id,
            r.fecha,
            'Salida' if r.tipo == Remito.TIPO_SALIDA else 'Entrada',
            r.punto_venta,
            r.numero,
            str(r.emisor) if r.emisor_id else '-',
            str(r.receptor) if r.receptor_id else '-',
            str(r.transportista) if r.transportista_id else '-',
            str(r.vehiculo) if r.vehiculo_id else '-',
            r.valor_declarado if r.valor_declarado is not None else '-',
        ]
        for r in remitos
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': {9},
        'anchos': [0.6, 1.0, 0.8, 1.0, 1.0, 2.0, 2.0, 2.0, 1.4, 1.2],
    }


def remito_reporte_excel(request):
    remitos, *_ = _remitos_filtrados(request)
    return excel_response('remitos', _filas_reporte_remito(remitos))


def remito_reporte_pdf(request):
    remitos, *_ = _remitos_filtrados(request)
    return pdf_response('remitos', 'Remitos', _filas_reporte_remito(remitos))


def remito_entidad_buscar(request):
    """Buscador de 'Cliente / Proveedor' (contraparte) del alta de Remito:
    sin filtro de rol, cualquier entidad. Se reexpone acá (en vez de usar
    directamente entidades:entidad_buscar desde el template) sólo para que
    la URL quede agrupada bajo el namespace de remitos; la lógica es la
    misma."""
    from entidades.views import entidad_buscar
    return entidad_buscar(request)


# ---------------------------------------------------------------------------
# Impresión de un Remito (pensada para talonario A4 preimpreso: NO se
# imprime punto de venta ni número, porque ya vienen impresos en el papel).
#
# Las constantes de acá abajo son a propósito fáciles de ajustar: la
# calibración exacta depende de una impresión de prueba sobre el papel real
# del talonario, así que se dejan como simples números en milímetros para
# poder retocarlas sin tener que entender el resto del código.
# ---------------------------------------------------------------------------

# Posición (desde el borde superior izquierdo de la hoja A4) de cada dato,
# en milímetros: (x, y).
POSICION_FECHA = (140, 40)
POSICION_CONTRAPARTE_NOMBRE = (20, 55)
POSICION_CONTRAPARTE_DIRECCION = (20, 61)
POSICION_CONTRAPARTE_LOCALIDAD = (20, 67)
POSICION_CONDICION_VENTA = (140, 55)
POSICION_TRANSPORTISTA = (20, 78)
POSICION_CHOFER = (20, 84)
POSICION_VEHICULO_ACOPLADO = (20, 90)
# Tabla de renglones: arranca en (X0, Y0) y cada fila baja ALTO_FILA mm.
TABLA_X0 = 20
TABLA_Y0 = 105
TABLA_ALTO_FILA = 7
TABLA_ANCHOS_COLUMNAS = [80, 30, 20, 25, 25]  # Producto, Detalle, Cant., Kg. enviados, Kg. confirmados
POSICION_VALOR_DECLARADO = (140, 250)
POSICION_OBSERVACIONES = (20, 260)


def remito_imprimir_pdf(request, pk):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from django.http import HttpResponse

    remito = get_object_or_404(Remito, pk=pk)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=remito_{remito.pk}.pdf'

    alto_hoja = A4[1]

    def y_desde_arriba(mm_desde_arriba):
        return alto_hoja - (mm_desde_arriba * mm)

    c = canvas.Canvas(response, pagesize=A4)
    c.setFont('Helvetica', 9)

    def escribir(posicion_mm, texto):
        x, y = posicion_mm
        c.drawString(x * mm, y_desde_arriba(y), texto)

    escribir(POSICION_FECHA, remito.fecha.strftime('%d/%m/%Y') if remito.fecha else '')

    contraparte = remito.contraparte
    if contraparte:
        escribir(POSICION_CONTRAPARTE_NOMBRE, texto_entidad_buscador(contraparte))
        escribir(POSICION_CONTRAPARTE_DIRECCION, contraparte.direccion or '')
        localidad = ', '.join(filter(None, [contraparte.localidad, contraparte.provincia]))
        escribir(POSICION_CONTRAPARTE_LOCALIDAD, localidad)

    if remito.condicion_venta_id:
        escribir(POSICION_CONDICION_VENTA, f'Cond. de venta: {remito.condicion_venta.nombre}')

    if remito.transportista_id:
        escribir(POSICION_TRANSPORTISTA, f'Transportista: {texto_entidad_buscador(remito.transportista)}')
    if remito.chofer_id:
        escribir(POSICION_CHOFER, f'Chofer: {texto_entidad_buscador(remito.chofer)}')
    vehiculo_acoplado = ' / '.join(filter(None, [str(remito.vehiculo) if remito.vehiculo_id else '', str(remito.acoplado) if remito.acoplado_id else '']))
    if vehiculo_acoplado:
        escribir(POSICION_VEHICULO_ACOPLADO, f'Vehículo: {vehiculo_acoplado}')

    # --- Tabla de renglones ---
    c.setFont('Helvetica-Bold', 8)
    encabezados = ['Producto', 'Detalle', 'Cantidad', 'Kg. enviados', 'Kg. confirmados']
    x = TABLA_X0
    for encabezado, ancho in zip(encabezados, TABLA_ANCHOS_COLUMNAS):
        c.drawString(x * mm, y_desde_arriba(TABLA_Y0), encabezado)
        x += ancho
    c.setFont('Helvetica', 8)

    fila_y = TABLA_Y0 + TABLA_ALTO_FILA
    for renglon in remito.renglones.select_related('producto').order_by('orden', 'id'):
        valores = [
            str(renglon.producto),
            renglon.detalle_adicional or '',
            f'{renglon.cantidad}' if renglon.cantidad is not None else '',
            f'{renglon.kilogramos_enviados}',
            f'{renglon.kilogramos_confirmados}' if renglon.kilogramos_confirmados is not None else '',
        ]
        x = TABLA_X0
        for valor, ancho in zip(valores, TABLA_ANCHOS_COLUMNAS):
            c.drawString(x * mm, y_desde_arriba(fila_y), valor)
            x += ancho
        fila_y += TABLA_ALTO_FILA

    if remito.valor_declarado is not None:
        escribir(POSICION_VALOR_DECLARADO, f'Valor declarado: {remito.valor_declarado}')

    if remito.observaciones:
        c.setFont('Helvetica', 8)
        x, y = POSICION_OBSERVACIONES
        for linea in remito.observaciones.splitlines() or ['']:
            c.drawString(x * mm, y_desde_arriba(y), linea)
            y += 5

    c.showPage()
    c.save()
    return response


def remito_imprimir_excel(request, pk):
    remito = get_object_or_404(Remito, pk=pk)
    columnas = ['Producto', 'Detalle', 'Cantidad', 'Unidad', 'Kg. enviados', 'Kg. confirmados']
    filas = [
        [
            str(r.producto),
            r.detalle_adicional or '-',
            r.cantidad if r.cantidad is not None else '-',
            r.unidad_de_medida.nombre if r.unidad_de_medida_id else '-',
            r.kilogramos_enviados,
            r.kilogramos_confirmados if r.kilogramos_confirmados is not None else '-',
        ]
        for r in remito.renglones.select_related('producto', 'unidad_de_medida').order_by('orden', 'id')
    ]
    resultado = {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': {2, 4, 5},
        'anchos': [3, 2, 1, 1, 1.2, 1.2],
    }
    return excel_response(f'remito_{remito.pk}', resultado)


# ---------------------------------------------------------------------------
# Alta / Modificación / Reportes de RemitoRenglon
# ---------------------------------------------------------------------------

def remito_renglon_remito_buscar(request):
    """Buscador de Remito, usado por el alta/modificación de RemitoRenglon
    (mismo patrón que comprobante_renglon_comprobante_buscar en
    comprobantes/views.py)."""
    q = request.GET.get('q', '').strip()
    resultados = []
    if q:
        remitos = Remito.objects.select_related('emisor', 'receptor')
        filtro = Q(numero__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q)) | Q(numero=int(q))
        remitos = remitos.filter(filtro).order_by('-fecha', '-id')[:20]
        resultados = [{'id': r.id, 'text': _texto_remito(r)} for r in remitos]
    return JsonResponse({'resultados': resultados})


@transaction.atomic
def remito_renglon_form(request, pk=None):
    """Alta y modificación de un RemitoRenglon (misma vista, pk=None para
    alta). Mismo patrón de pantalla que comprobante_renglon_form (ver
    comprobantes/views.py): el remito se elige primero con un buscador y, al
    elegirlo en el alta, la página se recarga con ?remito=<id> ya
    precargado, mostrando de una los renglones que ya tiene."""
    renglon = get_object_or_404(RemitoRenglon, pk=pk) if pk else None

    remito_preseleccionado = None
    if renglon is None:
        remito_id_qs = request.GET.get('remito', '').strip()
        if remito_id_qs.isdigit():
            remito_preseleccionado = Remito.objects.select_related('emisor', 'receptor').filter(pk=remito_id_qs).first()

    if request.method == 'POST':
        form = forms.RemitoRenglonForm(request.POST, instance=renglon)
        if form.is_valid():
            nuevo = form.save(commit=False)
            if renglon is None:
                ultimo_orden = RemitoRenglon.objects.filter(remito=nuevo.remito).aggregate(Max('orden'))['orden__max'] or 0
                nuevo.orden = ultimo_orden + 1
            nuevo.save()
            _sincronizar_movimiento_renglon(nuevo)

            messages.success(request, f'Renglón de remito {nuevo.id} guardado correctamente.')
            url_alta = reverse('remitos:remito_renglon_alta')
            return redirect(f'{url_alta}?remito={nuevo.remito_id}')
    else:
        initial = {'remito': remito_preseleccionado.id} if remito_preseleccionado else None
        form = forms.RemitoRenglonForm(instance=renglon, initial=initial)

    remito_para_texto = renglon.remito if renglon else remito_preseleccionado

    renglones_del_remito = []
    if remito_para_texto is not None:
        renglones_qs = remito_para_texto.renglones.select_related('producto', 'unidad_de_medida').order_by('orden', 'id')
        if renglon is not None:
            renglones_qs = renglones_qs.exclude(pk=renglon.pk)
        renglones_del_remito = list(renglones_qs)

    return render(request, 'remitos/remito_renglon_form.html', {
        'form': form,
        'renglon': renglon,
        'remito_texto': _texto_remito(remito_para_texto),
        'remito_seleccionado': remito_para_texto,
        'renglones_del_remito': renglones_del_remito,
        'producto_texto': _texto_producto(renglon.producto) if renglon else '',
        'producto_crear_form': forms.ProductoDetalleCrearForm(),
    })


def remito_renglon_listado(request):
    renglones = RemitoRenglon.objects.select_related('remito', 'producto').order_by('-remito__fecha', '-remito_id', 'orden')

    q_id = request.GET.get('id', '').strip()
    if q_id.isdigit():
        renglones = renglones.filter(pk=int(q_id))

    q_remito = request.GET.get('remito', '').strip()
    if q_remito.isdigit():
        renglones = renglones.filter(remito_id=int(q_remito))

    return render(request, 'remitos/remito_renglon_listado.html', {
        'renglones': renglones[:500],
        'q_id': q_id, 'q_remito': q_remito,
    })


def remito_renglon_eliminar(request, pk):
    renglon = get_object_or_404(RemitoRenglon, pk=pk)
    remito_id = renglon.remito_id
    with transaction.atomic():
        if renglon.movimiento_id:
            renglon.movimiento.delete()
        renglon.delete()
    messages.success(request, 'Renglón de remito eliminado correctamente.')
    return redirect(f"{reverse('remitos:remito_renglon_modificar')}?remito={remito_id}")


# ---------------------------------------------------------------------------
# Catálogos: Vehículo
# ---------------------------------------------------------------------------

def vehiculo_alta(request):
    if request.method == 'POST':
        form = forms.VehiculoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehículo creado correctamente.')
            return redirect('remitos:vehiculo_listado')
    else:
        form = forms.VehiculoForm(initial={'activo': True})
    return render(request, 'remitos/vehiculo_form.html', {'form': form, 'modo': 'alta'})


def vehiculo_listado(request):
    vehiculos = Vehiculo.objects.order_by('nombre')
    q = request.GET.get('q', '').strip()
    if q:
        vehiculos = vehiculos.filter(Q(nombre__icontains=q) | Q(patente__icontains=q))
    return render(request, 'remitos/vehiculo_listado.html', {'vehiculos': vehiculos, 'q': q})


def vehiculo_editar(request, pk):
    vehiculo = get_object_or_404(Vehiculo, pk=pk)
    if request.method == 'POST':
        form = forms.VehiculoForm(request.POST, instance=vehiculo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehículo modificado correctamente.')
            return redirect('remitos:vehiculo_listado')
    else:
        form = forms.VehiculoForm(instance=vehiculo)
    return render(request, 'remitos/vehiculo_form.html', {'form': form, 'modo': 'modificar', 'vehiculo': vehiculo})


def vehiculo_buscar(request):
    q = request.GET.get('q', '').strip()
    resultados = []
    if q:
        vehiculos = Vehiculo.objects.filter(Q(nombre__icontains=q) | Q(patente__icontains=q), activo=True).order_by('nombre')[:20]
        resultados = [{'id': v.id, 'text': str(v)} for v in vehiculos]
    return JsonResponse({'resultados': resultados})


@transaction.atomic
def vehiculo_crear_rapido(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    form = forms.VehiculoCrearRapidoForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errores': form.errors.get_json_data()}, status=400)
    nuevo = form.save()
    return JsonResponse({'id': nuevo.id, 'text': str(nuevo)})


# ---------------------------------------------------------------------------
# Catálogos: Acoplado
# ---------------------------------------------------------------------------

def acoplado_alta(request):
    if request.method == 'POST':
        form = forms.AcopladoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Acoplado creado correctamente.')
            return redirect('remitos:acoplado_listado')
    else:
        form = forms.AcopladoForm(initial={'activo': True})
    return render(request, 'remitos/acoplado_form.html', {'form': form, 'modo': 'alta'})


def acoplado_listado(request):
    acoplados = Acoplado.objects.order_by('patente')
    q = request.GET.get('q', '').strip()
    if q:
        acoplados = acoplados.filter(patente__icontains=q)
    return render(request, 'remitos/acoplado_listado.html', {'acoplados': acoplados, 'q': q})


def acoplado_editar(request, pk):
    acoplado = get_object_or_404(Acoplado, pk=pk)
    if request.method == 'POST':
        form = forms.AcopladoForm(request.POST, instance=acoplado)
        if form.is_valid():
            form.save()
            messages.success(request, 'Acoplado modificado correctamente.')
            return redirect('remitos:acoplado_listado')
    else:
        form = forms.AcopladoForm(instance=acoplado)
    return render(request, 'remitos/acoplado_form.html', {'form': form, 'modo': 'modificar', 'acoplado': acoplado})


def acoplado_buscar(request):
    q = request.GET.get('q', '').strip()
    vehiculo_id = request.GET.get('vehiculo', '').strip()
    resultados = []
    if q:
        acoplados = Acoplado.objects.filter(patente__icontains=q, activo=True)
        if vehiculo_id.isdigit():
            vehiculo = Vehiculo.objects.filter(pk=vehiculo_id).first()
            if vehiculo is not None and vehiculo.acoplados_habituales.exists():
                # El vehículo tiene acoplados vinculados (ver
                # Vehiculo.acoplados_habituales, en models.py): el buscador
                # sólo ofrece esos. Si no tiene ninguno vinculado, se busca
                # entre todos los acoplados activos, como antes.
                acoplados = acoplados.filter(pk__in=vehiculo.acoplados_habituales.values('pk'))
        acoplados = acoplados.order_by('patente')[:20]
        resultados = [{'id': a.id, 'text': str(a)} for a in acoplados]
    return JsonResponse({'resultados': resultados})


@transaction.atomic
def acoplado_crear_rapido(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    form = forms.AcopladoCrearRapidoForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errores': form.errors.get_json_data()}, status=400)
    nuevo = form.save()
    return JsonResponse({'id': nuevo.id, 'text': str(nuevo)})


# ---------------------------------------------------------------------------
# Catálogos: Condición de venta
# ---------------------------------------------------------------------------

def condicion_venta_alta(request):
    if request.method == 'POST':
        form = forms.CondicionVentaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Condición de venta creada correctamente.')
            return redirect('remitos:condicion_venta_listado')
    else:
        form = forms.CondicionVentaForm(initial={'activa': True})
    return render(request, 'remitos/condicion_venta_form.html', {'form': form, 'modo': 'alta'})


def condicion_venta_listado(request):
    condiciones = CondicionVenta.objects.order_by('nombre')
    q = request.GET.get('q', '').strip()
    if q:
        condiciones = condiciones.filter(nombre__icontains=q)
    return render(request, 'remitos/condicion_venta_listado.html', {'condiciones': condiciones, 'q': q})


def condicion_venta_editar(request, pk):
    condicion = get_object_or_404(CondicionVenta, pk=pk)
    if request.method == 'POST':
        form = forms.CondicionVentaForm(request.POST, instance=condicion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Condición de venta modificada correctamente.')
            return redirect('remitos:condicion_venta_listado')
    else:
        form = forms.CondicionVentaForm(instance=condicion)
    return render(request, 'remitos/condicion_venta_form.html', {'form': form, 'modo': 'modificar', 'condicion': condicion})


# ---------------------------------------------------------------------------
# Catálogos: Observación estándar
# ---------------------------------------------------------------------------

def observacion_alta(request):
    if request.method == 'POST':
        form = forms.ObservacionEstandarForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Observación estándar creada correctamente.')
            return redirect('remitos:observacion_listado')
    else:
        form = forms.ObservacionEstandarForm(initial={'activa': True})
    return render(request, 'remitos/observacion_form.html', {'form': form, 'modo': 'alta'})


def observacion_listado(request):
    observaciones = ObservacionEstandar.objects.order_by('texto')
    q = request.GET.get('q', '').strip()
    if q:
        observaciones = observaciones.filter(texto__icontains=q)
    return render(request, 'remitos/observacion_listado.html', {'observaciones': observaciones, 'q': q})


def observacion_editar(request, pk):
    observacion = get_object_or_404(ObservacionEstandar, pk=pk)
    if request.method == 'POST':
        form = forms.ObservacionEstandarForm(request.POST, instance=observacion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Observación estándar modificada correctamente.')
            return redirect('remitos:observacion_listado')
    else:
        form = forms.ObservacionEstandarForm(instance=observacion)
    return render(request, 'remitos/observacion_form.html', {'form': form, 'modo': 'modificar', 'observacion': observacion})
