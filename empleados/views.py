from django.contrib import messages
from django.db import IntegrityError
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from services.ordenamiento import aplicar_orden_queryset

from .forms import EmpleadoForm
from .models import Empleado


def empleado_buscar(request):
    """
    Devuelve, en JSON, hasta 20 empleados activos cuyo nombre, apellido o
    documento contengan el texto buscado. Usado por los buscadores de
    "solicitante" / "autorizado a retirar" de Solicitud de Compra.
    """
    q = request.GET.get('q', '').strip()
    resultados = []
    if len(q) >= 2:
        empleados = Empleado.objects.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(documento__icontains=q),
            activo=True,
        ).order_by('apellido', 'nombre')[:20]
        resultados = [{'id': e.id, 'text': str(e)} for e in empleados]
    return JsonResponse({'resultados': resultados})


def empleado_list(request):
    empleados = Empleado.objects.all()

    q = request.GET.get('q', '').strip()
    if q:
        empleados = empleados.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(documento__icontains=q)
        )

    solo_activos = request.GET.get('activos') == '1'
    if solo_activos:
        empleados = empleados.filter(activo=True)

    empleados = aplicar_orden_queryset(request, empleados, {
        'nombre': 'nombre',
        'apellido': 'apellido',
        'documento': 'documento',
        'activo': 'activo',
    }, default='apellido')

    return render(request, 'empleados/list.html', {
        'empleados': empleados,
        'q': q,
        'solo_activos': solo_activos,
    })


def empleado_form(request, pk=None):
    empleado = get_object_or_404(Empleado, pk=pk) if pk else None

    if request.method == 'POST':
        form = EmpleadoForm(request.POST, instance=empleado)
        if form.is_valid():
            empleado = form.save()
            messages.success(request, f'Empleado "{empleado}" guardado correctamente.')
            return redirect('empleados:listado')
    else:
        form = EmpleadoForm(instance=empleado)

    return render(request, 'empleados/form.html', {
        'form': form,
        'empleado': empleado,
    })


def empleado_eliminar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)

    if request.method == 'POST':
        try:
            empleado.delete()
        except (ProtectedError, IntegrityError):
            messages.error(
                request,
                f'"{empleado}" no se puede eliminar porque está siendo usado en alguna solicitud de compra.'
            )
        else:
            messages.success(request, f'"{empleado}" se eliminó correctamente.')
        return redirect('empleados:listado')

    return render(request, 'empleados/eliminar_confirm.html', {'empleado': empleado})
