from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from .models import ComprobanteRenglon, Comprobante, ComprobanteRenglonDetalle
from entidades.models import Entidad
from productos.models import ProductoDetalle
from django.views.generic import DetailView, UpdateView
from decimal import Decimal
from . import forms
from services import gestorexcel
from services.buscadores import texto_entidad_buscador
from services.ordenamiento import aplicar_orden_queryset, aplicar_orden_lista
from services.reportes import excel_response, pdf_response
from django.db.models import Sum, Count, Max, Q, F, Case, When, DecimalField, CharField, Value
from django.db.models.functions import Coalesce, Cast


# Id de la entidad "Fontana S.A." (la empresa), para poder excluirla del
# ranking de entidades cuando corresponda. Mismo criterio (y mismo id) que
# liquidaciones.views.ENTIDAD_PROPIA_ID y movimientos_caja.views.ENTIDAD_PROPIA_ID.
ENTIDAD_PROPIA_ID = 100


def buscar_comprobantes_por_fechas_y_entidad(request):
    if request.method == 'POST':
        # Vinculamos los datos del usuario al formulario
        form = forms.BuscarComprobanteEntreFechasPorEntidadForm(request.POST)
        if form.is_valid():
            # Procesar los datos limpios (form.cleaned_data)
            # O guardar directamente si es un ModelForm 
            comprobantes = filtrar_comprobantes(request)
            comprobantes_renglon = filtrar_comprobantes_renglones(request)
            nombre_hoja = f"{request.POST.get('emisor')} Desde {request.POST.get('fecha_desde')} - Hasta {request.POST.get('fecha_hasta')} "
            if comprobantes:
                tipo_accion = request.POST.get('accion')
                if tipo_accion=='Generar Excel':
                    return generar_reporte_excel_comprobante_y_renglones_simple(nombre_hoja,comprobantes,comprobantes_renglon)
            """
            movimientos = filtrar_movimientos(request)
            comprobantes_renglon = filtrar_comprobantes_renglones(request)
            if movimientos or comprobantes_renglon:
                tipo_accion = request.POST.get('accion')
                if tipo_accion=='Generar Excel':
                    return generar_vinculo_movimientos_comprobantes(nombre_hoja,movimientos,comprobantes_renglon)
                    
            """
        
    else:
        print("CONSOLA ENTRA")
        # Formulario vacío inicial
        form = forms.BuscarComprobanteEntreFechasPorEntidadForm()
    return render(request, 'comprobantes/buscar_por_entidad_emisor_entre_fechas.html', {'form': form})
    
# Create your views here.
def buscar_comprobante_renglon_para_movimiento(request):
    from .forms import BuscarRenglonComprobanteForm
    if request.method == 'POST':
        # Vinculamos los datos del usuario al formulario
        form = BuscarRenglonComprobanteForm(request.POST)

        if form.is_valid():
            # Procesar los datos limpios (form.cleaned_data)
            # O guardar directamente si es un ModelForm
            id_movimiento = request.POST.get('id_movimiento')
            numero = request.POST.get('numero')

            contexto = None
            if id_movimiento:
                contexto={'renglones_comprobantes': ComprobanteRenglon.objects.filter(id_movimiento=id_movimiento)}
            elif numero:
                    contexto = {'renglones_comprobantes': ComprobanteRenglon.objects.filter(numero=numero)}
            else:
                producto = request.POST.get('producto')
                renglones_comprobantes = ComprobanteRenglon.objects.all()
                if producto:
                    renglones_comprobantes = renglones_comprobantes.filter(producto=producto)
                entidad_emisor = request.POST.get('emisor')
                if entidad_emisor:
                    renglones_comprobantes = renglones_comprobantes.filter(comprobante__entidad_emisor__id=entidad_emisor)
                """
                receptor = request.POST.get('receptor')
                if receptor:
                    renglones_comprobantes = renglones_comprobantes.filter(comprobante__entidad_receptor=receptor)
                """
                fecha_desde = request.POST.get('fecha_desde')
                if fecha_desde:
                    renglones_comprobantes = renglones_comprobantes.filter(comprobante__fecha__gte=fecha_desde)#mayor o igual
                fecha_hasta = request.POST.get('fecha_hasta')
                if fecha_hasta:
                    renglones_comprobantes = renglones_comprobantes.filter(comprobante__fecha__lte=fecha_hasta)  # menor o igual
                if renglones_comprobantes:
                    contexto = {'renglones_comprobantes': renglones_comprobantes,'form':form}
                for obj in renglones_comprobantes:
                    obj.comprobante = Comprobante.objects.get(id=obj.comprobante_id)
                    detalle = ComprobanteRenglonDetalle.objects.get(comprobante_renglon_id=obj.id)
                    if detalle:
                        obj.detalle = detalle 
                    
            if contexto:
                return render(
                    request,
                    'listado_renglones.html',
                    context=contexto)


            #redirect('renglones_comprobantes:listado_movimiento')
    else:
        print("CONSOLA ENTRA")
        # Formulario vacío inicial
        form = BuscarRenglonComprobanteForm()

    
    return render(request, 'renglones_comprobantes.html', {'form': form})
def remove_renglon_comprobante(request):
    pass
    #si el objeto no existe no se lanza una excepcion, si no error 404
    """
    movimiento = get_object_or_404(Movimiento,pk=request.POST.get('movimiento_id'))
    movimiento.delete()

    return redirect('movimientos:buscar_movimiento_2')
    """
class RenglonComprobanteUpdateView(UpdateView):
    pass

def generar_excel_completo(request):
    import openpyxl
    from django.http import HttpResponse
    from openpyxl.styles import NamedStyle

     # 1. Crear un libro de trabajo y una hoja
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte de Datos"

    # 2. Agregar encabezados
    columnas = ['ID', 'Numero', 'Fecha','Producto','ID Emisor','Op Inym Emisor','Emisor','ID Receptor','Op Inym Receptor','Receptor','Bruto','Tara','Descuento','Total']
    ws.append(columnas)

    # 3. Obtener los datos (por ejemplo, desde un modelo)
    datos = ComprobanteRenglon.objects.all().select_related('movimiento_pesaje').values_list('id_movimiento','numero','fecha','producto__nombre',
                                                                                     'entidad_emisor__id','movimientohvyerbamate__inym_operador_origen__id','entidad_emisor__nombre',
                                                                                     'entidad_receptor__id','movimientohvyerbamate__inym_operador_destino__id','entidad_receptor__nombre','movimiento_pesaje__bruto','movimiento_pesaje__tara','movimiento_pesaje__descuento','total')

    for fila in datos:
        ws.append(fila)
    #le doy formato de fecha a la celda del date
    # Create the style
    date_style = NamedStyle(name="custom_date", number_format="DD/MM/YYYY")
    wb.add_named_style(date_style)

# Apply it to the column cells en este caso la columna es la C
    for cell in ws["C"]:
        if cell.row == 1:
            continue  # Skip header
        cell.style = date_style

     # 4. Preparar la respuesta HTTP para descargar el archivo
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    response['Content-Disposition'] = 'attachment; filename=reporte.xlsx'

    # 5. Guardar el libro en la respuesta
    wb.save(response)
    return response

def vista_buscar_renglones_comprobantes(request):
    from .forms import BuscarSaldoProductoEntidadForm
    if request.method == 'POST':
        # Vinculamos los datos del usuario al formulario
        form = BuscarSaldoProductoEntidadForm(request.POST)
        if form.is_valid():
            # Procesar los datos limpios (form.cleaned_data)
            # O guardar directamente si es un ModelForm 
            comprobantes_renglon = filtrar_comprobantes_renglones(request)
            nombre_hoja = f"{request.POST.get('emisor')} - {request.POST.get('producto')}"
            if comprobantes_renglon:
                tipo_accion = request.POST.get('accion')
                if tipo_accion=='Generar Excel':
                    return generar_renglones_comprobantes(nombre_hoja,comprobantes_renglon)
                    
            
            #redirect('movimientos:listado_movimiento')
    else:
        print("CONSOLA ENTRA")
        # Formulario vacío inicial
        form = BuscarSaldoProductoEntidadForm()


    return render(request, 'movimientos/producto_por_entidad_buscar_saldo.html', {'form': form})

def generar_renglones_comprobantes(nombre_hoja,comprobantes_renglones):
    from openpyxl.styles import NamedStyle
    from services import gestorexcel
    wb = gestorexcel.crear_excel()
    ws = wb.active
    ws.title = "Reporte de Datos"

    wb = generar_hoja_excel_renglones_comprobantes(wb,nombre_hoja,comprobantes_renglones)
    #le doy formato de fecha a la celda del date
    # Create the style
    date_style = NamedStyle(name="custom_date", number_format="DD/MM/YYYY")
    wb.add_named_style(date_style)

    # Apply it to the column cells en este caso la columna es la C
    for cell in ws["C"]:
        if cell.row == 1:
            continue  # Skip header
        cell.style = date_style

        # 4. Preparar la respuesta HTTP para descargar el archivo
    response = gestorexcel.crear_response_excel()
    # 5. Guardar el libro en la respuesta
    wb.save(response)
    return response

def generar_hoja_excel_renglones_comprobantes(wb,nombre_hoja,comprobantes_renglones):
    ws = wb.create_sheet(title=f"Vinculos comprobantes y movimientos {nombre_hoja}")
    columnas = ['Tipo','Tipo Comprobante', 'Id', 'Fecha','P.de Venta','Número','Producto','U.de Medida','Debe','Haber','Saldo']
    ws.append(columnas)
    comprobantes_renglones = comprobantes_renglones.select_related('comprobante_renglon_detalle').values_list('comprobante_id','tipo_comprobante__nombre','comprobante__fecha','comprobante__punto_de_venta',
                                                                                                                                                        'comprobante__numero','producto__nombre','renglon_detalle_comprobante__unidad_de_medida__nombre',
                                                                                                                        'renglon_detalle_comprobante__cantidad').order_by('comprobante__fecha','id').order_by('comprobante__fecha','id')
    lista_completa = []

    for fila in comprobantes_renglones:
        fila = list(fila)
        fila.insert(0,'Renglón de comprobante')
        fila.insert(9,float(0))
        lista_completa.append(fila)
    #ordeno por fecha y ahi recién hago saldo
    lista_completa = sorted(lista_completa, key=lambda x: x[2]) #indice de fecha es el 2
    saldo=0
    for renglon in lista_completa:
        # si es IVa no tiene cantidad entonces comprobar para que no sea None
        if renglon[7]!=None:
            saldo+=Decimal(renglon[8])-Decimal(renglon[7])
        else:
            saldo+=Decimal(renglon[8])
        renglon.insert(9,saldo)
        ws.append(renglon)
    return wb

def filtrar_comprobantes_renglones(request):
    producto = request.POST.get('producto')
    if producto:
        comprobantes_renglon = ComprobanteRenglon.objects.filter(producto=producto)
    else:
        comprobantes_renglon = ComprobanteRenglon.objects.all()
    fecha_desde = request.POST.get('fecha_desde')
    if fecha_desde:
        comprobantes_renglon = comprobantes_renglon.filter(comprobante__fecha__gte=fecha_desde)#mayor o igual
    fecha_hasta = request.POST.get('fecha_hasta')
    if fecha_hasta:
        comprobantes_renglon = comprobantes_renglon.filter(comprobante__fecha__lte=fecha_hasta)#menor o igual
    entidad_emisor = request.POST.get('emisor')
    if entidad_emisor:
       comprobantes_renglon = comprobantes_renglon.filter(comprobante__entidad_emisor=entidad_emisor)
    return comprobantes_renglon

def filtrar_comprobantes(request):
    producto = request.POST.get('producto')
    if producto:
        comprobantes= Comprobante.objects.filter(renglon_comprobante__producto=producto) #va nombre del related name
    else:
        comprobantes= Comprobante.objects.all()
    fecha_desde = request.POST.get('fecha_desde')
    if fecha_desde:
        comprobantes = comprobantes.filter(fecha__gte=fecha_desde)#mayor o igual
    fecha_hasta = request.POST.get('fecha_hasta')
    if fecha_hasta:
        comprobantes = comprobantes.filter(fecha__lte=fecha_hasta)#menor o igual
    entidad_emisor = request.POST.get('emisor')
    if entidad_emisor:
       comprobantes= comprobantes.filter(entidad_emisor=entidad_emisor)
    return comprobantes


def buscar_comprobantes_por_entidad():
    pass

def generar_reporte_excel_comprobante_y_renglones_simple(nombre_hoja,comprobantes,comprobantes_renglones):
    wb = gestorexcel.crear_excel()
    wb = crear_hoja_renglones_comprobantes_simple(wb,nombre_hoja,comprobantes_renglones)
    wb = crear_hoja_comprobantes_simple(wb,nombre_hoja,comprobantes)
    wb = crear_hoja_relacion_comprobantes_con_renglones(wb,'Vinculos comprobantes renglones',comprobantes)
        # 4. Preparar la respuesta HTTP para descargar el archivo
    response = gestorexcel.crear_response_excel()
    # 5. Guardar el libro en la respuesta
    wb.save(response)
    return response

def crear_hoja_renglones_comprobantes_simple(wb,nombre_hoja,comprobantes_renglones):
    ws = wb.create_sheet(title=f"Renglones Comp. {nombre_hoja}")
    columnas = ['Id','Fecha','Comprobante ID','P.de Venta','Número','Producto','U.de Medida','Cantidad','Precio Unitario','Bonificación','Total $']
    ws.append(columnas)
    comprobantes_renglones = comprobantes_renglones.select_related('comprobante_renglon_detalle').values_list('id','comprobante__fecha','comprobante_id',
                                                                                                              'comprobante__punto_de_venta','comprobante__numero',
                                                                                                              'producto__nombre','renglon_detalle_comprobante__unidad_de_medida__nombre',
                                                                                                                        'renglon_detalle_comprobante__cantidad','renglon_detalle_comprobante__precio_unitario',
                                                                                                                        'renglon_detalle_comprobante__bonificacion','total').order_by('comprobante__fecha','id')
    lista_completa = []

    for fila in comprobantes_renglones:
        lista_completa.append(list(fila))
    #ordeno por fecha y ahi recién hago saldo
    lista_completa = sorted(lista_completa, key=lambda x: x[2]) #indice de fecha es el 2
    for renglon in lista_completa:
        ws.append(renglon)
    #le doy formato de fecha a la celda del date
    # Create the style
    ws = gestorexcel.formatear_celda_numero(ws,'H')
    ws = gestorexcel.formatear_celda_numero(ws,'I')
    ws = gestorexcel.formatear_celda_numero(ws,'J')
    ws = gestorexcel.formatear_celda_numero(ws,'K')
    ws = gestorexcel.definir_estilo_general(ws)
    wb = gestorexcel.formatear_celda_fecha(wb,ws,"B")
    return wb


def crear_hoja_comprobantes_simple(wb,nombre_hoja,comprobantes):
    ws = wb.create_sheet(title=f"Comprobantes {nombre_hoja}")
    columnas = ['Id','Fecha','Emisor','Tipo Comp.','P.de Venta','Número','Total $']
    ws.append(columnas)
    comprobantes = comprobantes.values_list('id','fecha','entidad_emisor','tipo_comprobante__nombre',
                                                                'punto_de_venta','numero','total').order_by('fecha','id')
    lista_completa = []

    for fila in comprobantes:
        lista_completa.append(list(fila))
    #ordeno por fecha y ahi recién hago saldo
    lista_completa = sorted(lista_completa, key=lambda x: x[2]) #indice de fecha es el 2
    for renglon in lista_completa:
        ws.append(renglon)
    #le doy formato de fecha a la celda del date
    # Create the style
    wb = gestorexcel.formatear_celda_fecha(wb,ws,"B")
    ws = gestorexcel.formatear_celda_numero(ws,'G')
    ws = gestorexcel.definir_estilo_general(ws)
    return wb

def crear_hoja_relacion_comprobantes_con_renglones(wb,nombre_hoja,comprobantes):
    from django.db.models.functions import Cast
    from django.db.models import DecimalField
    ws = wb.create_sheet(title=f"Comprobantes {nombre_hoja}")
    columnas = ['Id.Comprobante','IDs Renglones','Total Comp.','Total Rengl.','Diferencia']
    ws.append(columnas)
    for comprobante in comprobantes:
        id = comprobante.id
        ids_renglones = comprobantes.values_list('renglon_comprobante__id',flat=True).filter(id=id)
        ids_renglones_texto = ", ".join(map(str, list(ids_renglones)))
        ##esto me devuelve un diccionario
        total_renglones = comprobantes.filter(id=id).aggregate(total_renglones=Cast(Sum("renglon_comprobante__total"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ))
        total_renglones=total_renglones["total_renglones"]
        ws.append([id,ids_renglones_texto,comprobante.total,total_renglones,comprobante.total-total_renglones])

    #ordeno por fecha y ahi recién hago saldo
   
    #le doy formato de fecha a la celda del date
    # Create the style
    ws = gestorexcel.formatear_celda_numero(ws,'C')
    ws = gestorexcel.formatear_celda_numero(ws,'D')
    ws = gestorexcel.formatear_celda_numero(ws,'E')
    ws = gestorexcel.definir_estilo_general(ws)
    return wb


# ---------------------------------------------------------------------------
# Alta / Modificar / Reportes de Comprobante
# ---------------------------------------------------------------------------

def _siguiente_id_comprobante():
    ultimo = Comprobante.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


def comprobante_entidad_buscar(request):
    """
    Devuelve, en JSON, hasta 20 entidades cuyo nombre o CUIT contengan el
    texto buscado, o cuyo ID coincida exactamente (si lo buscado es
    numérico). Usado por el buscador de entidad del alta/modificación de
    Comprobante.
    """
    q = request.GET.get('q', '').strip()
    resultados = []

    if len(q) >= 2:
        filtro = Q(nombre__icontains=q) | Q(cuit__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))
        entidades = Entidad.objects.filter(filtro).order_by('nombre')[:20]
        resultados = [
            {
                'id': ent.id,
                'text': f'{ent.nombre} (CUIT {ent.cuit})' if ent.cuit else ent.nombre,
            }
            for ent in entidades
        ]

    return JsonResponse({'resultados': resultados})


@transaction.atomic
def comprobante_form(request, pk=None):
    """Alta y modificación de un Comprobante (misma vista, pk=None para alta)."""
    comprobante = get_object_or_404(Comprobante, pk=pk) if pk else None

    if request.method == 'POST':
        form = forms.ComprobanteForm(request.POST, instance=comprobante)
        if form.is_valid():
            nuevo = form.save(commit=False)
            if comprobante is None:
                nuevo.id = _siguiente_id_comprobante()
            nuevo.save()
            messages.success(request, f'Comprobante {nuevo.id} guardado correctamente.')
            return redirect('comprobantes:comprobante_modificar')
    else:
        form = forms.ComprobanteForm(instance=comprobante)

    # Texto a mostrar en el buscador de entidad: la entidad ya elegida
    # (edición), o la que quedó tipeada en un POST inválido.
    entidad_emisor_id = form['entidad_emisor'].value()
    entidad_actual = Entidad.objects.filter(pk=entidad_emisor_id).first() if entidad_emisor_id else None
    entidad_texto = ''
    if entidad_actual:
        entidad_texto = (
            f'{entidad_actual.nombre} (CUIT {entidad_actual.cuit})'
            if entidad_actual.cuit else entidad_actual.nombre
        )

    return render(request, 'comprobantes/comprobante_form.html', {
        'form': form,
        'comprobante': comprobante,
        'entidad_texto': entidad_texto,
    })


def comprobante_listado(request):
    """Listado/búsqueda de comprobantes; es la puerta de entrada de 'Modificar'."""
    comprobantes = (
        Comprobante.objects.select_related('entidad_emisor', 'tipo_comprobante')
        .order_by('-fecha', '-id')
    )

    q_entidad = request.GET.get('entidad', '').strip()
    q_id = request.GET.get('id', '').strip()
    q_fecha = request.GET.get('fecha', '').strip()

    if q_entidad:
        comprobantes = comprobantes.filter(
            Q(entidad_emisor__nombre__icontains=q_entidad) | Q(entidad_emisor__cuit__icontains=q_entidad)
        )
    if q_id:
        if q_id.isdigit():
            comprobantes = comprobantes.filter(id=int(q_id))
        else:
            comprobantes = comprobantes.none()
    if q_fecha:
        comprobantes = comprobantes.filter(fecha=q_fecha)

    comprobantes = aplicar_orden_queryset(request, comprobantes, {
        'id': 'id',
        'fecha': 'fecha',
        'emisor': 'entidad_emisor__nombre',
        'tipo': 'tipo_comprobante__nombre',
        'numero': 'numero',
        'total': 'total',
    })

    return render(request, 'comprobantes/comprobante_listado.html', {
        'comprobantes': comprobantes[:200],
        'q_entidad': q_entidad,
        'q_id': q_id,
        'q_fecha': q_fecha,
    })


def comprobante_eliminar(request, pk):
    """Confirmación + baja de un Comprobante, desde el listado de 'Modificar'.

    Al ser on_delete=CASCADE, borrar el Comprobante también borra sus
    renglones (ComprobanteRenglon / ComprobanteRenglonDetalle) y su tipo de
    cambio si tenía. Si el comprobante ya está incluido en una liquidación
    no se permite borrarlo desde acá (mismo criterio que retenciones.views.
    retencion_eliminar), para no dejar una liquidación apuntando a un
    comprobante inexistente.
    """
    from django.db import IntegrityError
    from django.db.models import ProtectedError

    comprobante = get_object_or_404(Comprobante, pk=pk)

    if comprobante.liquidaciones.exists():
        messages.error(
            request,
            f'El comprobante {pk} ya está incluido en una liquidación y no se puede eliminar '
            'desde acá.'
        )
        return redirect('comprobantes:comprobante_modificar')

    if request.method == 'POST':
        try:
            comprobante.delete()
        except (ProtectedError, IntegrityError):
            messages.error(
                request,
                f'El comprobante {pk} no se puede eliminar porque está siendo usado en otro registro.'
            )
        else:
            messages.success(request, f'El comprobante {pk} se eliminó correctamente.')
        return redirect('comprobantes:comprobante_modificar')

    return render(request, 'comprobantes/comprobante_eliminar_confirm.html', {
        'comprobante': comprobante,
        'renglones': comprobante.renglon_comprobante.all(),
    })


# ---------------------------------------------------------------------------
# Exportar un comprobante puntual (encabezado + renglones) en formato
# parecido al de una factura, para poder puntear lo cargado en el sistema
# contra el papel real.
# ---------------------------------------------------------------------------

def _datos_comprobante_para_exportar(comprobante):
    """Arma los datos de encabezado y renglones de un comprobante, en la
    forma en que se ven en una factura (emisor, receptor, tabla de
    renglones, totales).

    'entidad_emisor' es siempre quien emitió el comprobante (puede ser un
    proveedor o la propia Fontana, según 'es_emisor'); el sistema no guarda
    una 'entidad_receptor' aparte, así que la contraparte se asume Fontana
    (ENTIDAD_PROPIA_ID) salvo que el emisor ya sea Fontana, en cuyo caso se
    usa el texto libre 'entidad_nombre' del comprobante (si lo tiene) como
    único dato del receptor.
    """
    emisor = comprobante.entidad_emisor
    if emisor and emisor.id == ENTIDAD_PROPIA_ID:
        receptor = None
        receptor_nombre_libre = comprobante.entidad_nombre or ''
    else:
        receptor = Entidad.objects.filter(pk=ENTIDAD_PROPIA_ID).first()
        receptor_nombre_libre = ''

    def _domicilio(entidad):
        if not entidad:
            return ''
        partes = [p for p in [entidad.direccion, entidad.localidad, entidad.provincia] if p]
        return ' - '.join(partes)

    renglones = (
        comprobante.renglon_comprobante
        .select_related(
            'producto', 'renglon_detalle_comprobante', 'renglon_detalle_comprobante__unidad_de_medida',
        )
        .order_by('id')
    )
    # Los productos/servicios reales van primero; iva/otros tributos
    # (percepciones de IVA, Ingresos Brutos, etc.) van al final, tanto en el
    # Excel como en el PDF, como en la lectura natural de una factura.
    renglones = sorted(renglones, key=lambda r: (0 if _producto_requiere_detalle(r.producto) else 1, r.id))

    filas = []
    for r in renglones:
        detalle = getattr(r, 'renglon_detalle_comprobante', None)
        filas.append({
            'codigo': r.producto_id,
            'producto': r.producto.nombre if r.producto_id else '',
            'cantidad': detalle.cantidad if detalle else None,
            'unidad': detalle.unidad_de_medida.nombre if detalle and detalle.unidad_de_medida_id else '',
            'precio_unitario': detalle.precio_unitario if detalle else None,
            'bonificacion': detalle.bonificacion if detalle else None,
            'subtotal': r.total,
            'cuenta_contable': r.id_cuenta_contable,
            'asiento_contable': r.id_asiento_contable,
        })

    numero_formateado = (
        f'{comprobante.punto_de_venta:04d}-{comprobante.numero:08d}'
        if comprobante.punto_de_venta is not None and comprobante.numero is not None
        else (str(comprobante.numero) if comprobante.numero is not None else '')
    )

    return {
        'tipo_texto': (
            f'{comprobante.tipo_comprobante.abreviatura or ""} {comprobante.tipo_comprobante.nombre or ""}'.strip()
            if comprobante.tipo_comprobante_id else 'Comprobante'
        ),
        'numero_formateado': numero_formateado,
        'emisor_nombre': emisor.nombre if emisor else '',
        'emisor_cuit': emisor.cuit if emisor else '',
        'emisor_domicilio': _domicilio(emisor),
        'emisor_iva': emisor.iva if emisor else '',
        'receptor_nombre': receptor.nombre if receptor else receptor_nombre_libre,
        'receptor_cuit': receptor.cuit if receptor else '',
        'receptor_domicilio': _domicilio(receptor),
        'receptor_iva': receptor.iva if receptor else '',
        'filas': filas,
        'comparacion_totales': _comparacion_totales_comprobante(comprobante, renglones),
    }


def comprobante_exportar_excel(request, pk):
    """Excel de un comprobante puntual (encabezado + renglones), con un
    formato parecido al de una factura."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from django.http import HttpResponse

    comprobante = get_object_or_404(
        Comprobante.objects.select_related('entidad_emisor', 'tipo_comprobante'), pk=pk
    )
    datos = _datos_comprobante_para_exportar(comprobante)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Comprobante {pk}'[:31]

    fuente_normal = Font(name='Arial', size=9)
    fuente_negrita = Font(name='Arial', size=9, bold=True)
    fuente_titulo = Font(name='Arial', size=13, bold=True)
    borde_fino = Border(
        left=Side(style='thin', color='999999'), right=Side(style='thin', color='999999'),
        top=Side(style='thin', color='999999'), bottom=Side(style='thin', color='999999'),
    )

    fila = 1
    ws.cell(row=fila, column=1, value=datos['tipo_texto']).font = fuente_titulo
    ws.cell(row=fila, column=5, value=f"Nº {datos['numero_formateado']}").font = fuente_negrita
    fila += 1
    ws.cell(row=fila, column=1, value=f"Fecha de emisión: {comprobante.fecha or ''}").font = fuente_normal
    ws.cell(row=fila, column=5, value=f"Comprobante interno: #{comprobante.id}").font = fuente_normal
    fila += 2

    def _bloque_entidad(fila, titulo, nombre, cuit, domicilio, iva):
        ws.cell(row=fila, column=1, value=titulo).font = fuente_negrita
        fila += 1
        ws.cell(row=fila, column=1, value='Nombre:').font = fuente_normal
        ws.cell(row=fila, column=2, value=nombre).font = fuente_normal
        ws.cell(row=fila, column=4, value='CUIT:').font = fuente_normal
        ws.cell(row=fila, column=5, value=cuit).font = fuente_normal
        fila += 1
        ws.cell(row=fila, column=1, value='Domicilio:').font = fuente_normal
        ws.cell(row=fila, column=2, value=domicilio).font = fuente_normal
        ws.cell(row=fila, column=4, value='Cond. IVA:').font = fuente_normal
        ws.cell(row=fila, column=5, value=iva).font = fuente_normal
        return fila + 2

    fila = _bloque_entidad(
        fila, 'Emisor', datos['emisor_nombre'], datos['emisor_cuit'], datos['emisor_domicilio'], datos['emisor_iva']
    )
    fila = _bloque_entidad(
        fila, 'Receptor', datos['receptor_nombre'], datos['receptor_cuit'], datos['receptor_domicilio'],
        datos['receptor_iva'],
    )

    columnas_tabla = [
        'Código', 'Producto / Servicio', 'Cantidad', 'U. Medida', 'Precio Unit.', 'Bonificación', 'Subtotal',
        'Cuenta Cont.', 'Asiento Cont.',
    ]
    for indice, titulo in enumerate(columnas_tabla, start=1):
        celda = ws.cell(row=fila, column=indice, value=titulo)
        celda.font = Font(name='Arial', size=9, bold=True, color='FFFFFF')
        celda.fill = PatternFill(start_color='343A40', end_color='343A40', fill_type='solid')
        celda.border = borde_fino
        celda.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    fila += 1

    primera_fila_datos = fila
    for r in datos['filas']:
        ws.cell(row=fila, column=1, value=r['codigo'])
        ws.cell(row=fila, column=2, value=r['producto'])
        ws.cell(row=fila, column=3, value=float(r['cantidad']) if r['cantidad'] is not None else None)
        ws.cell(row=fila, column=4, value=r['unidad'])
        ws.cell(row=fila, column=5, value=float(r['precio_unitario']) if r['precio_unitario'] is not None else None)
        ws.cell(row=fila, column=6, value=float(r['bonificacion']) if r['bonificacion'] is not None else None)
        ws.cell(row=fila, column=7, value=float(r['subtotal']) if r['subtotal'] is not None else None)
        ws.cell(row=fila, column=8, value=r['cuenta_contable'])
        ws.cell(row=fila, column=9, value=r['asiento_contable'])
        for columna in range(1, 10):
            celda = ws.cell(row=fila, column=columna)
            celda.font = fuente_normal
            celda.border = borde_fino
        fila += 1
    fila_final_datos = fila - 1

    for letra in ('C', 'E', 'F', 'G'):
        for fila_actual in range(primera_fila_datos, fila_final_datos + 1):
            ws[f'{letra}{fila_actual}'].number_format = '#,##0.00'

    fila += 1

    def _fila_total(fila, etiqueta, valor, negrita=False):
        estilo = fuente_negrita if negrita else fuente_normal
        ws.cell(row=fila, column=6, value=etiqueta).font = estilo
        celda_valor = ws.cell(row=fila, column=7, value=float(valor or 0))
        celda_valor.font = estilo
        celda_valor.number_format = '#,##0.00'
        return fila + 1

    fila = _fila_total(fila, 'Subtotal:', comprobante.neto_gravado)
    fila = _fila_total(fila, 'Otros tributos:', comprobante.otros_tributos)
    fila = _fila_total(fila, 'Exento:', comprobante.exento)
    fila = _fila_total(fila, 'IVA:', comprobante.iva)
    fila = _fila_total(fila, 'TOTAL:', comprobante.total, negrita=True)

    # Comparación cabecera vs. suma de renglones por categoría, para
    # puntear que lo cargado renglón por renglón coincida con la cabecera.
    fila += 1
    ws.cell(row=fila, column=6, value='Comparación cabecera vs. renglones:').font = Font(
        name='Arial', size=9, bold=True, italic=True
    )
    fila += 1
    for indice, titulo in enumerate(['Concepto', 'Cargado', 'Renglones', 'Diferencia'], start=6):
        celda = ws.cell(row=fila, column=indice, value=titulo)
        celda.font = fuente_negrita
        celda.border = borde_fino
    fila += 1
    for comp in datos['comparacion_totales']:
        con_diferencia = comp['diferencia'] != 0
        ws.cell(row=fila, column=6, value=comp['etiqueta']).font = fuente_normal
        for columna, clave in ((7, 'cargado'), (8, 'calculado'), (9, 'diferencia')):
            celda_valor = ws.cell(row=fila, column=columna, value=float(comp[clave]))
            celda_valor.number_format = '#,##0.00'
            celda_valor.font = fuente_negrita if con_diferencia else fuente_normal
            if con_diferencia:
                celda_valor.fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
        for columna in range(6, 10):
            ws.cell(row=fila, column=columna).border = borde_fino
        fila += 1

    for letra, ancho in {
        'A': 10, 'B': 38, 'C': 10, 'D': 10, 'E': 13, 'F': 13, 'G': 14, 'H': 12, 'I': 13,
    }.items():
        ws.column_dimensions[letra].width = ancho

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    nombre_archivo = f"comprobante_{datos['numero_formateado'] or comprobante.id}".replace('/', '-')
    response['Content-Disposition'] = f'attachment; filename={nombre_archivo}.xlsx'
    wb.save(response)
    return response


def comprobante_exportar_pdf(request, pk):
    """PDF de un comprobante puntual (encabezado + renglones), con un
    formato parecido al de una factura, tamaño A4 sin apaisar (parecido al
    tamaño real de una factura) para poder puntearlo contra el papel."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from django.http import HttpResponse

    from movimientos.templatetags.movimientos_extras import separador_miles

    comprobante = get_object_or_404(
        Comprobante.objects.select_related('entidad_emisor', 'tipo_comprobante'), pk=pk
    )
    datos = _datos_comprobante_para_exportar(comprobante)

    response = HttpResponse(content_type='application/pdf')
    nombre_archivo = f"comprobante_{datos['numero_formateado'] or comprobante.id}".replace('/', '-')
    response['Content-Disposition'] = f'attachment; filename={nombre_archivo}.pdf'

    margen = 1.3 * cm
    doc = SimpleDocTemplate(
        response, pagesize=A4,
        topMargin=margen, bottomMargin=margen, leftMargin=margen, rightMargin=margen,
    )
    ancho_disponible = A4[0] - doc.leftMargin - doc.rightMargin

    estilos = getSampleStyleSheet()
    estilo_normal = ParagraphStyle('normal_factura', parent=estilos['Normal'], fontSize=8, leading=10)
    estilo_negrita = ParagraphStyle('negrita_factura', parent=estilo_normal, fontName='Helvetica-Bold')
    estilo_celda = ParagraphStyle('celda_factura', parent=estilos['Normal'], fontSize=7.5, leading=9)
    estilo_encabezado_tabla = ParagraphStyle(
        'encabezado_factura', parent=estilo_celda, textColor=colors.white, fontName='Helvetica-Bold', alignment=1,
    )

    elementos = []

    encabezado = Table(
        [[
            Paragraph(
                f"<b>{datos['tipo_texto']}</b><br/>Nº {datos['numero_formateado']}",
                ParagraphStyle('titulo_factura', parent=estilos['Title'], fontSize=14, leading=17),
            ),
            Paragraph(
                f"Fecha de emisión: <b>{comprobante.fecha or ''}</b><br/>"
                f"Comprobante interno: #{comprobante.id}",
                estilo_normal,
            ),
        ]],
        colWidths=[ancho_disponible * 0.55, ancho_disponible * 0.45],
    )
    encabezado.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#343a40')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elementos += [encabezado, Spacer(1, 0.35 * cm)]

    def _bloque_entidad(titulo, nombre, cuit, domicilio, iva):
        texto = (
            f"<b>{titulo}:</b> {nombre or '—'}<br/>"
            f"CUIT: {cuit or '—'} &nbsp;&nbsp; Cond. IVA: {iva or '—'}<br/>"
            f"Domicilio: {domicilio or '—'}"
        )
        tabla = Table([[Paragraph(texto, estilo_normal)]], colWidths=[ancho_disponible])
        tabla.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return tabla

    elementos += [
        _bloque_entidad('Emisor', datos['emisor_nombre'], datos['emisor_cuit'], datos['emisor_domicilio'], datos['emisor_iva']),
        Spacer(1, 0.25 * cm),
        _bloque_entidad('Receptor', datos['receptor_nombre'], datos['receptor_cuit'], datos['receptor_domicilio'], datos['receptor_iva']),
        Spacer(1, 0.4 * cm),
    ]

    columnas_tabla = [
        'Código', 'Producto / Servicio', 'Cantidad', 'U. Medida', 'Precio Unit.', 'Bonificación', 'Subtotal',
        'Cuenta Cont.', 'Asiento Cont.',
    ]
    anchos_relativos = [0.6, 2.6, 0.7, 0.7, 0.9, 0.9, 1, 0.8, 0.8]
    total_relativo = sum(anchos_relativos)
    col_widths = [ancho_disponible * (peso / total_relativo) for peso in anchos_relativos]

    filas_tabla = [[Paragraph(c, estilo_encabezado_tabla) for c in columnas_tabla]]
    for r in datos['filas']:
        filas_tabla.append([
            Paragraph(str(r['codigo']) if r['codigo'] is not None else '', estilo_celda),
            Paragraph(r['producto'] or '', estilo_celda),
            Paragraph(separador_miles(r['cantidad']) if r['cantidad'] is not None else '', estilo_celda),
            Paragraph(r['unidad'] or '', estilo_celda),
            Paragraph(separador_miles(r['precio_unitario']) if r['precio_unitario'] is not None else '', estilo_celda),
            Paragraph(separador_miles(r['bonificacion']) if r['bonificacion'] is not None else '', estilo_celda),
            Paragraph(separador_miles(r['subtotal']) if r['subtotal'] is not None else '', estilo_celda),
            Paragraph(str(r['cuenta_contable']) if r['cuenta_contable'] is not None else '', estilo_celda),
            Paragraph(str(r['asiento_contable']) if r['asiento_contable'] is not None else '', estilo_celda),
        ])

    tabla_renglones = Table(filas_tabla, colWidths=col_widths, repeatRows=1)
    tabla_renglones.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elementos += [tabla_renglones, Spacer(1, 0.4 * cm)]

    filas_totales = [
        ('Subtotal:', separador_miles(comprobante.neto_gravado or 0)),
        ('Otros tributos:', separador_miles(comprobante.otros_tributos or 0)),
        ('Exento:', separador_miles(comprobante.exento or 0)),
        ('IVA:', separador_miles(comprobante.iva or 0)),
        ('TOTAL:', separador_miles(comprobante.total or 0)),
    ]
    tabla_totales = Table(
        [
            [
                Paragraph(etiqueta, estilo_negrita if etiqueta == 'TOTAL:' else estilo_normal),
                Paragraph(valor, estilo_negrita if etiqueta == 'TOTAL:' else estilo_normal),
            ]
            for etiqueta, valor in filas_totales
        ],
        colWidths=[ancho_disponible * 0.75, ancho_disponible * 0.25],
    )
    tabla_totales.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, -1), (-1, -1), 0.75, colors.HexColor('#343a40')),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elementos.append(tabla_totales)

    # Comparación cabecera vs. suma de renglones por categoría, para
    # puntear que lo cargado renglón por renglón coincida con la cabecera.
    filas_comparacion = [[
        Paragraph('Concepto', estilo_encabezado_tabla),
        Paragraph('Cargado', estilo_encabezado_tabla),
        Paragraph('Renglones', estilo_encabezado_tabla),
        Paragraph('Diferencia', estilo_encabezado_tabla),
    ]]
    for comp in datos['comparacion_totales']:
        estilo_fila = estilo_negrita if comp['diferencia'] else estilo_normal
        filas_comparacion.append([
            Paragraph(comp['etiqueta'], estilo_fila),
            Paragraph(separador_miles(comp['cargado']), estilo_fila),
            Paragraph(separador_miles(comp['calculado']), estilo_fila),
            Paragraph(separador_miles(comp['diferencia']), estilo_fila),
        ])
    tabla_comparacion = Table(
        filas_comparacion,
        colWidths=[ancho_disponible * 0.4, ancho_disponible * 0.2, ancho_disponible * 0.2, ancho_disponible * 0.2],
    )
    estilo_tabla_comparacion = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]
    for indice_fila, comp in enumerate(datos['comparacion_totales'], start=1):
        if comp['diferencia']:
            estilo_tabla_comparacion.append(
                ('BACKGROUND', (0, indice_fila), (-1, indice_fila), colors.HexColor('#f8d7da'))
            )
    tabla_comparacion.setStyle(TableStyle(estilo_tabla_comparacion))
    elementos += [Spacer(1, 0.3 * cm), tabla_comparacion]

    doc.build(elementos)
    return response


def comprobante_reporte(request):
    form = forms.ComprobanteReporteForm(request.GET or None)
    comprobantes = (
        Comprobante.objects.select_related('entidad_emisor', 'tipo_comprobante')
        .order_by('-fecha', '-id')
    )

    entidad = None
    if form.is_valid():
        entidad = form.cleaned_data.get('entidad')
        fecha_desde = form.cleaned_data.get('fecha_desde')
        fecha_hasta = form.cleaned_data.get('fecha_hasta')
        if entidad:
            comprobantes = comprobantes.filter(entidad_emisor=entidad)
        if fecha_desde:
            comprobantes = comprobantes.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            comprobantes = comprobantes.filter(fecha__lte=fecha_hasta)

    totales = comprobantes.aggregate(
        total=Coalesce(Sum('total'), Value(Decimal('0')), output_field=DecimalField(max_digits=20, decimal_places=2)),
    )

    comprobantes = aplicar_orden_queryset(request, comprobantes, {
        'id': 'id',
        'fecha': 'fecha',
        'emisor': 'entidad_emisor__nombre',
        'tipo': 'tipo_comprobante__nombre',
        'numero': 'numero',
        'total': 'total',
    })

    return render(request, 'comprobantes/comprobante_reporte.html', {
        'form': form,
        'comprobantes': comprobantes[:500],
        'totales': totales,
        'entidad_texto': texto_entidad_buscador(entidad),
    })


# --- Ranking de entidades (por monto total de comprobantes, filtrando por
# rol -emisora/receptora respecto de Fontana- y por un lapso de fechas) ---

def _comprobantes_ranking_filtrados(request):
    """Aplica a Comprobante los filtros de RankingEntidadesForm (rol de la
    entidad, según 'es_emisor', rango de fecha de emisión y, opcionalmente,
    excluir a Fontana). Devuelve (form, queryset, filtros_activos),
    centralizado para que la pantalla y las exportaciones (Excel / PDF) usen
    siempre los mismos criterios.

    El rol se aplica siempre (incluso sin enviar el formulario), tomando
    'emisora' como valor por defecto, porque no es un filtro opcional sino
    el modo del ranking: Comprobante sólo tiene un FK de entidad
    ('entidad_emisor'); 'es_emisor' indica si, respecto de Fontana, esa
    entidad emitió el comprobante (1, "entidad emisora") o lo recibió de
    Fontana (0, "entidad receptora").
    """
    form = forms.RankingEntidadesForm(request.GET or None)
    comprobantes = Comprobante.objects.all()

    rol = request.GET.get('rol') or forms.RankingEntidadesForm.ROL_EMISORA
    if rol not in dict(forms.RankingEntidadesForm.ROL_CHOICES):
        rol = forms.RankingEntidadesForm.ROL_EMISORA
    comprobantes = comprobantes.filter(es_emisor=1 if rol == forms.RankingEntidadesForm.ROL_EMISORA else 0)

    filtros_activos = False
    if form.is_valid():
        fecha_desde = form.cleaned_data.get('fecha_desde')
        fecha_hasta = form.cleaned_data.get('fecha_hasta')
        excluir_fontana = form.cleaned_data.get('excluir_fontana')
        if fecha_desde:
            comprobantes = comprobantes.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            comprobantes = comprobantes.filter(fecha__lte=fecha_hasta)
        if excluir_fontana:
            comprobantes = comprobantes.exclude(entidad_emisor_id=ENTIDAD_PROPIA_ID)
        filtros_activos = bool(
            rol != forms.RankingEntidadesForm.ROL_EMISORA or fecha_desde or fecha_hasta or excluir_fontana
        )

    return form, comprobantes, filtros_activos


def _calcular_ranking_entidades(comprobantes):
    """A partir de un queryset de Comprobante (ya filtrado por rol y fecha),
    arma el ranking de entidades por monto total (de mayor a menor) y el
    total general. El monto de los comprobantes de tipo 'nota de credito'
    -que se guardan siempre en positivo- se resta en vez de sumarse, mismo
    criterio de signo que liquidaciones.views.suma_comprobantes. Devuelve
    (ranking, total_general)."""
    monto_signado = Case(
        When(tipo_comprobante__nombre__icontains='nota de credito', then=-F('total')),
        default=F('total'),
        output_field=DecimalField(max_digits=20, decimal_places=2),
    )
    ranking = list(
        comprobantes.annotate(monto_signado=monto_signado)
        .values('entidad_emisor_id', 'entidad_emisor__nombre')
        .annotate(total_monto=Sum('monto_signado'), cantidad=Count('id'))
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


def comprobante_ranking_entidades(request):
    """Ranking de entidades por monto total de comprobantes, de mayor a
    menor, filtrando por rol (emisora o receptora respecto de Fontana) y,
    opcionalmente, por un rango de fecha de emisión."""
    form, comprobantes, filtros_activos = _comprobantes_ranking_filtrados(request)
    ranking, total_general = _calcular_ranking_entidades(comprobantes)
    ranking = aplicar_orden_lista(request, ranking, {
        'posicion': lambda f: f['posicion'],
        'entidad': lambda f: (f['entidad_emisor__nombre'] or '').lower(),
        'cantidad': lambda f: f['cantidad'],
        'monto': lambda f: f['total_monto'] if f['total_monto'] is not None else Decimal('0'),
        'porcentaje': lambda f: f['porcentaje'],
    })

    return render(request, 'comprobantes/comprobante_ranking_entidades.html', {
        'form': form,
        'ranking': ranking,
        'total_general': total_general,
        'filtros_activos': filtros_activos,
    })


def _filas_ranking_entidades(ranking):
    columnas = ['#', 'Entidad', 'Comprobantes', 'Monto total', 'Participación %']
    filas = [
        [
            fila['posicion'],
            fila['entidad_emisor__nombre'] or 'Sin nombre',
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


def comprobante_ranking_entidades_excel(request):
    _form, comprobantes, _filtros_activos = _comprobantes_ranking_filtrados(request)
    ranking, _total_general = _calcular_ranking_entidades(comprobantes)
    resultado = _filas_ranking_entidades(ranking)
    return excel_response('ranking_entidades_comprobantes', resultado)


def comprobante_ranking_entidades_pdf(request):
    _form, comprobantes, _filtros_activos = _comprobantes_ranking_filtrados(request)
    ranking, _total_general = _calcular_ranking_entidades(comprobantes)
    resultado = _filas_ranking_entidades(ranking)
    return pdf_response(
        'ranking_entidades_comprobantes', 'Ranking de entidades por monto de comprobantes', resultado
    )


# ---------------------------------------------------------------------------
# Alta / Modificar / Reportes de ComprobanteRenglon
# ---------------------------------------------------------------------------

def _siguiente_id_comprobante_renglon():
    ultimo = ComprobanteRenglon.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


def _categoria_producto(producto):
    """Categoría (item_tipo.nombre, en minúsculas y sin espacios extra) de
    un producto, o '' si no tiene categoría asignada."""
    if producto is None or not producto.item_tipo_id:
        return ''
    return (producto.item_tipo.nombre or '').strip().lower()


def _producto_requiere_detalle(producto):
    """True si la categoría (item_tipo) del producto es Producto o Servicio,
    caso en el que corresponde habilitar comprobante_renglon_detalle."""
    return _categoria_producto(producto) in forms.CATEGORIAS_CON_DETALLE


def _a_decimal(valor):
    """Convierte a Decimal un valor numérico (Decimal, float o None), para
    poder sumar/restar sin mezclar tipos (p.ej. Comprobante.neto_gravado es
    FloatField, pero iva/otros_tributos son DecimalField)."""
    if valor is None:
        return Decimal('0')
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def _totales_renglones_por_categoria(renglones):
    """Suma el campo 'total' de una lista/queryset de ComprobanteRenglon,
    agrupando por categoría del producto (item_tipo) en 'producto_servicio',
    'iva' u 'otro_tributo'. Sirve para puntear la cabecera del comprobante
    (neto_gravado/iva/otros_tributos) contra la suma de sus renglones."""
    acumulado = {
        'producto_servicio': Decimal('0'),
        'iva': Decimal('0'),
        'otro_tributo': Decimal('0'),
    }
    for r in renglones:
        categoria = _categoria_producto(r.producto)
        monto = _a_decimal(r.total)
        if categoria in forms.CATEGORIAS_CON_DETALLE:
            acumulado['producto_servicio'] += monto
        elif categoria == forms.CATEGORIA_IVA:
            acumulado['iva'] += monto
        elif categoria in forms.CATEGORIAS_OTRO_TRIBUTO:
            acumulado['otro_tributo'] += monto
    return acumulado


def _comparacion_totales_comprobante(comprobante, renglones):
    """Arma, para pantalla y exportaciones (Excel/PDF), la comparación
    entre lo cargado en la cabecera del comprobante (neto_gravado, iva,
    otros_tributos) y lo que suman sus renglones por categoría. Cada fila
    trae 'cargado' (cabecera), 'calculado' (suma de renglones) y
    'diferencia' (cargado - calculado; 0 si puntea)."""
    sumas = _totales_renglones_por_categoria(renglones)

    def _fila(etiqueta, cargado, calculado):
        cargado = _a_decimal(cargado)
        return {
            'etiqueta': etiqueta,
            'cargado': cargado,
            'calculado': calculado,
            'diferencia': cargado - calculado,
        }

    return [
        _fila('Neto gravado (producto/servicio)', comprobante.neto_gravado, sumas['producto_servicio']),
        _fila('IVA', comprobante.iva, sumas['iva']),
        _fila('Otros tributos', comprobante.otros_tributos, sumas['otro_tributo']),
    ]


def _texto_comprobante(comprobante):
    """Texto a mostrar en el buscador de comprobante."""
    if not comprobante:
        return ''
    partes = [f'#{comprobante.id}']
    if comprobante.punto_de_venta is not None and comprobante.numero is not None:
        partes.append(f'{comprobante.punto_de_venta:04d}-{comprobante.numero:08d}')
    elif comprobante.numero is not None:
        partes.append(f'Nº {comprobante.numero}')
    if comprobante.fecha:
        partes.append(str(comprobante.fecha))
    if comprobante.entidad_emisor_id and comprobante.entidad_emisor.nombre:
        partes.append(comprobante.entidad_emisor.nombre)
    return ' - '.join(partes)


def _texto_producto(producto):
    """Texto a mostrar en el buscador de producto."""
    if not producto:
        return ''
    return f'{producto.id} - {producto.nombre}' if producto.nombre else str(producto.id)


def comprobante_renglon_comprobante_buscar(request):
    """
    Devuelve, en JSON, hasta 20 comprobantes cuyo ID interno, número o punto
    de venta-número contengan el texto buscado. Usado por el buscador de
    comprobante del alta/modificación de ComprobanteRenglon.

    Antes esto sólo buscaba por 'id' (la clave interna autoincremental), que
    no es el "número de comprobante" que el usuario tiene a la vista (ese es
    el campo 'numero', junto con 'punto_de_venta'); por eso buscar por
    número de comprobante no encontraba nada.
    """
    q = request.GET.get('q', '').strip()
    resultados = []

    if q:
        comprobantes = (
            Comprobante.objects.select_related('entidad_emisor')
            .annotate(
                id_texto=Cast('id', output_field=CharField()),
                numero_texto=Cast('numero', output_field=CharField()),
                punto_venta_texto=Cast('punto_de_venta', output_field=CharField()),
            )
            .filter(
                Q(id_texto__icontains=q)
                | Q(numero_texto__icontains=q)
                | Q(punto_venta_texto__icontains=q)
                | Q(comprobante_string__icontains=q)
            )
            .order_by('-fecha', '-id')[:20]
        )
        resultados = [
            {'id': c.id, 'text': _texto_comprobante(c)}
            for c in comprobantes
        ]

    return JsonResponse({'resultados': resultados})


def comprobante_renglon_producto_buscar(request):
    """
    Devuelve, en JSON, hasta 20 producto_detalle cuyo nombre o ID coincidan
    con el texto buscado, incluyendo su categoría (item_tipo). Usado por el
    buscador de producto del alta/modificación de ComprobanteRenglon.
    """
    q = request.GET.get('q', '').strip()
    resultados = []

    if q:
        filtro = Q(nombre__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))
        productos = (
            ProductoDetalle.objects.select_related('item_tipo')
            .filter(filtro)
            .order_by('nombre')[:20]
        )
        resultados = [
            {
                'id': p.id,
                'text': _texto_producto(p),
                'categoria': (p.item_tipo.nombre or '').strip().lower() if p.item_tipo_id else None,
            }
            for p in productos
        ]

    return JsonResponse({'resultados': resultados})


def _siguiente_id_producto_detalle():
    ultimo = ProductoDetalle.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


@transaction.atomic
def comprobante_renglon_producto_crear(request):
    """
    Alta rápida (AJAX) de un producto/ítem nuevo desde el buscador de
    producto del alta/modificación de ComprobanteRenglon, para cuando el
    producto buscado todavía no existe. Devuelve el mismo formato que
    comprobante_renglon_producto_buscar, para poder seleccionarlo
    automáticamente apenas se crea.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)

    form = forms.ProductoDetalleCrearForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errores': form.errors.get_json_data()}, status=400)

    nuevo = form.save(commit=False)
    nuevo.id = _siguiente_id_producto_detalle()
    nuevo.save()

    return JsonResponse({
        'id': nuevo.id,
        'text': _texto_producto(nuevo),
        'categoria': (nuevo.item_tipo.nombre or '').strip().lower() if nuevo.item_tipo_id else None,
    })


@transaction.atomic
def comprobante_renglon_form(request, pk=None):
    """Alta y modificación de un ComprobanteRenglon (misma vista, pk=None para alta)."""
    renglon = get_object_or_404(ComprobanteRenglon, pk=pk) if pk else None
    detalle = ComprobanteRenglonDetalle.objects.filter(pk=renglon.pk).first() if renglon else None

    # Al guardar un renglón se vuelve al alta con el mismo comprobante ya
    # cargado (pasado por querystring), para poder seguir agregando
    # renglones del mismo comprobante sin tener que volver a buscarlo cada
    # vez (es el caso más habitual).
    comprobante_preseleccionado = None
    if renglon is None:
        comprobante_id_qs = request.GET.get('comprobante', '').strip()
        if comprobante_id_qs.isdigit():
            comprobante_preseleccionado = Comprobante.objects.select_related('entidad_emisor').filter(
                pk=comprobante_id_qs
            ).first()

    if request.method == 'POST':
        form = forms.ComprobanteRenglonForm(request.POST, instance=renglon)
        detalle_form = forms.ComprobanteRenglonDetalleForm(request.POST, instance=detalle)

        if form.is_valid():
            producto = form.cleaned_data.get('producto')
            requiere_detalle = _producto_requiere_detalle(producto)

            # El detalle sólo se valida (y exige) cuando la categoría del
            # producto lo requiere; si no, se ignora lo que haya llegado.
            detalle_valido = detalle_form.is_valid() if requiere_detalle else True

            if detalle_valido:
                nuevo = form.save(commit=False)
                if renglon is None:
                    nuevo.id = _siguiente_id_comprobante_renglon()
                nuevo.save()

                if requiere_detalle:
                    nuevo_detalle = detalle_form.save(commit=False)
                    nuevo_detalle.comprobante_renglon = nuevo
                    # El precio unitario se calcula siempre en el servidor
                    # (total del renglón / cantidad), sin confiar en lo que
                    # haya llegado del campo de solo lectura del formulario.
                    cantidad = detalle_form.cleaned_data.get('cantidad')
                    if cantidad and nuevo.total is not None:
                        nuevo_detalle.precio_unitario = (nuevo.total / cantidad).quantize(Decimal('0.01'))
                    else:
                        nuevo_detalle.precio_unitario = None
                    nuevo_detalle.save()
                elif detalle is not None:
                    # La categoría cambió y ya no corresponde tener detalle.
                    detalle.delete()

                messages.success(request, f'Renglón de comprobante {nuevo.id} guardado correctamente.')
                url_alta = reverse('comprobantes:comprobante_renglon_alta')
                return redirect(f'{url_alta}?comprobante={nuevo.comprobante_id}')
    else:
        initial = {'comprobante': comprobante_preseleccionado.id} if comprobante_preseleccionado else None
        form = forms.ComprobanteRenglonForm(instance=renglon, initial=initial)
        detalle_form = forms.ComprobanteRenglonDetalleForm(instance=detalle)

    comprobante_para_texto = renglon.comprobante if renglon else comprobante_preseleccionado

    # Renglones que ya tiene cargados el comprobante elegido (para mostrarlos
    # como referencia apenas se selecciona un comprobante, junto con su
    # detalle si lo tienen). Si se está editando un renglón puntual, se
    # excluye de esta lista (ya está en el formulario de arriba).
    renglones_del_comprobante = []
    if comprobante_para_texto is not None:
        renglones_qs = (
            comprobante_para_texto.renglon_comprobante
            .select_related(
                'producto', 'renglon_detalle_comprobante', 'renglon_detalle_comprobante__unidad_de_medida',
            )
            .order_by('id')
        )
        if renglon is not None:
            renglones_qs = renglones_qs.exclude(pk=renglon.pk)
        # Los productos/servicios reales van primero; iva/otros tributos
        # (percepciones de IVA, Ingresos Brutos, etc.) van al final, como en
        # la lectura natural de una factura.
        renglones_del_comprobante = sorted(
            renglones_qs, key=lambda r: (0 if _producto_requiere_detalle(r.producto) else 1, r.id)
        )

    # Comparación cabecera (neto_gravado/iva/otros_tributos) vs. suma de
    # renglones ya cargados, para puntear mientras se van agregando.
    comparacion_totales = (
        _comparacion_totales_comprobante(comprobante_para_texto, renglones_del_comprobante)
        if comprobante_para_texto is not None else []
    )

    return render(request, 'comprobantes/comprobante_renglon_form.html', {
        'form': form,
        'detalle_form': detalle_form,
        'renglon': renglon,
        'categorias_con_detalle': list(forms.CATEGORIAS_CON_DETALLE),
        'comprobante_texto': _texto_comprobante(comprobante_para_texto),
        'comprobante_seleccionado': comprobante_para_texto,
        'renglones_del_comprobante': renglones_del_comprobante,
        'comparacion_totales': comparacion_totales,
        'producto_texto': _texto_producto(renglon.producto) if renglon else '',
        'producto_categoria_inicial': (
            (renglon.producto.item_tipo.nombre or '').strip().lower()
            if renglon and renglon.producto.item_tipo_id else ''
        ),
        'producto_crear_form': forms.ProductoDetalleCrearForm(),
    })


def comprobante_renglon_listado(request):
    """Listado/búsqueda de renglones de comprobante; puerta de entrada de 'Modificar'."""
    renglones = (
        ComprobanteRenglon.objects.select_related('comprobante', 'producto')
        .order_by('-comprobante__fecha', '-id')
    )

    q_id = request.GET.get('id', '').strip()
    q_comprobante = request.GET.get('comprobante', '').strip()

    if q_id:
        if q_id.isdigit():
            renglones = renglones.filter(id=int(q_id))
        else:
            renglones = renglones.none()
    if q_comprobante:
        if q_comprobante.isdigit():
            renglones = renglones.filter(comprobante_id=int(q_comprobante))
        else:
            renglones = renglones.none()

    renglones = aplicar_orden_queryset(request, renglones, {
        'id': 'id',
        'comprobante': 'comprobante_id',
        'fecha': 'comprobante__fecha',
        'producto': 'producto__nombre',
        'total': 'total',
    })

    return render(request, 'comprobantes/comprobante_renglon_listado.html', {
        'renglones': renglones[:200],
        'q_id': q_id,
        'q_comprobante': q_comprobante,
    })


def comprobante_renglon_eliminar(request, pk):
    """Confirmación + baja de un ComprobanteRenglon, desde el listado de
    'Modificar' de renglones. Al ser on_delete=CASCADE, borrar el renglón
    también borra su detalle (ComprobanteRenglonDetalle) si tenía.
    """
    from django.db import IntegrityError
    from django.db.models import ProtectedError

    renglon = get_object_or_404(ComprobanteRenglon, pk=pk)

    if request.method == 'POST':
        try:
            renglon.delete()
        except (ProtectedError, IntegrityError):
            messages.error(
                request,
                f'El renglón {pk} no se puede eliminar porque está siendo usado en otro registro.'
            )
        else:
            messages.success(request, f'El renglón {pk} se eliminó correctamente.')
        return redirect('comprobantes:comprobante_renglon_modificar')

    return render(request, 'comprobantes/comprobante_renglon_eliminar_confirm.html', {
        'renglon': renglon,
    })


def comprobante_renglon_reporte(request):
    form = forms.ComprobanteRenglonReporteForm(request.GET or None)
    renglones = (
        ComprobanteRenglon.objects.select_related('comprobante', 'producto')
        .order_by('-comprobante__fecha', '-id')
    )

    if form.is_valid():
        producto = form.cleaned_data.get('producto')
        fecha_desde = form.cleaned_data.get('fecha_desde')
        fecha_hasta = form.cleaned_data.get('fecha_hasta')
        if producto:
            renglones = renglones.filter(producto=producto)
        if fecha_desde:
            renglones = renglones.filter(comprobante__fecha__gte=fecha_desde)
        if fecha_hasta:
            renglones = renglones.filter(comprobante__fecha__lte=fecha_hasta)

    totales = renglones.aggregate(
        total=Coalesce(Sum('total'), Value(Decimal('0')), output_field=DecimalField(max_digits=20, decimal_places=2)),
    )

    renglones = aplicar_orden_queryset(request, renglones, {
        'id': 'id',
        'comprobante': 'comprobante_id',
        'fecha': 'comprobante__fecha',
        'producto': 'producto__nombre',
        'total': 'total',
    })

    return render(request, 'comprobantes/comprobante_renglon_reporte.html', {
        'form': form,
        'renglones': renglones[:500],
        'totales': totales,
    })
