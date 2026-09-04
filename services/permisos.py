"""
Decorator para restringir una vista a un grupo puntual del menú (ver
GRUPOS_MENU / permisos_menu en fontana_movimientos/context_processors.py).

Hasta ahora esas restricciones eran solo visuales (el link se ocultaba del
navbar con {% if puede_ver_X %}, pero quien conociera la URL de memoria
podía entrar igual sin estar en el grupo). Este decorator agrega el mismo
chequeo a nivel de vista, para que la URL directa también quede bloqueada.

Uso:
    from services.permisos import requiere_grupo

    @requiere_grupo('Rankings')
    def mi_vista(request):
        ...
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def requiere_grupo(nombre_grupo, redirigir_a='liquidaciones:listado'):
    """Un superusuario, o quien esté en el grupo 'Administrador', pasa
    siempre (mismo criterio que permisos_menu). Cualquier otro usuario solo
    pasa si está en el grupo 'nombre_grupo'. Si no está logueado, va al
    login (aunque en los hechos LoginRequiredMiddleware ya lo intercepta
    antes de llegar acá). Si está logueado pero no tiene el grupo, se le
    muestra un mensaje de error y se lo redirige a 'redirigir_a' en vez de
    dejarlo entrar."""
    def decorador(vista):
        @wraps(vista)
        def vista_envuelta(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            nombres_grupos = set(user.groups.values_list('name', flat=True))
            if user.is_superuser or 'Administrador' in nombres_grupos or nombre_grupo in nombres_grupos:
                return vista(request, *args, **kwargs)

            messages.error(request, 'No tenés permiso para acceder a esa sección.')
            return redirect(redirigir_a)
        return vista_envuelta
    return decorador
