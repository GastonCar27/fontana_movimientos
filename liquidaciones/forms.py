from django import forms
from entidades.models import Entidad

from .models import Liquidacion


class LiquidacionSeleccionForm(forms.Form):
    """Form usado solo para renderizar el <select> de entidades (y el de
    tipo pago/cobro) en el template."""
    fecha = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    entidad = forms.ModelChoiceField(
        queryset=Entidad.objects.all().order_by('nombre'),
        required=False,
    )
    tipo = forms.ChoiceField(
        choices=Liquidacion.TIPO_CHOICES,
        required=False,
        initial=Liquidacion.TIPO_PAGO,
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
    # 07/10/2026 (pedido de Gastón): una fila por entidad con la cantidad de
    # liquidaciones y la suma de Debe / Haber.
    agrupar_entidad = forms.BooleanField(
        required=False,
        label='Agrupar por entidad',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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


class ComprobantesSinLiquidarFiltroForm(SinLiquidarFiltroForm):
    """Mismo filtro que `SinLiquidarFiltroForm`, con dos checkboxes de más
    sólo para el listado de Comprobantes sin liquidar (pedido de Gastón,
    25/09/2026): poder excluir los comprobantes donde Fontana es la
    EMISORA y/o los que Fontana es la RECEPTORA -- son independientes (se
    puede tildar uno solo, los dos, o ninguno) para poder quedarse viendo
    sólo "lo que le compramos a terceros" o sólo "lo que le facturamos a
    terceros", según haga falta."""
    excluir_fontana_emisora = forms.BooleanField(
        required=False,
        label='Excluir donde Fontana es la emisora',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    excluir_fontana_receptora = forms.BooleanField(
        required=False,
        label='Excluir donde Fontana es la receptora',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    # Pedido de Gastón (07/10/2026): por defecto NO se muestran las ventas
    # de Fontana a Consumidor Final (no se liquidan contra nadie); tildando
    # esto se vuelven a incluir.
    incluir_consumidor_final = forms.BooleanField(
        required=False,
        label='Incluir ventas de Fontana a Consumidor Final',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class MovimientosCajaSinLiquidarFiltroForm(SinLiquidarFiltroForm):
    """Filtro del listado de Movimientos de caja sin liquidar (pedido de
    Gastón, 30/09/2026): además de Entidad/fechas, poder ver sólo los que
    no están en una liquidación de PAGO (Fontana le paga a la entidad:
    receptor = la entidad) y/o de COBRO (la entidad le paga a Fontana:
    receptor = Fontana, emisor = la entidad) -- mismo criterio direccional
    que liquidaciones.views._armar_items --, y excluir los movimientos donde
    Fontana es la emisora y/o la receptora."""
    sin_liq_pago = forms.BooleanField(
        required=False,
        label='Solo sin liquidación de pago',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    sin_liq_cobro = forms.BooleanField(
        required=False,
        label='Solo sin liquidación de cobro',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    excluir_fontana_emisora = forms.BooleanField(
        required=False,
        label='Excluir donde Fontana es la emisora',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    excluir_fontana_receptora = forms.BooleanField(
        required=False,
        label='Excluir donde Fontana es la receptora',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
