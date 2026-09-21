from django import forms
from django.forms import inlineformset_factory

from comprobantes.models import ComprobanteUnidadDeMedida, SectorTipo
from entidades.models import Entidad
from productos.models import ProductoDetalle

from .models import SolicitudCompra, SolicitudCompraRenglon


class SolicitudCompraForm(forms.ModelForm):
    class Meta:
        model = SolicitudCompra
        fields = ['fecha', 'entidad', 'solicitante', 'responsable_retiro', 'estado', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            # Los <select> de entidad/empleado se reemplazan por buscadores
            # con autocompletado (ver form.html); estos campos quedan
            # ocultos y los completa el JS del buscador.
            'entidad': forms.HiddenInput(),
            'solicitante': forms.HiddenInput(),
            'responsable_retiro': forms.HiddenInput(),
            'estado': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['entidad'].queryset = Entidad.objects.order_by('nombre')
        self.fields['entidad'].label = 'Proveedor'
        # Cada campo se restringe a las entidades que tengan el tipo de
        # entidad (Rol) correspondiente -- ver SolicitudCompra.ROL_* en
        # models.py. No se exige 'activo=True' porque Entidad no tiene ese
        # concepto separado de "empleado activo": se maneja dándole/
        # quitándole el rol desde Entidades -> Modificación.
        self.fields['solicitante'].queryset = Entidad.objects.filter(
            roles__nombre=SolicitudCompra.ROL_AUTORIZADO_SOLICITAR,
        ).order_by('nombre')
        self.fields['responsable_retiro'].queryset = Entidad.objects.filter(
            roles__nombre=SolicitudCompra.ROL_AUTORIZADO_RETIRO,
        ).order_by('nombre')


class SolicitudCompraRenglonForm(forms.ModelForm):
    class Meta:
        model = SolicitudCompraRenglon
        fields = ['cantidad', 'unidad_medida', 'prioridad', 'estado', 'sector', 'descripcion', 'producto_sugerido']
        widgets = {
            'cantidad': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01'}),
            # 'descripcion-input' se usa para engancharle el autocompletado
            # de descripciones ya usadas (ver ProductoGenerico en models.py
            # y el JS de form.html); autocomplete='off' es el del navegador,
            # que si no molesta tapando las sugerencias propias.
            'descripcion': forms.TextInput(attrs={'class': 'form-control form-control-sm descripcion-input', 'autocomplete': 'off'}),
            'prioridad': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            # 'renglon-estado' se usa desde JS para poder aplicarle un mismo
            # estado a todos los renglones de una (ver el botón "Aplicar a
            # todos" en form.html).
            'estado': forms.Select(attrs={'class': 'form-select form-select-sm renglon-estado'}),
            'sector': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            # Reemplazado por un buscador con autocompletado (ver form.html);
            # este campo queda oculto y lo completa el JS del buscador.
            'producto_sugerido': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto_sugerido'].queryset = ProductoDetalle.objects.order_by('nombre')
        self.fields['producto_sugerido'].required = False
        self.fields['producto_sugerido'].empty_label = '--- (sin definir todavía) ---'

        # Sector: <select> con las opciones cargadas en sector_tipo.
        self.fields['sector'].queryset = (
            SectorTipo.objects.exclude(nombre__isnull=True).exclude(nombre='').order_by('nombre')
        )
        self.fields['sector'].required = False
        self.fields['sector'].empty_label = '---------'

        # unidad_medida deja de ser texto libre: pasa a ser un <select> que
        # solo permite elegir valores que están cargados en la tabla
        # comprobante_unidad_de_medida (mismo catálogo que usan los
        # comprobantes de compra), para no seguir arrastrando unidades
        # tipeadas a mano y que no coinciden entre sí.
        nombres = list(
            ComprobanteUnidadDeMedida.objects
            .exclude(nombre__isnull=True).exclude(nombre='')
            .order_by('nombre')
            .values_list('nombre', flat=True)
        )
        choices = [('', '---------')] + [(nombre, nombre) for nombre in nombres]

        # Si el renglón ya existía y su unidad guardada no está en la tabla
        # (dato viejo tipeado a mano antes de este cambio), se agrega igual
        # como opción para no perderlo/pisarlo la próxima vez que se guarde.
        valor_actual = self.instance.unidad_medida if self.instance and self.instance.pk else ''
        if valor_actual and valor_actual not in nombres:
            choices.append((valor_actual, f'{valor_actual} (valor anterior, no está en la tabla)'))

        self.fields['unidad_medida'] = forms.ChoiceField(
            choices=choices,
            required=False,
            initial='Unidad',
            label='U. de Medida',
            widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        )


SolicitudCompraRenglonFormSet = inlineformset_factory(
    SolicitudCompra,
    SolicitudCompraRenglon,
    form=SolicitudCompraRenglonForm,
    extra=3,
    can_delete=True,
)
