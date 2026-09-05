
from django.forms import ModelForm
from django.db.models import Case, When, Value, IntegerField
from .models import Entidad
from .models import Inym_Operador
from .models import Movimiento
from .models import MovimientoPesaje
from .models import MovimientoHvYerbaMate
from .models import ProductoDetalle
from django import forms


class  MovimientoPesajeForm(ModelForm):
    class Meta():
        model = MovimientoPesaje
        fields = ['movimiento','bruto','tara','descuento']

class MovimientoForm(ModelForm):
    """Alta / Modificación genérica de un Movimiento de producto."""

    class Meta():
        model = Movimiento
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'total': forms.NumberInput(attrs={'readonly': 'readonly'}),
            # Se reemplaza el <select> por un buscador con autocompletado
            # (ver movimiento_gestion_form.html); el campo queda oculto y lo
            # completa el JS del buscador (productos:buscar).
            'producto': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoDetalle.objects.all().order_by('nombre')
        self.fields['entidad_emisor'].queryset = Entidad.objects.all().order_by('nombre')
        self.fields['entidad_receptor'].queryset = Entidad.objects.all().order_by('nombre')
        # Orden de campos pedido: Fecha, número, Emisor, Receptor, Total, Ud. de medida, Producto.
        # (Bruto/tara/descuento se cargan aparte, con PesajeInlineForm, y se insertan
        # entre Receptor y Total en el template.)
        nuevo_orden = ['fecha', 'numero', 'entidad_emisor', 'entidad_receptor', 'total', 'unidad_de_medida', 'producto']
        self.order_fields(nuevo_orden)


class PesajeInlineForm(ModelForm):
    """Pesaje (bruto/tara/descuento) para cargar junto con el Alta/Modificación de un Movimiento de producto."""

    class Meta():
        model = MovimientoPesaje
        fields = ['bruto', 'tara', 'descuento']


class MovimientoInymOperadoresForm(forms.Form):
    """Operador INYM emisor/receptor, para cuando el movimiento de producto es de H.V. Yerba Mate."""
    inym_operador_origen = forms.ModelChoiceField(
        queryset=Inym_Operador.objects.select_related('entidad').order_by('entidad__nombre'),
        required=False,
        label='Operador INYM emisor',
    )
    inym_operador_destino = forms.ModelChoiceField(
        queryset=Inym_Operador.objects.select_related('entidad').order_by('entidad__nombre'),
        required=False,
        label='Operador INYM receptor',
    )


class SalidaForm(ModelForm):
    class Meta():
        model = Movimiento
        fields = ['fecha','producto','entidad_receptor','numero','total']
        widgets = {
            # Changes text input to a dedicated HTML5 date picker
            'fecha': forms.DateInput(attrs={'type': 'date', 'format': '%Y-%m-%d'}),
        }
class IngresoHvYerbaMateForm(ModelForm):
    bruto = forms.IntegerField(required=False)
    tara = forms.IntegerField(required=False)
    descuento = forms.IntegerField(required=False)

    class Meta():
        model = MovimientoHvYerbaMate
        fields = ['fecha', 'numero', 'inym_operador_origen','inym_operador_destino','total','unidad_de_medida','producto']
        widgets = {
            # Changes text input to a dedicated HTML5 date picker
            'fecha': forms.DateInput(attrs={'type': 'date', 'format': '%Y-%m-%d'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filters the dropdown choices to only display active authors
        # Se ordena para que, al buscar/seleccionar una entidad que tenga varios
        # operadores INYM (ej. productores y comercializadores), la opción de tipo
        # "productores" quede primera dentro de ese grupo. El buscador (buscar_en_input,
        # en buscador_generico.js) selecciona automáticamente la primera opción visible
        # que coincide con el texto buscado, por eso el orden acá define cuál queda
        # seleccionada por defecto.
        self.fields['inym_operador_origen'].queryset = Inym_Operador.objects.select_related(
            'entidad', 'tipo_operador'
        ).annotate(
            es_productor=Case(
                When(tipo_operador__nombre__iexact='PRODUCTORES', then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('entidad__nombre', 'es_productor', 'id')
        #cambio el label del emisor
        self.fields['inym_operador_origen'].label='Emisor'
        self.fields['inym_operador_destino'].queryset = Inym_Operador.objects.filter(id=181)
          # Estableces el valor inicial por su ID 
        self.fields['inym_operador_destino'].initial = 181
        self.fields['inym_operador_destino'].disabled = True
        self.fields['unidad_de_medida'].initial = '01'
        self.fields['unidad_de_medida'].disabled = True
        self.fields['producto'].initial = 2
        self.fields['producto'].disabled = True
        ultimo_creado=MovimientoHvYerbaMate.objects.latest('guardado_el')
        if ultimo_creado:
            if ultimo_creado.numero:
                self.fields["numero"].initial = ultimo_creado.numero + 1
            self.fields["fecha"].initial = ultimo_creado.fecha
        
        nuevo_orden = ['fecha', 'numero', 'inym_operador_origen','bruto','tara','descuento','total','inym_operador_destino','unidad_de_medida','producto']
        self.order_fields(nuevo_orden) #orden de los inputs

class SalidaYerbaMateCanchadaForm(ModelForm):
    bruto = forms.IntegerField(required=False)
    tara = forms.IntegerField(required=False)
    descuento = forms.IntegerField(required=False)

    class Meta():
        model = MovimientoHvYerbaMate
        fields = ['fecha', 'numero', 'inym_operador_origen','inym_operador_destino','total','unidad_de_medida','producto']
        widgets = {
            # Changes text input to a dedicated HTML5 date picker
            'fecha': forms.DateInput(attrs={'type': 'date', 'format': '%Y-%m-%d'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filters the dropdown choices to only display active authors
        self.fields['inym_operador_destino'].queryset = Inym_Operador.objects.all()
        #cambio el label del emisor
        self.fields['inym_operador_destino'].label='Receptor'
        self.fields['inym_operador_origen'].queryset = Inym_Operador.objects.filter(id=181)
          # Estableces el valor inicial por su ID 
        self.fields['inym_operador_origen'].initial = 181
        self.fields['inym_operador_origen'].disabled = True
        self.fields['unidad_de_medida'].initial = '01'
        self.fields['unidad_de_medida'].disabled = True
        self.fields['producto'].initial = 1037
        self.fields['producto'].disabled = True
        ultimo_creado=MovimientoHvYerbaMate.objects.latest('guardado_el')
        if ultimo_creado:
            if ultimo_creado.numero:
                self.fields["numero"].initial = ultimo_creado.numero + 1
            self.fields["fecha"].initial = ultimo_creado.fecha
        
        nuevo_orden = ['fecha', 'numero', 'inym_operador_destino','bruto','tara','descuento','total','inym_operador_origen','unidad_de_medida','producto']
        self.order_fields(nuevo_orden) #orden de los inputs

class MovimientoHvYerbaMateForm(ModelForm):
    bruto = forms.IntegerField(required=False)
    tara = forms.IntegerField(required=False)
    descuento = forms.IntegerField(required=False)

    class Meta():
        model = MovimientoHvYerbaMate
        fields = ['fecha', 'numero', 'inym_operador_origen','inym_operador_destino','total','unidad_de_medida','producto']
        widgets = {
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If an instance exists, populate the initial values for the related fields
        if self.instance and self.instance.pk:
            try:
                pesaje=MovimientoPesaje.objects.get(pk=self.instance.pk)
            except:
                pesaje=False
            if pesaje:
                if pesaje.bruto:
                    self.fields['bruto'].initial = pesaje.bruto
                if pesaje.tara:
                    self.fields['tara'].initial = pesaje.tara
                if pesaje.descuento:
                    self.fields['descuento'].initial = pesaje.descuento
        nuevo_orden = ['fecha', 'numero', 'inym_operador_origen','bruto','tara','descuento','total','inym_operador_destino','unidad_de_medida','producto']
        self.order_fields(nuevo_orden) #orden de los inputs
        


    
class BuscarMovimientoForm(forms.Form):
    id_movimiento = forms.IntegerField(required=False)
    numero = forms.IntegerField(required=False)
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date'}
        ))
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date'}
        ))
    buscador_emisor = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar emisor...',
            'autocomplete': 'off'
        })
        )
    emisor = forms.ModelChoiceField(
        required=False,
        queryset=Entidad.objects.all(), # Aquí defines el "otro modelo"
        label="Selecciona un emisor",
        empty_label="--- Elige una opción ---"
    )
    buscador_receptor = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar receptor...',
            'autocomplete': 'off'
        })
        )
    receptor =  forms.ModelChoiceField(
        required=False,
        queryset=Entidad.objects.all(), # Aquí defines el "otro modelo"
        label="Selecciona un receptor",
        empty_label="--- Elige una opción ---",
        )
    producto = forms.ModelChoiceField(
        queryset=ProductoDetalle.objects.all(), # Aquí defines el "otro modelo"
        label="Selecciona un producto",
        empty_label="--- Elige una opción ---",
        required=False,
        # Se reemplaza el <select> (y el viejo buscador_producto de filtrado
        # cliente) por un buscador con autocompletado por AJAX (ver
        # buscador_movimiento.html); el campo queda oculto y lo completa el
        # JS del buscador (productos:buscar).
        widget=forms.HiddenInput(),
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nuevo_orden = ['id_movimiento','numero','fecha_desde','fecha_hasta','buscador_emisor','emisor','buscador_receptor','receptor',
                       'producto']
        self.order_fields(nuevo_orden) #orden de los inputs


def crear_campo_fecha():
    return forms.DateField(
        required=False,
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date'}
        ))

def crear_campo_buscador_producto():
    return forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar producto...',
            'autocomplete': 'off'
        })
        )

def crear_campo_producto():
    return forms.ModelChoiceField(
        queryset=ProductoDetalle.objects.all(), # Aquí defines el "otro modelo"
        label="Selecciona un producto",
        empty_label="--- Elige una opción ---",
        required=False,
        # Se reemplaza el <select> por un buscador con autocompletado (ver
        # producto_buscar_saldo_form.html); el campo queda oculto y lo
        # completa el JS del buscador (productos:buscar).
        widget=forms.HiddenInput(),
    )

def crear_campo_emisor():
    return forms.ModelChoiceField(
        required=False,
        queryset=Entidad.objects.all(), # Aquí defines el "otro modelo"
        label="Selecciona un emisor",
        empty_label="--- Elige una opción ---"
    )

def crear_campo_buscador_emisor():
    return forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar emisor...',
            'autocomplete': 'off'
        })
        )

class BuscarSaldoProductoMovimientoComprobanteForm(forms.Form):
    fecha_desde = crear_campo_fecha()
    fecha_hasta = crear_campo_fecha()
    # producto ya no usa el viejo buscador_producto de filtrado en cliente:
    # crear_campo_producto() lo entrega oculto y lo completa el buscador con
    # autocompletado por AJAX (ver producto_buscar_saldo_form.html).
    producto = crear_campo_producto()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nuevo_orden = ['fecha_desde','fecha_hasta','producto',]
        self.order_fields(nuevo_orden) #orden de los inputs

class BuscarSaldoProductoEntidadForm(BuscarSaldoProductoMovimientoComprobanteForm):
    buscador_emisor = crear_campo_buscador_emisor()
    emisor = crear_campo_emisor()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nuevo_orden = ['fecha_desde','fecha_hasta','buscador_emisor','emisor','producto']
        self.order_fields(nuevo_orden) #orden de los inputs

"""
from .models import Entidad
from .models import Recepcion_HV_Yerba_Mate

class RecepcionForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cosechero'].queryset = Entidad.objects.filter(roles__nombre__icontains='cosechero té')
        self.fields['productor'].queryset = Entidad.objects.filter(roles__nombre__icontains='productor té')

    class Meta():
        fields='__all__'

    def get_search_results(self, request, queryset, search_term):
        print("request", request)
        print("query", queryset)
        print("search_term", search_term)
        queryset, may_have_duplicates = super().get_search_results(
            request,
            queryset,
            search_term,
        )

        author_id = request.GET.get("author_id")

        if author_id:
            queryset = queryset.filter(author=author_id)

        return queryset, False


class RecepcionHvYerbaMateForm(ModelForm):
    class Meta:
        model = Recepcion_HV_Yerba_Mate
        fields = '__all__'

"""


class MovimientoReporteForm(forms.Form):
    # Filtros para el listado 'Modificación' y para 'Reportes' de Movimientos de producto.
    producto = forms.ModelChoiceField(
        queryset=ProductoDetalle.objects.all().order_by('nombre'),
        required=False,
        # Se reemplaza el <select> por un buscador con autocompletado (ver
        # movimiento_gestion_reporte.html): con muchos productos cargados,
        # elegir de una lista desplegable es incómodo. El campo queda oculto
        # y lo completa el JS del buscador (productos:buscar).
        widget=forms.HiddenInput(),
    )
    entidad_emisor = forms.ModelChoiceField(
        queryset=Entidad.objects.all().order_by('nombre'),
        required=False,
        label='Entidad emisora',
        # Reemplazado por un buscador con autocompletado (ver
        # movimiento_gestion_reporte.html); este campo queda oculto y lo
        # completa el JS del buscador.
        widget=forms.HiddenInput(),
    )
    entidad_receptor = forms.ModelChoiceField(
        queryset=Entidad.objects.all().order_by('nombre'),
        required=False,
        label='Entidad receptora',
        widget=forms.HiddenInput(),
    )
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )


class RankingProductoresForm(forms.Form):
    """Filtros (fecha de emisión y, opcionalmente, producto) para el ranking
    de productores (entidad emisora) por total entregado."""
    fecha_desde = forms.DateField(
        required=False,
        label='Emisión desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label='Emisión hasta',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    producto = forms.ModelChoiceField(
        queryset=ProductoDetalle.objects.all().order_by('nombre'),
        required=False,
        # Se reemplaza el <select> por un buscador con autocompletado (ver
        # movimiento_ranking_productores.html): con muchos productos
        # cargados, elegir de una lista desplegable es incómodo. El campo
        # queda oculto y lo completa el JS del buscador (productos:buscar,
        # que ya busca por ID o por nombre).
        widget=forms.HiddenInput(),
    )

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get('fecha_desde')
        hasta = cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', '"Emisión hasta" no puede ser anterior a "Emisión desde".')
        return cleaned_data


class ReporteHvYerbaMateForm(forms.Form):
    # Filtros para el Reporte de Ingreso H.V. de Yerba Mate.
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    # Búsqueda libre de la entidad emisora: acepta ID de entidad, nombre
    # (parcial) o ID de Inym Operador. Solo se consideran entidades que
    # tengan al menos un Inym Operador asociado (ver vista).
    entidad_emisor = forms.CharField(
        required=False,
        label='Entidad emisora (ID, nombre o ID Inym Operador)',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'ID, nombre o ID Inym Operador',
        }),
    )