from django.conf import settings


def entorno_bd(request):
    """Context processor global: expone en todos los templates si la
    conexión activa (settings.DATABASES['default']) apunta a una base de
    datos local, para poder mostrar el aviso "BD de Desarrollo" en la
    barra de navegación en todo momento, sin tener que repetirlo view por
    view.

    Se considera "local" un HOST vacío, 'localhost' o '127.0.0.1' (con o
    sin espacios / mayúsculas, tal cual puede quedar en el .env)."""
    db_config = settings.DATABASES.get('default', {}) or {}
    host = (db_config.get('HOST') or '').strip().lower()
    nombre_bd = db_config.get('NAME') or ''

    es_bd_local = host in ('', 'localhost', '127.0.0.1')

    return {
        'es_bd_local': es_bd_local,
        'bd_host': host or 'localhost',
        'bd_nombre': nombre_bd,
    }


# Secciones del menú de navegación (navbar.html) que están restringidas por
# grupo de usuario. "Ingreso", "Salida" y "Reportes" NO están acá a propósito:
# esas quedan visibles para cualquier usuario logueado, sin restricción.
# Cada nombre de acá tiene que coincidir EXACTO con el nombre del grupo de
# Django (ver entidades/migrations/0002_grupos_menu.py, que los crea solos).
GRUPOS_MENU = [
    'Rankings',
    'Movimientos de Productos',
    'Movimientos de Caja',
    'Comprobantes',
    'Liquidaciones',
    'Retenciones',
    'Tipos',
    'Solicitudes de Compra',
    'Empleados',
    'Otros',
]


def permisos_menu(request):
    """Context processor global: expone en navbar.html, para el usuario
    logueado, qué secciones del menú puede ver.

    Un superusuario, o quien esté en el grupo "Administrador", ve todas las
    secciones de la lista de arriba sin necesidad de estar además en cada
    grupo puntual. Cualquier otro usuario solo ve una sección si está en el
    grupo con ese mismo nombre (asignable desde /admin/, en la ficha del
    usuario, campo "Groups").
    """
    user = request.user
    if not user.is_authenticated:
        return {}

    nombres_grupos = set(user.groups.values_list('name', flat=True))
    ve_todo = user.is_superuser or 'Administrador' in nombres_grupos

    def puede_ver(nombre_grupo):
        return ve_todo or nombre_grupo in nombres_grupos

    return {
        'puede_ver_rankings': puede_ver('Rankings'),
        'puede_ver_movimientos_productos': puede_ver('Movimientos de Productos'),
        'puede_ver_movimientos_caja': puede_ver('Movimientos de Caja'),
        'puede_ver_comprobantes': puede_ver('Comprobantes'),
        'puede_ver_liquidaciones': puede_ver('Liquidaciones'),
        'puede_ver_retenciones': puede_ver('Retenciones'),
        'puede_ver_tipos': puede_ver('Tipos'),
        'puede_ver_solicitudes_compra': puede_ver('Solicitudes de Compra'),
        'puede_ver_empleados': puede_ver('Empleados'),
        'puede_ver_otros': puede_ver('Otros'),
    }
