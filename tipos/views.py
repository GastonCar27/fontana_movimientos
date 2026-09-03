from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Max, ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from services.ordenamiento import aplicar_orden_queryset

from .forms import form_class_para
from .registry import obtener_config


def _config_o_404(slug):
    config = obtener_config(slug)
    if config is None:
        raise Http404(f'No existe ningún catálogo de tipos con el identificador "{slug}".')
    return config


def _siguiente_id(model):
    """Ninguna de las tablas 'tipo' tiene AUTO_INCREMENT en su columna id
    (se ve en estructura_bd.sql), así que el próximo id se calcula a
    mano, igual que en retenciones.views._siguiente_id_retencion."""
    ultimo = model.objects.aggregate(Max('id'))['id__max'] or 0
    return ultimo + 1


def tipo_listado(request, slug):
    config = _config_o_404(slug)
    objetos = config['model'].objects.all().order_by(config['orden'])
    # Los campos del catálogo son siempre columnas propias del modelo (no
    # relaciones), así que se puede ordenar de forma genérica por 'id' o por
    # el nombre de cualquiera de los 'campos' configurados en el registry.
    campos_orden = {nombre_campo: nombre_campo for nombre_campo, _etiqueta in config['campos']}
    campos_orden['id'] = 'id'
    objetos = aplicar_orden_queryset(request, objetos, campos_orden)
    return render(request, 'tipos/tipo_listado.html', {
        'config': config,
        'objetos': objetos,
    })


def tipo_alta(request, slug):
    config = _config_o_404(slug)
    FormClass = form_class_para(config)

    if request.method == 'POST':
        form = FormClass(request.POST)
        if form.is_valid():
            objeto = form.save(commit=False)
            objeto.id = _siguiente_id(config['model'])
            objeto.save(force_insert=True)
            messages.success(request, f'{config["nombre_singular"]} "{objeto}" se creó correctamente.')
            return redirect('tipos:listado', slug=slug)
    else:
        form = FormClass()

    return render(request, 'tipos/tipo_form.html', {
        'config': config,
        'form': form,
        'modo': 'alta',
    })


def tipo_modificar(request, slug, pk):
    config = _config_o_404(slug)
    FormClass = form_class_para(config)
    objeto = get_object_or_404(config['model'], pk=pk)

    if request.method == 'POST':
        form = FormClass(request.POST, instance=objeto)
        if form.is_valid():
            form.save()
            messages.success(request, f'{config["nombre_singular"]} "{objeto}" se modificó correctamente.')
            return redirect('tipos:listado', slug=slug)
    else:
        form = FormClass(instance=objeto)

    return render(request, 'tipos/tipo_form.html', {
        'config': config,
        'form': form,
        'modo': 'modificar',
        'objeto': objeto,
    })


def tipo_eliminar(request, slug, pk):
    """Confirmación + baja de un registro de cualquier catálogo de 'tipos'.

    Genérica para todo el registro: varios de estos catálogos están
    referenciados con on_delete=PROTECT desde otras apps (por ejemplo
    BancoCuentaTipoMovim desde MovimientoCaja.tipo), así que si el registro
    está en uso Django frena el borrado con ProtectedError; acá se atrapa
    para mostrar un mensaje claro en vez de un error 500.
    """
    config = _config_o_404(slug)
    objeto = get_object_or_404(config['model'], pk=pk)

    if request.method == 'POST':
        try:
            objeto.delete()
        except (ProtectedError, IntegrityError):
            messages.error(
                request,
                f'{config["nombre_singular"]} "{objeto}" no se puede eliminar porque está '
                'siendo usado en otro registro.'
            )
        else:
            messages.success(request, f'{config["nombre_singular"]} "{objeto}" se eliminó correctamente.')
        return redirect('tipos:listado', slug=slug)

    return render(request, 'tipos/tipo_eliminar_confirm.html', {
        'config': config,
        'objeto': objeto,
    })
