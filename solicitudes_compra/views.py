from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from comprobantes.models import ComprobanteRenglon
from empleados.models import Empleado
from entidades.models import Entidad
from services.buscadores import texto_empleado_buscador, texto_entidad_buscador
from services.ordenamiento import aplicar_orden_queryset

from . import documentos
from .forms import SolicitudCompraForm, SolicitudCompraRenglonFormSet
from .models import SolicitudCompra, SolicitudCompraRenglon, SolicitudCompraRenglonComprobanteRenglon

FORMSET_PREFIX = 'renglones'


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------

def solicitud_list(request):
    solicitudes = SolicitudCompra.objects.select_related('entidad', 'solicitante', 'responsable_retiro', 'creado_por')

    q_entidad = request.GET.get('entidad', '').strip()
    q_id = request.GET.get('id', '').strip()
    q_estado = request.GET.get('estado', '').strip()

    if q_entidad:
        solicitudes = solicitudes.filter(
            Q(entidad__nombre__icontains=q_entidad) | Q(entidad__cuit__icontains=q_entidad)
        )
    if q_id:
        if q_id.isdigit():
            solicitudes = solicitudes.filter(id=int(q_id))
        else:
            solicitudes = solicitudes.none()
    if q_estado:
        solicitudes = solicitudes.filter(estado=q_estado)

    solicitudes = aplicar_orden_queryset(request, solicitudes, {
        'id': 'id',
        'numero': 'numero',
        'fecha': 'fecha',
        'entidad': 'entidad__nombre',
        'estado': 'estado',
    })

    return render(request, 'solicitudes_compra/list.html', {
        'solicitudes': solicitudes,
        'q_entidad': q_entidad,
        'q_id': q_id,
        'q_estado': q_estado,
        'estados': SolicitudCompra.ESTADO_CHOICES,
        # Si venimos de "Guardar y generar PDF/Excel" en el alta/edición,
        # 'abrir' le dice a list.html que abra ese archivo solo en esta
        # carga de la página (ver script al pie de list.html).
        'abrir': request.GET.get('abrir', '').strip(),
    })


# ---------------------------------------------------------------------------
# Alta / Edición (misma vista, pk=None para alta)
# ---------------------------------------------------------------------------

def solicitud_form(request, pk=None):
    solicitud = get_object_or_404(SolicitudCompra, pk=pk) if pk else None

    if request.method == 'POST':
        form = SolicitudCompraForm(request.POST, instance=solicitud)
        formset = SolicitudCompraRenglonFormSet(
            request.POST, instance=solicitud or SolicitudCompra(), prefix=FORMSET_PREFIX,
        )
        if form.is_valid() and formset.is_valid():
            es_nueva = solicitud is None  # antes de guardar: sin pk todavía en el alta
            solicitud = form.save(commit=False)
            if es_nueva:
                # Usuario que crea la solicitud, tomado del login de Django
                # (no se pisa en ediciones posteriores).
                solicitud.creado_por = request.user
            solicitud.save()
            formset.instance = solicitud
            formset.save()
            messages.success(request, f'Solicitud {solicitud.numero} guardada correctamente.')

            # El formulario tiene tres botones de guardar (name="accion"):
            # uno guarda y nada más, y los otros dos además abren el PDF o
            # el Excel recién generado en una pestaña nueva (ver el script
            # al pie de list.html, que es donde se termina redirigiendo).
            accion = request.POST.get('accion', 'guardar')
            destino = f"{reverse('solicitudes_compra:listado')}?id={solicitud.id}"
            if accion == 'guardar_pdf':
                destino += '&abrir=pdf'
            elif accion == 'guardar_excel':
                destino += '&abrir=excel'
            return redirect(destino)
    else:
        form = SolicitudCompraForm(instance=solicitud)
        formset = SolicitudCompraRenglonFormSet(instance=solicitud, prefix=FORMSET_PREFIX)

    # Texto a mostrar en cada buscador: lo ya elegido (edición), o lo que
    # quedó tipeado en un POST inválido (mismo criterio que ya se usa en
    # comprobantes/liquidaciones para sus propios buscadores de entidad).
    entidad_id = form['entidad'].value()
    entidad_texto = texto_entidad_buscador(Entidad.objects.filter(pk=entidad_id).first()) if entidad_id else ''
    solicitante_id = form['solicitante'].value()
    solicitante_texto = texto_empleado_buscador(Empleado.objects.filter(pk=solicitante_id).first()) if solicitante_id else ''
    responsable_id = form['responsable_retiro'].value()
    responsable_texto = texto_empleado_buscador(Empleado.objects.filter(pk=responsable_id).first()) if responsable_id else ''

    return render(request, 'solicitudes_compra/form.html', {
        'form': form,
        'formset': formset,
        'solicitud': solicitud,
        'entidad_texto': entidad_texto,
        'solicitante_texto': solicitante_texto,
        'responsable_texto': responsable_texto,
    })


# ---------------------------------------------------------------------------
# Eliminar
# ---------------------------------------------------------------------------

def solicitud_eliminar(request, pk):
    solicitud = get_object_or_404(SolicitudCompra, pk=pk)

    if request.method == 'POST':
        numero = solicitud.numero
        solicitud.delete()  # CASCADE se encarga de sus renglones y vínculos
        messages.success(request, f'Solicitud {numero} eliminada.')
        return redirect('solicitudes_compra:listado')

    return render(request, 'solicitudes_compra/eliminar_confirm.html', {'solicitud': solicitud})


# ---------------------------------------------------------------------------
# Vincular renglones de la solicitud con renglones de factura ya cargados
# ---------------------------------------------------------------------------

def solicitud_vincular(request, pk):
    solicitud = get_object_or_404(SolicitudCompra.objects.select_related('entidad'), pk=pk)
    renglones = solicitud.renglones.prefetch_related(
        'vinculos__comprobante_renglon__producto',
        'vinculos__comprobante_renglon__comprobante',
    )

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'vincular':
            renglon = get_object_or_404(
                SolicitudCompraRenglon, pk=request.POST.get('solicitud_renglon'), solicitud=solicitud,
            )
            comprobante_renglon = get_object_or_404(ComprobanteRenglon, pk=request.POST.get('comprobante_renglon'))
            SolicitudCompraRenglonComprobanteRenglon.objects.get_or_create(
                solicitud_renglon=renglon, comprobante_renglon=comprobante_renglon,
            )
            messages.success(request, 'Renglón vinculado correctamente.')
        elif accion == 'desvincular':
            SolicitudCompraRenglonComprobanteRenglon.objects.filter(
                pk=request.POST.get('vinculo_id'), solicitud_renglon__solicitud=solicitud,
            ).delete()
            messages.success(request, 'Vínculo eliminado.')
        return redirect('solicitudes_compra:vincular', pk=pk)

    q = request.GET.get('q', '').strip()
    candidatos = (
        ComprobanteRenglon.objects.filter(
            comprobante__entidad_emisor=solicitud.entidad,
            producto__item_tipo_id=1,
        )
        .select_related('producto', 'comprobante', 'renglon_detalle_comprobante')
        .order_by('-comprobante__fecha', '-id')
    )
    if q:
        candidatos = candidatos.filter(producto__nombre__icontains=q)
    candidatos = candidatos[:100]

    return render(request, 'solicitudes_compra/vincular.html', {
        'solicitud': solicitud,
        'renglones': renglones,
        'candidatos': candidatos,
        'q': q,
    })


# ---------------------------------------------------------------------------
# Impresión (PDF / Excel)
# ---------------------------------------------------------------------------

def solicitud_pdf(request, pk):
    solicitud = get_object_or_404(
        SolicitudCompra.objects.select_related('entidad', 'solicitante', 'responsable_retiro'), pk=pk
    )
    return documentos.generar_pdf_solicitud(solicitud)


def solicitud_excel(request, pk):
    solicitud = get_object_or_404(
        SolicitudCompra.objects.select_related('entidad', 'solicitante', 'responsable_retiro'), pk=pk
    )
    return documentos.generar_excel_solicitud(solicitud)
