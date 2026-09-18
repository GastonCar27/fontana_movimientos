"""Helpers para los buscadores con autocompletado (AJAX) de entidad /
producto: el texto que se muestra en el campo cuando ya hay algo elegido
(alta con errores de validación, o edición). Reutilizado por las vistas de
varias apps para no repetir la misma lógica de armado de texto en cada una.

Nota: ya no hay un texto_empleado_buscador aparte -- los "empleados" pasaron
a ser Entidad con un tipo de entidad (Rol) puntual (ver
solicitudes_compra/models.py y entidades/migrations/0009_seed_tipos_entidad_empleado.py),
así que usan texto_entidad_buscador(entidad, campo_documento='documento_nro')
como cualquier otra entidad identificada por DNI."""


def texto_entidad_buscador(entidad, campo_documento='cuit'):
    """Texto a mostrar en el buscador para una entidad ya seleccionada, ej.
    'Del Libano S.R.L. (CUIT 30711486670)'.

    Por default se identifica por CUIT (empresas/proveedores). Para
    personas físicas identificadas por DNI (ej. choferes, ver
    remitos/forms.py: ROL_CHOFER) pasar campo_documento='documento_nro' para
    que muestre 'DNI ...' en su lugar."""
    if not entidad:
        return ''
    if campo_documento == 'documento_nro':
        if entidad.documento_nro:
            return f'{entidad.nombre} (DNI {entidad.documento_nro})'
        return entidad.nombre or ''
    if entidad.cuit:
        return f'{entidad.nombre} (CUIT {entidad.cuit})'
    return entidad.nombre or ''


def texto_producto_buscador(producto):
    """Texto a mostrar en el buscador para un producto de catálogo ya
    seleccionado."""
    return str(producto) if producto else ''
