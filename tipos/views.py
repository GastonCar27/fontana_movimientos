from django import forms
from django.contrib import messages
from django.db import IntegrityError, transaction
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


def _id_sugerido(config, valor):
    """Si el catálogo tiene 'id_sugerido_desde' (por ahora sólo Tipo de
    Comprobante -> 'id_afip'), convierte ese valor a número cuando se
    puede: "082" -> 82, " 11 " -> 11. Si no es un número entero positivo
    devuelve None (ej. "A", "", None)."""
    if not config.get('id_sugerido_desde') or valor is None:
        return None
    texto = str(valor).strip()
    if not texto.isdigit():
        return None
    numero = int(texto)
    return numero if numero > 0 else None


def _form_class_con_id(config, modo, objeto=None):
    """Igual que form_class_para(config), pero si el catálogo tiene
    `'id_editable': True` en el registry le agrega un campo "ID".

    * Alta (`id_editable`): opcional. Vacío -> se asigna solo (el ID
      sugerido por el ID AFIP si el catálogo lo tiene y está libre, si no
      el próximo disponible). Cargado -> se usa tal cual, si está libre.
      Casos: "Tipo de Retención INYM" (24/09/2026) y "Tipo de
      Comprobante" (02/10/2026).
    * Modificación (`id_editable_en_modificar`, por ahora SÓLO "Tipo de
      Comprobante", pedido de Gastón 02/10/2026): obligatorio, viene
      cargado con el ID actual. Si se cambia, se valida en
      `tipo_modificar` que el nuevo no lo use otro registro (nunca se
      pisa un ID existente) y se actualizan las columnas de otras tablas
      que guardan ese ID (`referencias_id` del registry). En los demás
      catálogos el ID sigue sin poder cambiarse, porque puede estar
      referenciado desde tablas que no están listadas (por ejemplo
      RetencionInym.id_tipo_tarifa)."""
    FormClass = form_class_para(config)
    if modo == 'alta' and not config.get('id_editable'):
        return FormClass
    if modo == 'modificar' and not config.get('id_editable_en_modificar'):
        return FormClass

    ayuda = config.get('ayuda_id') or (
        'Dejalo vacío para asignar el próximo disponible automáticamente.'
    )
    if modo == 'alta' and config.get('id_sugerido_desde'):
        ayuda += ' Si lo dejás vacío y el ID AFIP es un número libre, se usa ese número.'
    if modo == 'modificar' and objeto is not None:
        sugerido = _id_sugerido(config, getattr(objeto, config.get('id_sugerido_desde') or '', None))
        if sugerido and sugerido != objeto.pk:
            ocupante = config['model'].objects.filter(pk=sugerido).first()
            if ocupante is None:
                ayuda += f' Según el ID AFIP, el ID sugerido es {sugerido} (está libre).'
            else:
                ayuda += f' Según el ID AFIP sería {sugerido}, pero ya lo usa "{ocupante}".'

    class FormClassConId(FormClass):
        id = forms.IntegerField(
            required=(modo == 'modificar'),
            min_value=1,
            label='ID',
            help_text=ayuda,
            widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # "ID" primero, antes de los campos propios del catálogo.
            self.fields = {'id': self.fields.pop('id'), **self.fields}
            if modo == 'modificar' and self.instance is not None and self.instance.pk is not None:
                self.fields['id'].initial = self.instance.pk

    return FormClassConId


def _form_class_para_alta(config):
    """Compatibilidad: antes sólo existía la variante de alta."""
    return _form_class_con_id(config, 'alta')


def _modelo_referencia(app_label, nombre_modelo):
    from django.apps import apps
    return apps.get_model(app_label, nombre_modelo)


def _cambiar_id(config, id_viejo, id_nuevo):
    """Cambia la clave primaria de un registro de catálogo de id_viejo a
    id_nuevo, y actualiza las columnas de otras tablas que guardan ese ID
    (`referencias_id` del registry). Se llama dentro de una transacción y
    DESPUÉS de validar que id_nuevo está libre.

    Orden: primero el propio registro (si la columna de la otra tabla
    tiene FK con ON UPDATE CASCADE, la base ya la actualiza sola) y
    después cada referencia explícitamente (para las que no tienen FK, y
    por las dudas para las que sí: en ese caso no encuentra filas con el
    ID viejo y no hace nada). Devuelve una lista de (descripción,
    cantidad) con lo que se movió."""
    referencias = []
    for app_label, nombre_modelo, campo, descripcion in config.get('referencias_id', []):
        modelo = _modelo_referencia(app_label, nombre_modelo)
        cantidad = modelo.objects.filter(**{campo: id_viejo}).count()
        referencias.append((modelo, campo, descripcion, cantidad))

    nombre_pk = config['model']._meta.pk.name
    actualizados = config['model'].objects.filter(pk=id_viejo).update(**{nombre_pk: id_nuevo})
    if actualizados != 1:
        raise RuntimeError(f'No se encontró el registro con ID {id_viejo} para cambiarle el ID.')

    resultado = []
    for modelo, campo, descripcion, cantidad in referencias:
        modelo.objects.filter(**{campo: id_viejo}).update(**{campo: id_nuevo})
        if cantidad:
            resultado.append((descripcion, cantidad))
    return resultado


def tipo_alta(request, slug):
    config = _config_o_404(slug)
    FormClass = _form_class_con_id(config, 'alta')

    if request.method == 'POST':
        form = FormClass(request.POST)
        if form.is_valid():
            id_elegido = form.cleaned_data.get('id') if config.get('id_editable') else None
            if id_elegido and config['model'].objects.filter(pk=id_elegido).exists():
                ocupante = config['model'].objects.get(pk=id_elegido)
                form.add_error(
                    'id',
                    f'Ya existe un {config["nombre_singular"].lower()} con el ID {id_elegido} '
                    f'("{ocupante}"). Elegí otro: no se sobrescribe un ID existente.'
                )
            else:
                objeto = form.save(commit=False)
                aviso = None
                if not id_elegido:
                    sugerido = _id_sugerido(config, getattr(objeto, config.get('id_sugerido_desde') or '', None))
                    if sugerido and not config['model'].objects.filter(pk=sugerido).exists():
                        id_elegido = sugerido
                    elif sugerido:
                        ocupante = config['model'].objects.get(pk=sugerido)
                        aviso = (
                            f'El ID {sugerido} (según el ID AFIP) ya lo usa "{ocupante}", '
                            'así que se asignó el próximo disponible.'
                        )
                objeto.id = id_elegido or _siguiente_id(config['model'])
                objeto.save(force_insert=True)
                messages.success(request, f'{config["nombre_singular"]} "{objeto}" se creó correctamente.')
                if aviso:
                    messages.warning(request, aviso)
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
    objeto = get_object_or_404(config['model'], pk=pk)
    FormClass = _form_class_con_id(config, 'modificar', objeto)
    id_editable = bool(config.get('id_editable_en_modificar'))

    if request.method == 'POST':
        form = FormClass(request.POST, instance=objeto)
        if form.is_valid():
            id_viejo = pk
            id_nuevo = form.cleaned_data.get('id') if id_editable else id_viejo
            if id_nuevo != id_viejo and config['model'].objects.filter(pk=id_nuevo).exists():
                ocupante = config['model'].objects.get(pk=id_nuevo)
                form.add_error(
                    'id',
                    f'El ID {id_nuevo} ya lo usa "{ocupante}". No se sobrescribe un ID '
                    'existente: elegí otro o primero cambiale el ID a ese registro.'
                )
            else:
                movidos = []
                with transaction.atomic():
                    form.save()
                    if id_nuevo != id_viejo:
                        movidos = _cambiar_id(config, id_viejo, id_nuevo)
                objeto = config['model'].objects.get(pk=id_nuevo)
                messages.success(request, f'{config["nombre_singular"]} "{objeto}" se modificó correctamente.')
                if id_nuevo != id_viejo:
                    detalle = ', '.join(f'{cantidad} {descripcion}' for descripcion, cantidad in movidos)
                    messages.info(
                        request,
                        f'El ID cambió de {id_viejo} a {id_nuevo}.'
                        + (f' Se actualizaron también: {detalle}.' if detalle else ' No había registros que lo usaran.')
                    )
                return redirect('tipos:listado', slug=slug)
    else:
        form = FormClass(instance=objeto)

    return render(request, 'tipos/tipo_form.html', {
        'config': config,
        'form': form,
        'modo': 'modificar',
        'objeto': objeto,
        'id_editable': id_editable,
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
