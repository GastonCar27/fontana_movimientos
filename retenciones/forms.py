from django import forms

from comprobantes.models import Comprobante, ComprobanteTipo
from entidades.models import Entidad
from .models import RetencionTipoImpuesto, RetencionTipoRegimen


class RankingEntidadesForm(forms.Form):
    """Filtro (fecha de la retención y, opcionalmente, excluir a Fontana)
    para el ranking de entidades por monto total de retenciones. Mismo
    patrón que comprobantes.forms.RankingEntidadesForm /
    movimientos_caja.forms.RankingEntidadesForm."""
    fecha_desde = forms.DateField(
        required=False,
        label='Fecha desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label='Fecha hasta',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    excluir_fontana = forms.BooleanField(
        required=False,
        label='Excluir Fontana (entidad propia)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get('fecha_desde')
        hasta = cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', '"Fecha hasta" no puede ser anterior a "Fecha desde".')
        return cleaned_data


class ImpuestoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nombre or f'Impuesto {obj.id}'


class RegimenChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nombre or f'Régimen {obj.id}'


class RetencionHeaderForm(forms.Form):
    """Datos comunes a todo el comprobante de retención (todos los renglones
    del formset comparten estos valores: entidad, dirección, impuesto/
    régimen y número de comprobante)."""

    entidad = forms.ModelChoiceField(
        queryset=Entidad.objects.all(),
        required=False,
        widget=forms.HiddenInput(),
    )
    entidad_nombre = forms.CharField(
        required=False,
        label='Entidad',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'id': 'entidad-buscador',
            'autocomplete': 'off',
            'placeholder': 'Buscar por nombre o CUIT...',
        }),
    )
    # Dirección de la retención: 1/Sí (default) = Fontana se la practicó a
    # la entidad al pagarle (comportamiento histórico, "Proveedor" en el
    # PDF/Excel); 0/No = la entidad se la practicó a Fontana al pagarle a
    # Fontana (retención sufrida, "Cliente" en el PDF/Excel). Ver
    # Retencion.es_emisor en models.py.
    es_emisor = forms.TypedChoiceField(
        choices=(
            (1, 'Practicada por Fontana (se la retuvimos a la entidad)'),
            (0, 'Sufrida (la entidad nos la retuvo a nosotros)'),
        ),
        coerce=int,
        required=True,
        initial=1,
        label='Dirección',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm', 'id': 'id_es_emisor'}),
    )
    id_impuesto = ImpuestoChoiceField(
        queryset=RetencionTipoImpuesto.objects.all().order_by('nombre'),
        required=True,
        label='Impuesto',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm', 'id': 'id_id_impuesto'}),
    )
    id_regimen = RegimenChoiceField(
        queryset=RetencionTipoRegimen.objects.select_related('impuesto').order_by('nombre'),
        required=True,
        label='Régimen',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm', 'id': 'id_id_regimen'}),
    )
    # Fecha de la retención en sí (no la del comprobante origen -- esa es
    # fecha_comp_origen, un campo propio de cada renglón de "Detalle de las
    # operaciones"). Antes de esto no existía ningún campo para cargarla a
    # mano: se guardaba una copia de la fecha del renglón sin que el usuario
    # pudiera elegirla ni verla en el encabezado (pedido de Gastón,
    # 23/09/2026).
    fecha = forms.DateField(
        required=True,
        label='Fecha',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    año = forms.IntegerField(
        label='Año',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )
    numero = forms.IntegerField(
        label='Número de comprobante',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )
    # Total de LA RETENCIÓN completa (un solo comprobante/certificado),
    # cargado a mano -- pedido de Gastón, 24/09/2026: "cuando cargo una
    # retención con dos renglones me debería guardar solo una retención con
    # el total, y el vínculo nomás debería ser con dos renglones distintos".
    # Mismo criterio que ya usaba la pantalla de "vincular renglones"
    # (retencion_vincular_renglones.html): el total es el dato maestro del
    # encabezado, y la suma de los renglones nunca puede superarlo (ver
    # _chequear_suma_renglones en views.py) aunque sí puede quedar por
    # debajo (por si falta vincular algún comprobante más).
    total = forms.DecimalField(
        required=True,
        label='Total de la retención',
        max_digits=20,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', 'step': '0.01', 'id': 'id_total_header',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        entidad = cleaned.get('entidad')
        entidad_nombre = (cleaned.get('entidad_nombre') or '').strip()
        if not entidad and not entidad_nombre:
            raise forms.ValidationError('Elegí un proveedor de la lista o escribí su nombre.')
        cleaned['entidad_nombre'] = entidad_nombre

        id_impuesto = cleaned.get('id_impuesto')
        id_regimen = cleaned.get('id_regimen')
        if id_impuesto and id_regimen:
            vinculados = set(id_regimen.impuestos.values_list('id', flat=True))
            if not vinculados and id_regimen.impuesto_id is not None:
                # Régimen viejo, todavía no migrado a la relación M2M nueva
                # (nadie lo volvió a guardar desde la pantalla de Ret.
                # Regímenes con los checkboxes): se usa el vínculo legacy de
                # un solo impuesto como resguardo.
                vinculados = {id_regimen.impuesto_id}
            if vinculados and id_impuesto.id not in vinculados:
                self.add_error('id_regimen', 'El régimen elegido no corresponde al impuesto seleccionado.')

        return cleaned


class RetencionRenglonForm(forms.Form):
    """Un renglón de 'Detalle de las operaciones': un Comprobante REAL
    (factura ya cargada en el sistema) sobre el que se practicó la
    retención -- se guarda como un RetencionRenglon vinculado a esa
    Retencion (encabezado), nunca como una Retencion aparte (rediseño de
    24/09/2026, ver _guardar_grupo en views.py).

    `comprobante` (oculto) es el vínculo real, elegido con el buscador de
    `comprobante_texto` -- mismo patrón que `entidad`/`entidad_nombre` en
    RetencionHeaderForm. tipo_comp_origen/punto_venta/numero_comprobante/
    fecha_comp_origen se siguen mostrando (se autocompletan solos al elegir
    la factura, de sólo lectura) para que se vea de un vistazo a qué
    comprobante corresponde cada renglón, pero ya no se guardan sueltos --
    esos datos se leen del Comprobante vinculado."""

    comprobante_texto = forms.CharField(
        required=False,
        label='Factura',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm comprobante-buscador',
            'autocomplete': 'off',
            'placeholder': 'Buscar factura ya cargada...',
        }),
    )
    comprobante = forms.ModelChoiceField(
        queryset=Comprobante.objects.all(),
        required=False,
        widget=forms.HiddenInput(),
    )
    tipo_comp_origen = forms.ModelChoiceField(
        queryset=ComprobanteTipo.objects.all().order_by('nombre'),
        required=False,
        label='Tipo de factura',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    punto_venta = forms.IntegerField(
        required=False,
        label='Punto de venta',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0}),
    )
    numero_comprobante = forms.IntegerField(
        required=False,
        label='Número',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 0}),
    )
    fecha_comp_origen = forms.DateField(
        required=False,
        label='Fecha',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    subtotal = forms.DecimalField(
        required=False,
        label='Importe',
        max_digits=20,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm importe-input', 'step': '0.01'}),
    )
    porcentaje = forms.FloatField(
        required=False,
        label='Porcentaje',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm porcentaje-input', 'step': '0.01'}),
    )
    total = forms.DecimalField(
        required=False,
        label='Retención',
        max_digits=20,
        decimal_places=2,
        # Se autocompleta con Importe x Porcentaje / 100 (ver JS de
        # retencion_form.html), pero queda editable a mano: puede haber una
        # diferencia de centavos entre lo calculado y lo que realmente
        # retuvo la otra parte (por su propio redondeo), y en ese caso se
        # carga el monto real -- el JS avisa antes de guardar si hay una
        # diferencia, pero no lo bloquea.
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm total-input', 'step': '0.01'}),
    )

    def clean(self):
        cleaned = super().clean()
        # Un renglón "vacío" (todos los campos en blanco) se ignora en vez de
        # exigir que se completen los campos requeridos: así el formset puede
        # tener de sobra filas vacías sin que tiren error de validación.
        valores = [cleaned.get(campo) for campo in (
            'comprobante', 'comprobante_texto', 'tipo_comp_origen', 'punto_venta',
            'numero_comprobante', 'fecha_comp_origen', 'subtotal', 'porcentaje',
        )]
        if not any(v not in (None, '') for v in valores):
            cleaned['_vacio'] = True
            return cleaned
        cleaned['_vacio'] = False

        faltantes = []
        if cleaned.get('comprobante') is None:
            faltantes.append('Factura (elegila de la lista de "Buscar factura")')
        if cleaned.get('subtotal') is None:
            faltantes.append('Importe')
        if cleaned.get('porcentaje') is None:
            faltantes.append('Porcentaje')
        if faltantes:
            raise forms.ValidationError(
                f"Completá estos campos del renglón: {', '.join(faltantes)}."
            )
        return cleaned


RetencionRenglonFormSet = forms.formset_factory(
    RetencionRenglonForm, extra=1, can_delete=True,
)


# ---------------------------------------------------------------------------
# Alta / Modificación de los catálogos "Ret. Impuestos" y "Ret. Regimenes"
# ---------------------------------------------------------------------------

class ImpuestosMultipleChoiceField(forms.ModelMultipleChoiceField):
    """A diferencia de ImpuestoChoiceField (que solo muestra el nombre,
    pensado para el buscador de la retención), acá el pedido puntual fue
    que al dar de alta/modificar un Régimen se vean los impuestos
    relacionados con su id y su nombre."""

    def label_from_instance(self, obj):
        return f'{obj.id} - {obj.nombre}'


class RetencionTipoImpuestoForm(forms.ModelForm):
    # El id NO está en Meta.fields a propósito: al ser la clave primaria, si
    # Django lo tratara como un campo de modelo común, form.save() podría
    # intentar reasignarle el pk a una instancia ya guardada (editar el ID
    # de un impuesto existente rompería los vínculos con Ret. Regímenes y
    # con las retenciones que ya lo usan). Se maneja a mano: sólo se ofrece
    # al dar de ALTA (se saca del form en __init__ si ya hay instancia), y
    # la vista es la que lo asigna a la instancia nueva.
    id = forms.IntegerField(
        required=False,
        min_value=1,
        label='ID',
        help_text='Opcional: si este impuesto ya tiene un código propio en AFIP (u otro sistema) y querés guardarlo con ese mismo número, cargalo acá. Si se deja vacío, se asigna automáticamente el próximo disponible.',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )

    class Meta:
        model = RetencionTipoImpuesto
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }
        labels = {
            'nombre': 'Nombre del impuesto',
        }

    field_order = ['nombre', 'id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Ya existe: el ID no se puede tocar al editar.
            del self.fields['id']

    def clean_id(self):
        id_elegido = self.cleaned_data.get('id')
        if id_elegido and RetencionTipoImpuesto.objects.filter(pk=id_elegido).exists():
            raise forms.ValidationError('Ya existe un impuesto con ese ID.')
        return id_elegido


class RetencionTipoRegimenForm(forms.ModelForm):
    # M2M a través de RetencionRegimenImpuesto: un mismo régimen puede
    # aplicar a varios impuestos a la vez (ver comentario en models.py).
    # No se puede declarar en Meta.fields porque un ManyToManyField con
    # through= no lo guarda form.save()/save_m2m() solo -- hay que llamar
    # guardar_impuestos() a mano desde la vista, una vez que el régimen ya
    # tiene un id guardado.
    impuestos = ImpuestosMultipleChoiceField(
        queryset=RetencionTipoImpuesto.objects.all().order_by('nombre'),
        required=True,
        label='Impuestos relacionados',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )
    # El id NO está en Meta.fields a propósito (mismo motivo que en
    # RetencionTipoImpuestoForm): es la clave primaria, así que sólo se
    # ofrece al dar de ALTA (se saca del form en __init__ si ya hay
    # instancia) y la vista es la que lo asigna a mano.
    id = forms.IntegerField(
        required=False,
        min_value=1,
        label='ID',
        help_text='Opcional: si este régimen ya tiene un código propio en AFIP (u otro sistema) y querés guardarlo con ese mismo número, cargalo acá. Si se deja vacío, se asigna automáticamente el próximo disponible.',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )

    class Meta:
        model = RetencionTipoRegimen
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }
        labels = {
            'nombre': 'Nombre del régimen',
        }

    field_order = ['nombre', 'id', 'impuestos']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Ya existe: el ID no se puede tocar al editar.
            del self.fields['id']
            vinculados = list(self.instance.impuestos.values_list('id', flat=True))
            if not vinculados and self.instance.impuesto_id is not None:
                # Régimen viejo, todavía no migrado a la relación M2M
                # nueva: se precarga tildado el impuesto que tenía en el
                # campo legacy, para no perder ese dato al editar.
                vinculados = [self.instance.impuesto_id]
            self.fields['impuestos'].initial = vinculados

    def clean_id(self):
        id_elegido = self.cleaned_data.get('id')
        if id_elegido and RetencionTipoRegimen.objects.filter(pk=id_elegido).exists():
            raise forms.ValidationError('Ya existe un régimen con ese ID.')
        return id_elegido

    def guardar_impuestos(self, regimen):
        """Guarda el M2M. Hay que llamarlo a mano desde la vista, después
        de que `regimen` ya tenga un pk guardado en la base (ver
        retencion_tipo_regimen_alta/modificar en views.py)."""
        regimen.impuestos.set(self.cleaned_data['impuestos'])
