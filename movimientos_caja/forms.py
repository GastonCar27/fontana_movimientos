
from django import forms
from django.core.exceptions import ValidationError
from entidades.models import Entidad
from .models import (
    BancoCuentaEntidad,
    Caja,
    BancoCuentaTipoMovim,
    LibroCaja,
    LibroMovim,
    MovimientoCaja,
    MovimientoCajaConceptoTipo,
)


class MovimientoCajaForm(forms.ModelForm):
    """
    Formulario principal para crear o editar un Movimiento de Caja (Alta / Modificación).

    Nota: 'asiento_libro' no es un campo real de MovimientoCaja (es el related_name
    inverso de LibroMovim), así que no puede ir en un ModelForm de MovimientoCaja.
    Los datos de las tablas relacionadas (libro/hoja/renglón, diferido,
    concepto y cuenta bancaria del receptor) se completan, en la misma
    pantalla, con MovimientoCajaRelacionadosForm.
    """
    class Meta:
        model = MovimientoCaja
        fields = ['caja', 'tipo', 'emision', 'monto', 'receptor', 'efectivizacion']
        widgets = {
            'emision': forms.DateInput(attrs={'type': 'date'}),
            'efectivizacion': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['caja'].queryset = Caja.objects.all().order_by('nombre')
        self.fields['tipo'].queryset = BancoCuentaTipoMovim.objects.all().order_by('nombre')
        self.fields['receptor'].queryset = Entidad.objects.all().order_by('nombre')
        self.fields['receptor'].required = False
        # Estilo bootstrap parejo para todos los campos de este form (el
        # template ya lo usa para el resto de la pantalla de Alta/Modificación).
        for campo in self.fields.values():
            extra = 'form-select form-select-sm' if isinstance(campo.widget, forms.Select) else 'form-control form-control-sm'
            actuales = campo.widget.attrs.get('class', '')
            campo.widget.attrs['class'] = f'{actuales} {extra}'.strip()


class MovimientoCajaRelacionadosForm(forms.Form):
    """Datos de las tablas relacionadas con un Movimiento de Caja (libro,
    hoja, renglón, fecha de diferido, concepto y cuenta bancaria del
    receptor), para completarlos en la misma pantalla de Alta/Modificación
    sin tener que pasar por el admin. Todos los campos son opcionales: si se
    dejan vacíos, no se guarda (o se borra, si ya existía) el registro
    relacionado correspondiente.

    El campo 'libro' se muestra en el template con un <select> armado a mano
    (necesita un atributo data-caja por <option> para que el JS lo filtre
    según la cuenta de banco elegida y proponga por defecto el de mayor id),
    así que acá sólo se usa para validar el valor recibido.
    """
    libro = forms.ModelChoiceField(
        queryset=LibroCaja.objects.all(),
        required=False,
        label='Libro de caja',
    )
    hoja = forms.IntegerField(
        required=False, label='Hoja',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )
    renglon = forms.IntegerField(
        required=False, label='Renglón',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )
    diferido = forms.DateField(
        required=False, label='Fecha de diferido',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    concepto_tipo = forms.ModelChoiceField(
        queryset=MovimientoCajaConceptoTipo.objects.all().order_by('nombre'),
        required=False, label='Concepto',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    cuenta_bancaria_entidad = forms.ModelChoiceField(
        queryset=BancoCuentaEntidad.objects.none(),
        required=False, label='Cuenta bancaria del receptor',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    def __init__(self, *args, receptor_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if receptor_id:
            self.fields['cuenta_bancaria_entidad'].queryset = BancoCuentaEntidad.objects.filter(entidad_id=receptor_id)

    def clean(self):
        cleaned_data = super().clean()
        libro = cleaned_data.get('libro')
        hoja = cleaned_data.get('hoja')
        renglon = cleaned_data.get('renglon')

        if (hoja is not None and renglon is None) or (hoja is None and renglon is not None):
            campo_con_error = 'renglon' if hoja is not None else 'hoja'
            self.add_error(campo_con_error, 'Debe completar tanto la hoja como el renglón, o dejar ambos vacíos.')
        if (hoja is not None or renglon is not None) and not libro:
            self.add_error('libro', 'Debe seleccionar un libro para poder cargar hoja y renglón.')
        return cleaned_data


class AsignarLibroMovimientoForm(forms.Form):
    """
    Formulario auxiliar para crear o actualizar el asiento del libro 
    (libro, hoja y renglón) en un movimiento de caja.
    """
    libro = forms.ModelChoiceField(
        queryset=LibroCaja.objects.all(),
        required=True,
        label="Libro de Caja",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    hoja = forms.IntegerField(
        required=False, 
        label="Número de Hoja",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Pendiente si se deja vacío'})
    )
    renglon = forms.IntegerField(
        required=False, 
        label="Número de Renglón",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Pendiente si se deja vacío'})
    )

    def __init__(self, caja_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra los libros disponibles basándose estrictamente en la caja recibida
        if caja_id:
            self.fields['libro'].queryset = LibroCaja.objects.filter(
                caja__id=caja_id
            )
        else:
            self.fields['libro'].queryset = LibroCaja.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        hoja = cleaned_data.get('hoja')
        renglon = cleaned_data.get('renglon')

        # Regla de negocio: Si se ingresa hoja se exige renglón y viceversa
        if (hoja is not None and renglon is None) or (hoja is None and renglon is not None):
            raise ValidationError(
                "Debe completar tanto la hoja como el renglón, o dejar ambos vacíos."
            )
        return cleaned_data


class MovimientoCajaReporteForm(forms.Form):
    """Filtros para el listado 'Modificación' y para 'Reportes' de Movimientos de Caja."""
    caja = forms.ModelChoiceField(
        queryset=Caja.objects.all().order_by('nombre'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    tipo = forms.ModelChoiceField(
        queryset=BancoCuentaTipoMovim.objects.all().order_by('nombre'),
        required=False,
        label='Tipo de movimiento',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    receptor = forms.ModelChoiceField(
        queryset=Entidad.objects.all().order_by('nombre'),
        required=False,
        # Reemplazado por un buscador con autocompletado (ver
        # movimiento_caja_reporte.html); este campo queda oculto y lo
        # completa el JS del buscador.
        widget=forms.HiddenInput(),
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
    efectivizacion_desde = forms.DateField(
        required=False,
        label='Efectivización desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    efectivizacion_hasta = forms.DateField(
        required=False,
        label='Efectivización hasta',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    diferido_desde = forms.DateField(
        required=False,
        label='Diferido desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    diferido_hasta = forms.DateField(
        required=False,
        label='Diferido hasta',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    sin_efectivizar = forms.BooleanField(
        required=False,
        label='Sólo sin efectivización',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        pares = (
            ('fecha_desde', 'fecha_hasta', 'Emisión'),
            ('efectivizacion_desde', 'efectivizacion_hasta', 'Efectivización'),
            ('diferido_desde', 'diferido_hasta', 'Diferido'),
        )
        for campo_desde, campo_hasta, etiqueta in pares:
            desde = cleaned_data.get(campo_desde)
            hasta = cleaned_data.get(campo_hasta)
            if desde and hasta and desde > hasta:
                self.add_error(campo_hasta, f'"{etiqueta} hasta" no puede ser anterior a "{etiqueta} desde".')
        return cleaned_data


class RankingEntidadesForm(forms.Form):
    """Filtro (sólo por fecha de emisión) para el ranking de entidades por monto total."""
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

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get('fecha_desde')
        hasta = cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', '"Emisión hasta" no puede ser anterior a "Emisión desde".')
        return cleaned_data