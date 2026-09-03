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
