from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from .forms import EntidadAltaForm
from .models import Rol, Entidad
from django.db.models import Max, Q
from services.ordenamiento import aplicar_orden_queryset
from services.reportes import excel_response, pdf_response

# Rango de ids que se prioriza al dar de alta una Entidad nueva (pedido
# explícitamente): si hay algún id libre en 2815-3000, se usa el más bajo
# de esos. Si el rango completo ya está ocupado, se sigue con el
# comportamiento de siempre (siguiente id disponible, por fuera del rango).
RANGO_ID_ENTIDAD_PRIORITARIO = range(2815, 3001)


def siguiente_id_entidad():
    """Calcula el id a usar para una Entidad nueva: el más bajo libre
    dentro de RANGO_ID_ENTIDAD_PRIORITARIO si hay alguno disponible, o si
    no, el siguiente id disponible fuera de ese rango (máximo id actual + 1).
    """
    ids_en_rango_ocupados = set(
        Entidad.objects.filter(
            id__gte=RANGO_ID_ENTIDAD_PRIORITARIO.start,
            id__lte=RANGO_ID_ENTIDAD_PRIORITARIO.stop - 1,
        ).values_list('id', flat=True)
    )
    for candidato in RANGO_ID_ENTIDAD_PRIORITARIO:
        if candidato not in ids_en_rango_ocupados:
            return candidato

    # Rango agotado: se sigue con el máximo id existente + 1 (comportamiento
    # habitual fuera del rango prioritario).
    maximo = Entidad.objects.aggregate(Max('id'))['id__max'] or 0
    return maximo + 1


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


def entidad_alta(request):
    """Alta de una Entidad nueva: el id lo asigna solo la vista (ver
    siguiente_id_entidad), y se pueden elegir uno o más "tipos de entidad"
    (Rol) además de los datos básicos."""
    if request.method == 'POST':
        form = EntidadAltaForm(request.POST)
        if form.is_valid():
            entidad = form.save(commit=False)
            entidad.id = siguiente_id_entidad()
            entidad.save()
            # 'roles' es la relación inversa M2M (declarada en Rol, no en
            # Entidad): un ModelForm normal no la guarda solo, hay que
            # asignarla a mano después de tener el id de la entidad.
            entidad.roles.set(form.cleaned_data['roles'])
            messages.success(request, f'Entidad "{entidad}" creada correctamente (id {entidad.id}).')
            return redirect('entidades:alta')
    else:
        form = EntidadAltaForm(initial={'activo': True})

    return render(request, 'entidades/entidad_form.html', {'form': form, 'modo': 'alta'})


# ---------------------------------------------------------------------------
# Modificación / Listado / Reportes de Entidad (menú Entidades)
# ---------------------------------------------------------------------------

def _entidades_filtradas(request):
    """Aplica los filtros de búsqueda (q, tipo, activo) usados tanto por el
    listado/modificación como por los reportes de Entidad. Centralizado
    para que ambas pantallas (y sus exportaciones) usen siempre el mismo
    criterio."""
    entidades = Entidad.objects.all().prefetch_related('roles').order_by('nombre')

    q = request.GET.get('q', '').strip()
    if q:
        filtro = Q(nombre__icontains=q) | Q(cuit__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))
        entidades = entidades.filter(filtro)

    tipo_id = request.GET.get('tipo', '').strip()
    if tipo_id.isdigit():
        entidades = entidades.filter(roles__id=int(tipo_id))

    solo_activas = request.GET.get('activo') == '1'
    if solo_activas:
        entidades = entidades.filter(activo=True)

    return entidades.distinct(), q, tipo_id, solo_activas


def entidad_listado(request):
    """Listado/búsqueda de entidades; puerta de entrada de 'Modificación'."""
    entidades, q, tipo_id, solo_activas = _entidades_filtradas(request)

    entidades = aplicar_orden_queryset(request, entidades, {
        'id': 'id',
        'nombre': 'nombre',
        'localidad': 'localidad',
    })

    return render(request, 'entidades/entidad_listado.html', {
        'entidades': entidades[:500],
        'q': q,
        'tipo_id': tipo_id,
        'solo_activas': solo_activas,
        'tipos': Rol.objects.all().order_by('nombre'),
    })


def entidad_editar(request, pk):
    entidad = get_object_or_404(Entidad, pk=pk)

    if request.method == 'POST':
        form = EntidadAltaForm(request.POST, instance=entidad)
        if form.is_valid():
            form.save()
            # 'roles' es la relación inversa M2M: no la guarda el ModelForm
            # solo, hay que asignarla a mano (ver también entidad_alta).
            entidad.roles.set(form.cleaned_data['roles'])
            messages.success(request, f'Entidad "{entidad}" se modificó correctamente.')
            return redirect('entidades:listado')
    else:
        form = EntidadAltaForm(instance=entidad, initial={'roles': entidad.roles.all()})

    return render(request, 'entidades/entidad_form.html', {
        'form': form, 'modo': 'modificar', 'entidad': entidad,
    })


def entidad_reporte(request):
    """Listado de entidades para exportar (mismos filtros que el listado de
    Modificación), pensado para revisar/entregar por Excel o PDF."""
    entidades, q, tipo_id, solo_activas = _entidades_filtradas(request)
    entidades = aplicar_orden_queryset(request, entidades, {
        'id': 'id',
        'nombre': 'nombre',
        'localidad': 'localidad',
    })

    return render(request, 'entidades/entidad_reporte.html', {
        'entidades': entidades[:500],
        'q': q,
        'tipo_id': tipo_id,
        'solo_activas': solo_activas,
        'tipos': Rol.objects.all().order_by('nombre'),
        'filtros_activos': bool(q or tipo_id or solo_activas),
    })


def _filas_reporte_entidad(entidades):
    columnas = ['ID', 'Nombre', 'CUIT', 'Localidad', 'Tipos', 'Activo']
    filas = [
        [
            ent.id,
            ent.nombre or '-',
            ent.cuit or '-',
            ent.localidad or '-',
            ', '.join(rol.nombre for rol in ent.roles.all()) or '-',
            'Sí' if ent.activo else 'No',
        ]
        for ent in entidades
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': set(),
        'anchos': [0.8, 2.4, 1.4, 1.8, 2.2, 0.8],
    }


def entidad_reporte_excel(request):
    entidades, _q, _tipo_id, _solo_activas = _entidades_filtradas(request)
    resultado = _filas_reporte_entidad(entidades)
    return excel_response('entidades', resultado)


def entidad_reporte_pdf(request):
    entidades, _q, _tipo_id, _solo_activas = _entidades_filtradas(request)
    resultado = _filas_reporte_entidad(entidades)
    return pdf_response('entidades', 'Entidades', resultado)
