from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from .models import Rol, Entidad
from django.db.models import Q


def entidad_buscar(request):
    """
    Devuelve, en JSON, hasta 20 entidades cuyo nombre o CUIT contengan el
    texto buscado, o cuyo ID coincida exactamente (si lo buscado es
    numérico). Endpoint centralizado para los buscadores de proveedor /
    entidad emisora / entidad receptora de las apps que no tenían uno propio
    (movimientos, movimientos_caja, solicitudes_compra); comprobantes y
    liquidaciones ya tenían el suyo y siguen usándolo tal cual.
    """
    q = request.GET.get('q', '').strip()
    resultados = []
    if len(q) >= 2:
        filtro = Q(nombre__icontains=q) | Q(cuit__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))
        entidades = Entidad.objects.filter(filtro).order_by('nombre')[:20]
        resultados = [
            {'id': ent.id, 'text': f'{ent.nombre} (CUIT {ent.cuit})' if ent.cuit else ent.nombre}
            for ent in entidades
        ]
    return JsonResponse({'resultados': resultados})


class RolBusquedaListView(ListView):
    template_name = 'roles/search.html'

    def get_queryset(self):
        filters = Q(title__icontains=self.query()) | Q(category__title__icontains=self.query())
        return Rol.objects.filter(filters)


# Create your views here.

class RolListView(ListView):
    template_name = 'index.html'
    queryset = Rol.objects.all().order_by('id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['message'] = 'Listado de roles'
        context['roles'] = context['rol_list']
        return context


class RolSearchListView(ListView):
    template_name = 'roles/search.html'

    def get_queryset(self):
        # return Rol.objects.filter(nombre=self.query()) #nombre completo
        return Rol.objects.filter(
            nombre__icontains=self.query())  # contiene es un like where en la tabla, la i significa que no distingue mayusculas de minisculas

    def query(self):
        return self.request.GET.get('q')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.query()
        context['count'] = context['rol_list'].count()
        return context


class RolDetailView(DetailView):  # id -> pk busca un rol por el id por default
    model = Rol
    template_name = 'roles/rol.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print("contexto", context)
        return context


from django.shortcuts import render

# Create your views here.
