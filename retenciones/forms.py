from django import forms

from comprobantes.models import ComprobanteTipo
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
    del formset comparten estos valores: proveedor, impuesto/régimen y
    número de comprobante)."""

    entidad = forms.ModelChoiceField(
        queryset=Entidad.objects.all(),
        required=False,
        widget=forms.HiddenInput(),
    )
    entidad_nombre = forms.CharField(
        required=False,
        label='Proveedor',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'id': 'entidad-buscador',
            'autocomplete': 'off',
            'placeholder': 'Buscar por nombre o CUIT...',
        }),
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
    año = forms.IntegerField(
        label='Año',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )
    numero = forms.IntegerField(
        label='Número de comprobante',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
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
        if id_impuesto and id_regimen and id_regimen.impuesto_id != id_impuesto.id:
            self.add_error('id_regimen', 'El régimen elegido no corresponde al impuesto seleccionado.')

        return cleaned


class RetencionRenglonForm(forms.Form):
    """Un renglón de 'Detalle de las operaciones': un comprobante (factura)
    sobre el que se practicó la retención."""

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
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm total-input', 'step': '0.01', 'readonly': 'readonly'}),
    )

    def clean(self):
        cleaned = super().clean()
        # Un renglón "vacío" (todos los campos en blanco) se ignora en vez de
        # exigir que se completen los campos requeridos: así el formset puede
        # tener de sobra filas vacías sin que tiren error de validación.
        valores = [cleaned.get(campo) for campo in (
            'tipo_comp_origen', 'punto_venta', 'numero_comprobante',
            'fecha_comp_origen', 'subtotal', 'porcentaje',
        )]
        if not any(v not in (None, '') for v in valores):
            cleaned['_vacio'] = True
            return cleaned
        cleaned['_vacio'] = False

        faltantes = []
        if cleaned.get('fecha_comp_origen') is None:
            faltantes.append('Fecha')
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

class ImpuestoIdNombreChoiceField(forms.ModelChoiceField):
    """A diferencia de ImpuestoChoiceField (que solo muestra el nombre,
    pensado para el buscador de la retención), acá el pedido puntual fue
    que al dar de alta/modificar un Régimen se vea el impuesto relacionado
    con su id y su nombre."""

    def label_from_instance(self, obj):
        return f'{obj.id} - {obj.nombre}'


class RetencionTipoImpuestoForm(forms.ModelForm):
    class Meta:
        model = RetencionTipoImpuesto
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }
        labels = {
            'nombre': 'Nombre del impuesto',
        }


class RetencionTipoRegimenForm(forms.ModelForm):
    impuesto = ImpuestoIdNombreChoiceField(
        queryset=RetencionTipoImpuesto.objects.all().order_by('nombre'),
        required=True,
        label='Impuesto relacionado',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    class Meta:
        model = RetencionTipoRegimen
        fields = ['impuesto', 'nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }
        labels = {
            'nombre': 'Nombre del régimen',
        }
