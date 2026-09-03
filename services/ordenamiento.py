"""
Helpers genéricos para ordenar listados/reportes al hacer clic en el
encabezado de una columna, a partir de los parámetros GET 'orden' (nombre
de columna) y 'dir' ('asc'/'desc'). Se usan junto con el template tag
{% sort_th %} (definido en movimientos.templatetags.movimientos_extras),
que arma el link de cada encabezado conservando los demás filtros ya
aplicados en la URL.
"""


def parametros_orden(request):
    """Devuelve (campo, direccion) según los parámetros GET actuales."""
    return request.GET.get('orden', '').strip(), request.GET.get('dir', 'asc').strip()


def aplicar_orden_queryset(request, queryset, campos, default=None):
    """Ordena un queryset según el parámetro GET 'orden', si coincide con
    alguna clave de 'campos'.

    'campos' es un dict: nombre de columna (el que viaja en la URL) ->
    nombre de campo ORM (string), expresión (F(), etc.), o una tupla/lista
    de varios de estos para desempatar. 'default' tiene el mismo formato y
    se usa si no vino un 'orden' válido en la URL (si no se pasa, se deja
    el order_by() que ya traía el queryset).
    """
    campo, direccion = parametros_orden(request)
    objetivo = campos.get(campo, default)
    if objetivo is None:
        return queryset

    if not isinstance(objetivo, (list, tuple)):
        objetivo = [objetivo]

    criterios = []
    for expresion in objetivo:
        if isinstance(expresion, str):
            criterios.append('-' + expresion if direccion == 'desc' else expresion)
        else:
            criterios.append(expresion.desc() if direccion == 'desc' else expresion.asc())
    return queryset.order_by(*criterios)


def aplicar_orden_lista(request, lista, campos, default=None):
    """Ordena (con sorted()) una lista de dicts u objetos ya evaluada en
    Python, según el parámetro GET 'orden', si coincide con alguna clave de
    'campos' (dict: nombre de columna -> función que, dado un elemento de
    la lista, devuelve la clave de ordenamiento). 'default' tiene el mismo
    formato y se usa si no vino un 'orden' válido en la URL.
    """
    campo, direccion = parametros_orden(request)
    clave = campos.get(campo, default)
    if clave is None:
        return lista
    return sorted(lista, key=clave, reverse=(direccion == 'desc'))
