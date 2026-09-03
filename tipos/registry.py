"""Catálogo único de todas las tablas "tipo" que se administran con el
motor genérico de esta app (alta / modificación / listado).

Agregar un caso nuevo acá (y nada más) alcanza para que aparezca en el
menú "Tipos", con sus URLs y sus pantallas: no hace falta escribir un
form.py / views.py / template por cada tabla.

Cada entrada:
    slug:            identificador corto usado en la URL (/tipos/<slug>/...)
    nombre_singular:  usado en títulos ("Nuevo <nombre_singular>")
    nombre_plural:    usado en el menú y en el listado
    model:            clase de modelo Django (managed=False, ya mapeada
                       a la tabla real)
    campos:           lista de tuplas (nombre_de_campo, etiqueta) que se
                       editan en el alta/modificación y se muestran como
                       columnas en el listado
    orden:            campo por el que se ordena el listado

Están en orden alfabético por nombre de tabla (que es, a la vez, el
orden en que se dibuja el menú "Tipos" en la barra de navegación, tal
como se pidió).
"""

from comprobantes.models import ComprobanteTipo, DocumentoTipo, SectorTipo
from entidades.models import Inym_Operador_Tipo
from movimientos_caja.models import (
    BancoCuentaTipo,
    BancoCuentaTipoMovim,
    MovimientoCajaConceptoTipo,
)
from productos.models import ItemTipo
from retenciones_inym.models import InymRetencionTipo

from .models import BancoCuentaTipoProducto, CuentaTipo, ProductoTipo


TIPOS_REGISTRY = [
    {
        'slug': 'banco-cuenta-tipo',
        'nombre_singular': 'Tipo de Cuenta Bancaria',
        'nombre_plural': 'Tipos de Cuenta Bancaria',
        'model': BancoCuentaTipo,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'banco-cuenta-tipo-producto',
        'nombre_singular': 'Tipo de Producto de Cuenta Bancaria',
        'nombre_plural': 'Tipos de Producto de Cuenta Bancaria',
        'model': BancoCuentaTipoProducto,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'bancocuenta-tipomovim',
        'nombre_singular': 'Tipo de Movimiento de Caja',
        'nombre_plural': 'Tipos de Movimiento de Caja',
        'model': BancoCuentaTipoMovim,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'comprobante-tipo',
        'nombre_singular': 'Tipo de Comprobante',
        'nombre_plural': 'Tipos de Comprobante',
        'model': ComprobanteTipo,
        'campos': [
            ('nombre', 'Nombre'),
            ('id_afip', 'ID AFIP'),
            ('abreviatura', 'Abreviatura'),
        ],
        'orden': 'nombre',
    },
    {
        'slug': 'cuenta-tipo',
        'nombre_singular': 'Tipo de Cuenta',
        'nombre_plural': 'Tipos de Cuenta',
        'model': CuentaTipo,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'documento-tipo',
        'nombre_singular': 'Tipo de Documento',
        'nombre_plural': 'Tipos de Documento',
        'model': DocumentoTipo,
        # ojo: en esta tabla el campo de nombre se llama "tipo", no "nombre"
        'campos': [('tipo', 'Tipo')],
        'orden': 'tipo',
    },
    {
        'slug': 'inym-operador-tipo',
        'nombre_singular': 'Tipo de Operador INYM',
        'nombre_plural': 'Tipos de Operador INYM',
        'model': Inym_Operador_Tipo,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'inym-retencion-tipo',
        'nombre_singular': 'Tipo de Retención INYM',
        'nombre_plural': 'Tipos de Retención INYM',
        'model': InymRetencionTipo,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'item-tipo',
        'nombre_singular': 'Tipo de Ítem',
        'nombre_plural': 'Tipos de Ítem',
        'model': ItemTipo,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'movimiento-caja-concepto-tipo',
        'nombre_singular': 'Tipo de Concepto de Caja',
        'nombre_plural': 'Tipos de Concepto de Caja',
        'model': MovimientoCajaConceptoTipo,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'producto-tipo',
        'nombre_singular': 'Tipo de Producto',
        'nombre_plural': 'Tipos de Producto',
        'model': ProductoTipo,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
    {
        'slug': 'sector-tipo',
        'nombre_singular': 'Tipo de Sector',
        'nombre_plural': 'Tipos de Sector',
        'model': SectorTipo,
        'campos': [('nombre', 'Nombre')],
        'orden': 'nombre',
    },
]


def obtener_config(slug):
    """Devuelve la entrada del registro para ese slug, o None."""
    for config in TIPOS_REGISTRY:
        if config['slug'] == slug:
            return config
    return None
