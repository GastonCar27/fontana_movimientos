from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth import authenticate
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_not_required, login_required
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import RegisterForm


# login_not_required: esta vista tiene que quedar SIEMPRE accesible sin
# sesión iniciada, porque es la única puerta de entrada — si quedara detrás
# del login (como el resto del sitio, ver LoginRequiredMiddleware en
# settings/base.py) nadie podría loguearse nunca.
@login_not_required
def login_view(request):
    siguiente = request.POST.get('next') or request.GET.get('next', '')

    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, 'Bienvenido {}'.format(user.username))
            # Si LoginRequiredMiddleware mandó para acá con "?next=<url>"
            # (alguien intentó abrir una página sin estar logueado), lo
            # devolvemos ahí. Se valida con url_has_allowed_host_and_scheme
            # para no permitir que "next" mande a un sitio externo. Sin
            # "next" (login directo desde /usuarios/login), va al listado de
            # liquidaciones como página de inicio por defecto.
            if siguiente and url_has_allowed_host_and_scheme(
                siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(siguiente)
            return redirect('liquidaciones:listado')

        else:
            messages.error(request, "Usuario Incorrecto")

    return render(request, 'users/login.html', {
        'next': siguiente,
    })

def logout_view(request):
    logout(request)
    messages.success(request,'Sesión cerrada exitosamente')
    return redirect('login')

# login_required explícito (además de quedar protegida por
# LoginRequiredMiddleware): solo alguien ya logueado puede dar de alta un
# usuario nuevo.
@login_required
def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        # OJO: no hacer login(request, user) acá — reemplazaría la sesión de
        # quien está creando el usuario nuevo por la del usuario recién
        # creado, "expulsando" a quien lo estaba dando de alta.
        form.save()
        messages.success(request, "Usuario creado correctamente")
        return redirect('register')
    return render(request, 'users/register.html', {'form': form})

