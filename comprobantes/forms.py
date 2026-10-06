from django import forms
from django.db.models import Q
from productos.models import ProductoDetalle
from productos.forms import ProductoDetalleForm as _ProductoDetalleFormBase
from entidades.models import Entidad
from services.forms import BuscarConFechasForm
from entidades.forms import BuscarEntidadEmisorForm
from copy import deepcopy
from .models import (
    Comprobante, ComprobanteRenglon, ComprobanteRenglonDetalle, ComprobanteUnidadDeMedida,
    IDS_UNIDADES_SOLO_REMITOS,
)

class BuscarComprobanteEntreFechasPorEntidadForm(forms.Form):
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
                   
            # 1. Copiamos de forma segura los campos de los otros formularios
            self.fields.update(deepcopy(BuscarConFechasForm.base_fields))
            self.fields.update(deepcopy(BuscarEntidadEmisorForm.base_fields))
            
            # 2. Definimos el orden exacto que necesitas
            nuevo_orden = ['fecha_desde', 'fecha_hasta', 'buscador_emisor', 'emisor']
            self.order_fields(nuevo_orden)
class BuscarRenglonComprobanteForm(forms.Form):
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
    buscador_producto = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar producto...',
            'autocomplete': 'off'
        })
        )
    producto = forms.ModelChoiceField(
        queryset=ProductoDetalle.objects.all(), # Aquí defines el "otro modelo"
        label="Selecciona un producto",
        empty_label="--- Elige una opción ---",
        required=False

    )


# ---------------------------------------------------------------------------
# Alta / Modificar / Reportes de Comprobante
# ---------------------------------------------------------------------------

class ComprobanteForm(forms.ModelForm):
    class Meta:
        model = Comprobante
        fields = [
            'entidad_emisor',
            'tipo_comprobante',
            'tipo_documento_entidad',
            'fecha',
            'punto_de_venta',
            'numero',
            'moneda',
            'neto_gravado',
            'neto_no_gravado',
            'recargo',
            'impuesto',
            'iva',
            'exento',
            'otros_tributos',
            'total',
            'detalle',
            'es_emisor',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            # Se reemplaza el <select> por un buscador con autocompletado
            # (ver comprobante_form.html); este input queda oculto y lo
            # completa el JS del buscador.
            'entidad_emisor': forms.HiddenInput(),
        }

    # 06/10/2026: el campo 'entidad_emisor' es en realidad LA entidad del
    # comprobante (proveedor o cliente), sea quien sea el que lo emitió; quién
    # lo emitió lo dice 'es_emisor'. Con las etiquetas viejas ("Entidad
    # emisora" + "Es emisor: Sí/No") era fácil ver "Entidad emisora: X" y no
    # notar que "Es emisor" estaba en No (= lo emitió Fontana, y entonces el
    # comprobante se ofrece para COBRO y no para PAGO). Sólo cambian las
    # etiquetas: los valores guardados siguen siendo 1 / 0.
    ES_EMISOR_CHOICES = [
        (1, 'La entidad -- Fontana lo RECIBE (compra / gasto, se liquida en PAGO)'),
        (0, 'Fontana -- se lo EMITIMOS a la entidad (venta, se liquida en COBRO)'),
    ]

    # 06/10/2026: control de duplicados al cargar/editar a mano (ver clean).
    confirmar_posible_duplicado = forms.BooleanField(
        required=False,
        label='Confirmo que NO es un duplicado (es otro comprobante distinto con el mismo número)',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields['es_emisor']
        campo.label = '¿Quién emitió el comprobante?'
        campo.choices = self.ES_EMISOR_CHOICES
        self.mostrar_confirmar_duplicado = False

    def clean(self):
        """Control de duplicados (06/10/2026, a raíz de los de Electricidad
        de Misiones):
          - mismo comprobante exacto (entidad + tipo + punto de venta +
            número) -> no se puede guardar;
          - misma entidad + número con OTRO tipo, o con el punto de venta
            vacío en alguno de los dos -> se avisa y hay que tildar
            "Confirmo que NO es un duplicado" para guardar igual.
        Al editar, sólo se controla si se cambió alguno de esos datos (para
        no trabar la edición de comprobantes viejos)."""
        cleaned_data = super().clean()
        entidad = cleaned_data.get('entidad_emisor')
        numero = cleaned_data.get('numero')
        pv = cleaned_data.get('punto_de_venta')
        tipo = cleaned_data.get('tipo_comprobante')
        claves = {'entidad_emisor', 'numero', 'punto_de_venta', 'tipo_comprobante'}
        if self.instance.pk and not (claves & set(self.changed_data)):
            return cleaned_data
        if not entidad or not numero:
            return cleaned_data
        qs = Comprobante.objects.filter(entidad_emisor=entidad, numero=numero)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if pv:
            qs = qs.filter(Q(punto_de_venta=pv) | Q(punto_de_venta__isnull=True) | Q(punto_de_venta=0))
        existentes = list(qs.select_related('tipo_comprobante')[:10])
        if not existentes:
            return cleaned_data
        exactos = [c for c in existentes
                   if tipo and c.tipo_comprobante_id == tipo.id and pv and c.punto_de_venta == pv]
        if exactos:
            raise forms.ValidationError(
                f'Ese comprobante ya está cargado (comprobante {exactos[0].id}: misma entidad, tipo, '
                f'punto de venta y número).'
            )
        if not cleaned_data.get('confirmar_posible_duplicado'):
            self.mostrar_confirmar_duplicado = True
            detalle = ', '.join(
                f'{c.id} ({c.tipo_comprobante or "sin tipo"}, pv {c.punto_de_venta or "vacío"}, {c.fecha})'
                for c in existentes
            )
            raise forms.ValidationError(
                f'Posible duplicado: esta entidad ya tiene cargado el número {numero} en: {detalle}. '
                'Si es otro comprobante distinto, tildá "Confirmo que NO es un duplicado" y guardá de nuevo.'
            )
        return cleaned_data


class ComprobanteReporteForm(forms.Form):
    entidad = forms.ModelChoiceField(
        queryset=Entidad.objects.all().order_by('nombre'),
        required=False,
        label='Entidad emisora',
        # Reemplazado por un buscador con autocompletado (ver
        # comprobante_reporte.html); este campo queda oculto y lo completa
        # el JS del buscador.
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
    # Agregado 2026-09-09: para encontrar rápido los comprobantes cargados
    # sin ningún ComprobanteRenglon (por ejemplo, comprobantes importados o
    # cargados a mano a los que todavía no se les detalló el contenido) y
    # poder ir directo a agregarles uno desde "Modificar".
    sin_renglones = forms.BooleanField(
        required=False,
        label='Solo sin renglones cargados',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    # Agregado 2026-10-01: los comprobantes marcados "NO RECIBIDO"
    # (ComprobanteNoRecibido) quedan afuera salvo que se tilde esto.
    incluir_no_recibidos = forms.BooleanField(
        required=False,
        label='Incluir no recibidos',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


# ---------------------------------------------------------------------------
# Alta / Modificar / Reportes de ComprobanteRenglon
# ---------------------------------------------------------------------------

# Categorías de producto (item_tipo.nombre, normalizado en minúsculas y sin
# espacios extra) para las que el renglón habilita los campos de
# comprobante_renglon_detalle. Antes esto era sólo {'producto o servicio'},
# asumiendo una única categoría con ese nombre exacto; si en item_tipo la
# categoría está separada en 'Producto' y 'Servicio' (u otra variante de
# escritura), ese nombre nunca matcheaba y el detalle no se mostraba nunca.
# Se incluyen todas las variantes razonables; correr el comando de gestión
# 'inspeccionar_categoria_producto' muestra los nombres reales guardados en
# item_tipo por si hace falta agregar alguno más.
CATEGORIAS_CON_DETALLE = {
    'producto o servicio',
    'producto/servicio',
    'producto',
    'servicio',
}

# Categoría (item_tipo.nombre, en minúsculas) de los producto_detalle que
# pueden elegirse como "tipo de iva" en el detalle de un renglón.
CATEGORIA_IVA = 'iva'

# Categoría (item_tipo.nombre, en minúsculas) de los renglones que
# representan otros tributos (percepciones, Ingresos Brutos, etc.), para
# puntear neto_gravado/iva/otros_tributos de la cabecera del comprobante
# contra la suma de sus renglones. Si en item_tipo el nombre real es otra
# variante, agregarla acá (correr el comando 'inspeccionar_categoria_producto'
# para ver los nombres reales guardados).
CATEGORIAS_OTRO_TRIBUTO = {
    'otro tributo',
    'otros tributos',
}


class ComprobanteRenglonForm(forms.ModelForm):
    class Meta:
        model = ComprobanteRenglon
        fields = ['comprobante', 'producto', 'total', 'id_cuenta_contable', 'id_asiento_contable']
        widgets = {
            # Se reemplazan los <select> por buscadores con autocompletado
            # (ver comprobante_renglon_form.html); estos inputs quedan
            # ocultos y los completa el JS de los buscadores.
            'comprobante': forms.HiddenInput(),
            'producto': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['comprobante'].queryset = Comprobante.objects.order_by('-fecha', '-id')
        self.fields['producto'].queryset = ProductoDetalle.objects.order_by('nombre')


class ProductoDetalleCrearForm(_ProductoDetalleFormBase):
    """Alta rápida de un producto/ítem nuevo, embebida en el buscador de
    producto del alta/modificación de ComprobanteRenglon (cuando el
    producto buscado todavía no existe). Reusa el formulario canónico
    productos.forms.ProductoDetalleForm (el mismo que usa Tipos > Productos
    > Alta), agregándole sólo la particularidad de vivir oculto.

    Este mini-formulario vive oculto (display:none) dentro del <form>
    principal de alta de renglón. "use_required_attribute" es un
    atributo de CLASE de Django (no un método) que, en False, evita que
    se renderice el atributo HTML "required" en sus campos — si se
    renderizara, el navegador bloquearía en silencio el envío del
    formulario grande (no puede enfocar un campo oculto para pedir que
    se complete). La obligatoriedad la sigue exigiendo el servidor vía
    is_valid(), que no depende de este atributo.
    """
    use_required_attribute = False


class ComprobanteRenglonDetalleForm(forms.ModelForm):
    """Detalle opcional de un renglón (cantidad, precio, etc.), habilitado
    sólo cuando el producto elegido es de categoría Producto o Servicio."""

    class Meta:
        model = ComprobanteRenglonDetalle
        fields = ['cantidad', 'unidad_de_medida', 'precio_unitario', 'bonificacion', 'iva_tipo', 'sector_tipo']
        widgets = {
            # Se calcula automáticamente (total del renglón / cantidad) por
            # JS y, para garantizarlo, se recalcula también en el servidor
            # al guardar; queda de solo lectura para que no se edite a mano.
            'precio_unitario': forms.NumberInput(attrs={'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El "tipo de iva" sólo puede ser un producto_detalle cuya categoría
        # (item_tipo) sea Iva.
        self.fields['iva_tipo'].queryset = ProductoDetalle.objects.filter(
            item_tipo__nombre__iexact=CATEGORIA_IVA
        ).order_by('nombre')
        # Unidades que no vienen del padrón de AFIP (ver
        # comprobantes.models.IDS_UNIDADES_SOLO_REMITOS): se excluyen acá
        # para que nunca se puedan elegir en un comprobante fiscal real,
        # aunque sí queden disponibles para Remitos. Igual que en
        # RemitoForm._queryset_activos, si el renglón ya tenía guardada una
        # de estas (no debería pasar, pero por las dudas) se la sigue
        # mostrando para no "perderla" al editar.
        queryset_unidades = ComprobanteUnidadDeMedida.objects.exclude(id__in=IDS_UNIDADES_SOLO_REMITOS)
        unidad_actual_id = getattr(self.instance, 'unidad_de_medida_id', None)
        if unidad_actual_id in IDS_UNIDADES_SOLO_REMITOS:
            queryset_unidades = ComprobanteUnidadDeMedida.objects.filter(
                Q(pk__in=queryset_unidades.values('pk')) | Q(pk=unidad_actual_id)
            )
        self.fields['unidad_de_medida'].queryset = queryset_unidades.order_by('nombre')
        # La obligatoriedad real se controla en la vista según la categoría
        # del producto elegido (no siempre corresponde completar el detalle).
        for nombre_campo in self.fields:
            self.fields[nombre_campo].required = False
        # Unidad de medida por defecto "Unidad", sólo para un detalle nuevo
        # (no pisa el valor ya guardado al editar uno existente).
        if self.instance.pk is None:
            unidad_por_defecto = ComprobanteUnidadDeMedida.objects.filter(nombre__iexact='unidad').first()
            if unidad_por_defecto:
                self.fields['unidad_de_medida'].initial = unidad_por_defecto.pk


class RankingEntidadesForm(forms.Form):
    """Filtros para el ranking de entidades por monto total de comprobantes:
    rol de la entidad (emisora o receptora, respecto de Fontana, según el
    campo 'es_emisor' de Comprobante) y, opcionalmente, un lapso de fecha de
    emisión y excluir a Fontana como entidad."""
    ROL_EMISORA = 'emisora'
    ROL_RECEPTORA = 'receptora'
    ROL_CHOICES = [
        (ROL_EMISORA, 'Entidades emisoras (de las que recibimos comprobantes)'),
        (ROL_RECEPTORA, 'Entidades receptoras (a las que les emitimos comprobantes)'),
    ]

    rol = forms.ChoiceField(
        choices=ROL_CHOICES,
        required=False,
        initial=ROL_EMISORA,
        label='Rol de la entidad',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
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
    excluir_fontana = forms.BooleanField(
        required=False,
        label='Excluir Fontana (entidad propia)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    # Agregado 2026-10-01: los comprobantes marcados "NO RECIBIDO"
    # (ComprobanteNoRecibido) quedan afuera salvo que se tilde esto.
    incluir_no_recibidos = forms.BooleanField(
        required=False,
        label='Incluir no recibidos',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get('fecha_desde')
        hasta = cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', '"Emisión hasta" no puede ser anterior a "Emisión desde".')
        return cleaned_data


class ComprobanteRenglonReporteForm(forms.Form):
    producto = forms.ModelChoiceField(
        queryset=ProductoDetalle.objects.all().order_by('nombre'),
        required=False,
        # Se reemplaza el <select> por un buscador con autocompletado (ver
        # comprobante_renglon_reporte.html); el campo queda oculto y lo
        # completa el JS del buscador (productos:buscar).
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
    # Agregado 2026-10-01: los comprobantes marcados "NO RECIBIDO"
    # (ComprobanteNoRecibido) quedan afuera salvo que se tilde esto.
    incluir_no_recibidos = forms.BooleanField(
        required=False,
        label='Incluir no recibidos',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class ImportarAfipForm(forms.Form):
    """Subida del archivo "Mis Comprobantes" de AFIP/ARCA (06/10/2026)."""
    SENTIDO_CHOICES = [
        ('auto', 'Detectar solo (según las columnas del archivo)'),
        ('recibidos', 'Comprobantes RECIBIDOS (compras / gastos: se liquidan en PAGO)'),
        ('emitidos', 'Comprobantes EMITIDOS por Fontana (ventas: se liquidan en COBRO)'),
    ]
    archivo = forms.FileField(
        label='Archivo de AFIP (CSV o Excel)',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm', 'accept': '.csv,.txt,.xlsx,.xls'}),
    )
    sentido = forms.ChoiceField(
        label='Tipo de archivo', choices=SENTIDO_CHOICES, initial='auto',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    fecha_desde = forms.DateField(
        required=False, label='Fecha desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    fecha_hasta = forms.DateField(
        required=False, label='Fecha hasta',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    crear_entidades = forms.BooleanField(
        required=False, initial=True,
        label='Crear las entidades que no existen (con el nombre y CUIT del archivo)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        desde, hasta = cleaned_data.get('fecha_desde'), cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', '"Fecha hasta" no puede ser anterior a "Fecha desde".')
        return cleaned_data
