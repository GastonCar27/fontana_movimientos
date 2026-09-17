from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.utils.text import slugify
from .forms import EntidadAltaForm, EntidadRolRapidoForm, RolForm
from .models import Rol, Entidad
from django.db.models import Count, Max, Q
from services.buscadores import texto_entidad_buscador
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

    Admite un parámetro opcional 'rol' (id numérico o nombre exacto de un
    Rol) para restringir el resultado a las entidades que tengan ese tipo de
    entidad asignado -- lo usa, por ejemplo, el alta de Remito para que el
    buscador de transportista/chofer sólo muestre entidades con ese rol
    (ver también entidad_crear_rapido, acá abajo, para cuando no aparece la
    que se busca).

    Admite también un parámetro opcional 'mostrar' ('cuit', el default, o
    'documento_nro') para elegir qué dato se muestra entre paréntesis en el
    texto de cada resultado (ver services.buscadores.texto_entidad_buscador)
    -- lo usa el alta de Remito para que el buscador de chofer muestre el
    DNI en vez del CUIT, ya que un chofer es una persona, no una empresa.
    """
    q = request.GET.get('q', '').strip()
    rol_param = request.GET.get('rol', '').strip()
    campo_documento = request.GET.get('mostrar', 'cuit').strip()
    resultados = []
    if len(q) >= 2:
        filtro = Q(nombre__icontains=q) | Q(cuit__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q)) | Q(documento_nro__icontains=q)
        entidades = Entidad.objects.filter(filtro)
        if rol_param:
            if rol_param.isdigit():
                entidades = entidades.filter(roles__id=int(rol_param))
            else:
                entidades = entidades.filter(roles__nombre__iexact=rol_param)
        entidades = entidades.distinct().order_by('nombre')[:20]
        resultados = [
            {'id': ent.id, 'text': texto_entidad_buscador(ent, campo_documento=campo_documento)}
            for ent in entidades
        ]
    return JsonResponse({'resultados': resultados})


@transaction.atomic
def entidad_crear_rapido(request):
    """
    Alta rápida (AJAX) de una entidad con un tipo de entidad (Rol) puntual
    ya asignado, para cuando el buscador de entidad_buscar (arriba, con
    ?rol=...) no encuentra la que se busca. Si ya existe una entidad con el
    mismo CUIT no se duplica: se reutiliza esa entidad y sólo se le agrega
    el rol si todavía no lo tenía. Se manda por POST el id del Rol (campo
    'rol') además de los datos de EntidadRolRapidoForm.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)

    rol_id = request.POST.get('rol', '').strip()
    if not rol_id.isdigit():
        return JsonResponse(
            {'errores': {'rol': [{'message': 'Falta indicar el tipo de entidad.'}]}}, status=400
        )
    rol = get_object_or_404(Rol, pk=rol_id)

    form = EntidadRolRapidoForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'errores': form.errors.get_json_data()}, status=400)

    cuit = form.cleaned_data['cuit'].strip()
    documento_nro = form.cleaned_data.get('documento_nro')
    nombre = form.cleaned_data['nombre'].strip()

    # Se busca primero por DNI y si no por CUIT (sólo se completa uno de
    # los dos, según el rol -- ver EntidadRolRapidoForm, en forms.py, y
    # remito_form.html): choferes (personas) se identifican por DNI,
    # transportistas (empresas) por CUIT.
    entidad = None
    if documento_nro:
        entidad = Entidad.objects.filter(documento_nro=documento_nro).first()
    elif cuit:
        entidad = Entidad.objects.filter(cuit=cuit).first()

    if entidad is None:
        entidad = Entidad(
            id=siguiente_id_entidad(), nombre=nombre,
            cuit=cuit or None, documento_nro=documento_nro, activo=True,
        )
        entidad.save()

    entidad.roles.add(rol)

    campo_documento = 'documento_nro' if documento_nro else 'cuit'
    return JsonResponse({'id': entidad.id, 'text': texto_entidad_buscador(entidad, campo_documento=campo_documento)})


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


def _entidades_duplicadas(cuit, documento_nro, excluir_pk=None):
    """Busca otras entidades que ya tengan cargado el mismo CUIT o el mismo
    DNI (documento_nro) que se está por guardar. La usan tanto la
    advertencia de alta/edición (ver entidad_alta/entidad_editar, acá
    abajo) como, apoyándose en el mismo criterio de "mismo valor = mismo
    dato", el listado de duplicados ya existentes en la base (ver
    entidad_duplicados más abajo).

    Devuelve una lista de tuplas (entidad, campo, valor); una misma
    entidad puede aparecer dos veces si coincide tanto en CUIT como en DNI.
    No filtra por 'activo': una entidad dada de baja sigue siendo un
    duplicado real a los fines de esta advertencia. 'excluir_pk' se usa en
    la edición para no compararse contra una misma."""
    coincidencias = []
    if cuit:
        qs = Entidad.objects.filter(cuit=cuit)
        if excluir_pk is not None:
            qs = qs.exclude(pk=excluir_pk)
        coincidencias += [(ent, 'CUIT', cuit) for ent in qs]
    if documento_nro:
        qs = Entidad.objects.filter(documento_nro=documento_nro)
        if excluir_pk is not None:
            qs = qs.exclude(pk=excluir_pk)
        coincidencias += [(ent, 'DNI', documento_nro) for ent in qs]
    return coincidencias


def entidad_alta(request):
    """Alta de una Entidad nueva: el id lo asigna solo la vista (ver
    siguiente_id_entidad), y se pueden elegir uno o más "tipos de entidad"
    (Rol) además de los datos básicos.

    Si el CUIT o el DNI cargado ya lo tiene otra entidad, no se bloquea el
    alta (el pedido fue una "advertencia", no una validación dura): se
    vuelve a mostrar el formulario con el aviso y, si igual se quiere
    continuar, un botón "Guardar de todos modos" que reenvía el mismo POST
    con 'confirmar_duplicado=1' (ver entidad_form.html)."""
    duplicados = []
    if request.method == 'POST':
        form = EntidadAltaForm(request.POST)
        if form.is_valid():
            cuit = (form.cleaned_data.get('cuit') or '').strip()
            documento_nro = form.cleaned_data.get('documento_nro')
            duplicados = _entidades_duplicadas(cuit, documento_nro)
            confirmar_duplicado = request.POST.get('confirmar_duplicado') == '1'

            if not duplicados or confirmar_duplicado:
                entidad = form.save(commit=False)
                entidad.id = siguiente_id_entidad()
                entidad.save()
                # 'roles' es la relación inversa M2M (declarada en Rol, no
                # en Entidad): un ModelForm normal no la guarda solo, hay
                # que asignarla a mano después de tener el id de la
                # entidad.
                entidad.roles.set(form.cleaned_data['roles'])
                messages.success(request, f'Entidad "{entidad}" creada correctamente (id {entidad.id}).')
                return redirect('entidades:alta')
    else:
        form = EntidadAltaForm(initial={'activo': True})

    return render(request, 'entidades/entidad_form.html', {
        'form': form, 'modo': 'alta', 'duplicados': duplicados,
    })


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
    """Edición de una Entidad existente. Misma advertencia (no bloqueante)
    de CUIT/DNI duplicado que entidad_alta, excluyendo a la propia entidad
    de la comparación (si no, siempre "chocaría" contra sí misma)."""
    entidad = get_object_or_404(Entidad, pk=pk)
    duplicados = []

    if request.method == 'POST':
        form = EntidadAltaForm(request.POST, instance=entidad)
        if form.is_valid():
            cuit = (form.cleaned_data.get('cuit') or '').strip()
            documento_nro = form.cleaned_data.get('documento_nro')
            duplicados = _entidades_duplicadas(cuit, documento_nro, excluir_pk=entidad.pk)
            confirmar_duplicado = request.POST.get('confirmar_duplicado') == '1'

            if not duplicados or confirmar_duplicado:
                form.save()
                # 'roles' es la relación inversa M2M: no la guarda el
                # ModelForm solo, hay que asignarla a mano (ver también
                # entidad_alta).
                entidad.roles.set(form.cleaned_data['roles'])
                messages.success(request, f'Entidad "{entidad}" se modificó correctamente.')
                return redirect('entidades:listado')
    else:
        form = EntidadAltaForm(instance=entidad, initial={'roles': entidad.roles.all()})

    return render(request, 'entidades/entidad_form.html', {
        'form': form, 'modo': 'modificar', 'entidad': entidad, 'duplicados': duplicados,
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


# ---------------------------------------------------------------------------
# Entidades con CUIT/DNI duplicado (datos ya cargados a revisar/corregir)
# ---------------------------------------------------------------------------

def _grupos_entidades_duplicadas():
    """Recorre TODA la base (sin los filtros de búsqueda de
    _entidades_filtradas: esto es un reporte de "cosas para revisar", no
    una pantalla de trabajo diario) y arma un grupo por cada valor de CUIT
    que se repite en más de una entidad, y otro por cada valor de DNI
    (documento_nro) que se repite. Usado por entidad_duplicados y su
    exportación a Excel/PDF."""
    grupos = []

    cuits_repetidos = (
        Entidad.objects.exclude(cuit__isnull=True).exclude(cuit='')
        .values('cuit').annotate(cantidad=Count('id')).filter(cantidad__gt=1)
        .order_by('cuit')
    )
    for fila in cuits_repetidos:
        entidades = Entidad.objects.filter(cuit=fila['cuit']).prefetch_related('roles').order_by('id')
        grupos.append({'campo': 'CUIT', 'valor': fila['cuit'], 'entidades': list(entidades)})

    documentos_repetidos = (
        Entidad.objects.exclude(documento_nro__isnull=True)
        .values('documento_nro').annotate(cantidad=Count('id')).filter(cantidad__gt=1)
        .order_by('documento_nro')
    )
    for fila in documentos_repetidos:
        entidades = Entidad.objects.filter(documento_nro=fila['documento_nro']).prefetch_related('roles').order_by('id')
        grupos.append({'campo': 'DNI', 'valor': fila['documento_nro'], 'entidades': list(entidades)})

    return grupos


def entidad_duplicados(request):
    """Listado de entidades ya cargadas que comparten CUIT o DNI con otra
    (dato ya existente en la base, a diferencia de la advertencia de
    alta/edición -- ver _entidades_duplicadas -- que compara contra lo que
    se está por guardar)."""
    grupos = _grupos_entidades_duplicadas()
    return render(request, 'entidades/entidad_duplicados.html', {'grupos': grupos})


def _filas_reporte_duplicados(grupos):
    columnas = ['Campo duplicado', 'Valor', 'ID', 'Nombre', 'Localidad', 'Tipos', 'Activo']
    filas = [
        [
            grupo['campo'],
            grupo['valor'],
            ent.id,
            ent.nombre or '-',
            ent.localidad or '-',
            ', '.join(rol.nombre for rol in ent.roles.all()) or '-',
            'Sí' if ent.activo else 'No',
        ]
        for grupo in grupos
        for ent in grupo['entidades']
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': set(),
        'anchos': [1.3, 1.5, 0.7, 2.3, 1.7, 2.0, 0.8],
    }


def entidad_duplicados_excel(request):
    grupos = _grupos_entidades_duplicadas()
    resultado = _filas_reporte_duplicados(grupos)
    return excel_response('entidades_duplicadas', resultado)


def entidad_duplicados_pdf(request):
    grupos = _grupos_entidades_duplicadas()
    resultado = _filas_reporte_duplicados(grupos)
    return pdf_response('entidades_duplicadas', 'Entidades con CUIT/DNI duplicado', resultado)


# ---------------------------------------------------------------------------
# Alta / Modificación / Listado de Rol ("tipo de entidad")
# ---------------------------------------------------------------------------

def rol_alta(request):
    """Alta de un tipo de entidad nuevo (Transportista, Chofer de
    Transporte, Productor de H.V. de Té, etc. - ver también la carga
    inicial en la migración 0006_seed_tipos_entidad)."""
    if request.method == 'POST':
        form = RolForm(request.POST)
        if form.is_valid():
            rol = form.save(commit=False)
            rol.slug = slugify(rol.nombre)
            rol.save()
            messages.success(request, f'Tipo de entidad "{rol.nombre}" se creó correctamente.')
            return redirect('entidades:rol_listado')
    else:
        form = RolForm()

    return render(request, 'entidades/rol_form.html', {'form': form, 'modo': 'alta'})


def _roles_filtrados(request):
    """Aplica el filtro de búsqueda (q) usado tanto por el listado de tipos
    de entidad como por su exportación a Excel/PDF."""
    roles = Rol.objects.annotate(cantidad_entidades=Count('entidades')).order_by('nombre')

    q = request.GET.get('q', '').strip()
    if q:
        filtro = Q(nombre__icontains=q)
        if q.isdigit():
            filtro |= Q(id=int(q))
        roles = roles.filter(filtro)

    return roles, q


def rol_listado(request):
    """Listado/búsqueda de tipos de entidad; puerta de entrada de
    'Modificación'. Incluye exportación a Excel/PDF."""
    roles, q = _roles_filtrados(request)

    roles = aplicar_orden_queryset(request, roles, {
        'id': 'id',
        'nombre': 'nombre',
    })

    return render(request, 'entidades/rol_listado.html', {
        'roles': roles[:500],
        'q': q,
    })


def rol_editar(request, pk):
    rol = get_object_or_404(Rol, pk=pk)

    if request.method == 'POST':
        form = RolForm(request.POST, instance=rol)
        if form.is_valid():
            rol = form.save(commit=False)
            rol.slug = slugify(rol.nombre)
            rol.save()
            messages.success(request, f'Tipo de entidad "{rol.nombre}" se modificó correctamente.')
            return redirect('entidades:rol_listado')
    else:
        form = RolForm(instance=rol)

    return render(request, 'entidades/rol_form.html', {
        'form': form, 'modo': 'modificar', 'rol': rol,
    })


def _filas_reporte_rol(roles):
    columnas = ['ID', 'Nombre', 'Cantidad de entidades']
    filas = [
        [rol.id, rol.nombre or '-', rol.cantidad_entidades]
        for rol in roles
    ]
    return {
        'columnas': columnas,
        'filas': filas,
        'columnas_numericas': {2},
        'anchos': [0.8, 3.0, 2.0],
    }


def rol_listado_excel(request):
    roles, _q = _roles_filtrados(request)
    resultado = _filas_reporte_rol(roles)
    return excel_response('tipos_de_entidad', resultado)


def rol_listado_pdf(request):
    roles, _q = _roles_filtrados(request)
    resultado = _filas_reporte_rol(roles)
    return pdf_response('tipos_de_entidad', 'Tipos de entidad', resultado)
