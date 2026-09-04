from django import forms
from entidades.models import Entidad


class LiquidacionSeleccionForm(forms.Form):
    """Form usado solo para renderizar el <select> de entidades en el template."""
    fecha = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    entidad = forms.ModelChoiceField(
        queryset=Entidad.objects.all().order_by('nombre'),
        required=False,
    )


class LiquidacionReporteForm(forms.Form):
    # HiddenInput: el campo visible es el buscador con autocompletado
    # (id/nombre/CUIT) que arma el template con inicializarBuscador(),
    # apuntando a liquidaciones:entidad_buscar. Este campo oculto es el que
    # realmente viaja en el <form> con el id elegido.
    entidad = forms.ModelChoiceField(
        queryset=Entidad.objects.all().order_by('nombre'),
        required=False,
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


class RankingEntidadesForm(forms.Form):
    """Filtro (fecha de la liquidación y, opcionalmente, excluir a Fontana)
    para el ranking de entidades por monto total liquidado. Mismo patrón
    que comprobantes.forms.RankingEntidadesForm /
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


class SinLiquidarFiltroForm(forms.Form):
    """Filtro común (Entidad / Fecha desde / Fecha hasta) para los 4 listados
    de 'Sin liquidar' (Comprobantes, Movimientos de Caja, Retenciones y
    Retenciones INYM), mostrado en la ventana modal de filtro de cada uno.

    'entidad' es HiddenInput porque el campo visible es el buscador con
    autocompletado (id/nombre/CUIT) que arma cada template con
    inicializarBuscador(), apuntando a liquidaciones:entidad_buscar.
    """
    entidad = forms.ModelChoiceField(
        queryset=Entidad.objects.all().order_by('nombre'),
        required=False,
        widget=forms.HiddenInput(),
    )
    fecha_desde = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    fecha_hasta = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))