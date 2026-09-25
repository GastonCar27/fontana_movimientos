from decimal import Decimal, InvalidOperation

from django import template
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import format_html

register = template.Library()


@register.filter(name='separador_miles')
def separador_miles(valor, decimales=2):
    """Formatea un número con separador de miles '.' y decimal ',' (formato
    argentino), por ejemplo 1234567.891 con decimales=2 -> '1.234.567,89'.

    Se usa para mostrar montos (como el total de un movimiento, o la suma de
    totales) de forma más legible en los listados y reportes.
    """
    if valor in (None, ''):
        return ''
    try:
        decimales = int(decimales)
    except (TypeError, ValueError):
        decimales = 2
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return valor
    # El formato con coma para miles y punto para decimal es el que da
    # Python por defecto (estilo EE.UU.); acá se invierten para llegar al
    # formato argentino (punto de miles, coma decimal).
    formateado = f'{numero:,.{decimales}f}'
    formateado = formateado.replace(',', '￿').replace('.', ',').replace('￿', '.')
    return formateado


@register.filter(name='liquidaciones_validas')
def liquidaciones_validas(movimiento):
    """Vínculos a liquidación de un movimiento de caja (movimiento.liquidaciones,
    el related_name de LiquidacionMovimiento) que todavía apuntan a una
    Liquidacion existente.

    Se usa en vez de filtrar directo en la plantilla con `{% if lm.liquidacion %}`
    porque, si el vínculo quedó "huérfano" (id_liquidacion apunta a una fila que
    ya no existe -- ej. un borrado manual en la base, dado que estas tablas son
    managed=False sin FK real), acceder a lm.liquidacion no da None: Django
    lanza una excepción al resolver la relación. Django Template la resuelve
    sola como "atributo vacío" (silenciosa), así que el `{% if %}` da falso iguel
    -- pero el `{% for %}...{% empty %}` de al lado NO entra en el `empty`
    porque el queryset de vínculos no está vacío, sólo el que está roto es
    éste. Resultado: la celda quedaba en blanco (25/09/2026, reporte de
    Gastón) -- ni el número de liquidación, ni "Sin liquidar", nada.

    Filtrando acá (en Python, con el try/except explícito que hace falta
    fuera de una plantilla) se puede volver a usar el patrón
    `{% for %}...{% empty %}Sin liquidar{% endfor %}` con la garantía de que,
    si no queda ningún vínculo válido, cae siempre en el `empty`.
    """
    validos = []
    for lm in movimiento.liquidaciones.all():
        try:
            if lm.liquidacion:
                validos.append(lm)
        except ObjectDoesNotExist:
            continue
    return validos


@register.simple_tag(takes_context=True)
def sort_th(context, campo, etiqueta):
    """Arma el contenido ordenable de un encabezado de columna: un link
    que, al hacer clic, ordena la tabla por 'campo' (usando los parámetros
    GET 'orden'/'dir' que interpreta services.ordenamiento en la vista), con
    una flechita que indica el campo y la dirección de orden activos, sin
    perder los filtros ya aplicados. Se usa así:

        <th class="text-end">{% sort_th 'monto' 'Monto' %}</th>
    """
    request = context['request']
    orden_actual = request.GET.get('orden', '')
    dir_actual = request.GET.get('dir', 'asc')

    if orden_actual == campo:
        nueva_dir = 'desc' if dir_actual == 'asc' else 'asc'
        flecha = '▲' if dir_actual == 'asc' else '▼'
    else:
        nueva_dir = 'asc'
        flecha = ''

    parametros = request.GET.copy()
    parametros['orden'] = campo
    parametros['dir'] = nueva_dir

    return format_html(
        '<a href="?{}" class="text-reset text-decoration-none d-inline-flex align-items-center gap-1">'
        '{}<span class="text-muted small">{}</span></a>',
        parametros.urlencode(), etiqueta, flecha,
    )
