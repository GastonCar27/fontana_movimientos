from .registry import TIPOS_REGISTRY


def tipos_menu(request):
    """Expone el listado de catálogos "tipo" (ya en el orden alfabético
    del registro) para poder armar el submenú "Tipos" en navbar.html sin
    tener que tocar cada view del proyecto."""
    return {
        'tipos_menu': [
            {'slug': c['slug'], 'nombre_plural': c['nombre_plural']}
            for c in TIPOS_REGISTRY
        ],
    }
