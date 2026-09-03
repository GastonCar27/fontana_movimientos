"""Helpers para los buscadores con autocompletado (AJAX) de entidad /
empleado / producto: el texto que se muestra en el campo cuando ya hay
algo elegido (alta con errores de validación, o edición). Reutilizado por
las vistas de varias apps para no repetir la misma lógica de armado de
texto en cada una."""


def texto_entidad_buscador(entidad):
    """Texto a mostrar en el buscador para una entidad ya seleccionada,
    ej. 'Del Libano S.R.L. (CUIT 30711486670)'."""
    if not entidad:
        return ''
    if entidad.cuit:
        return f'{entidad.nombre} (CUIT {entidad.cuit})'
    return entidad.nombre or ''


def texto_empleado_buscador(empleado):
    """Texto a mostrar en el buscador para un empleado ya seleccionado."""
    return str(empleado) if empleado else ''


def texto_producto_buscador(producto):
    """Texto a mostrar en el buscador para un producto de catálogo ya
    seleccionado."""
    return str(producto) if producto else ''
