from django import forms
from django.db.models import Q

from entidades.models import Entidad
from productos.models import ProductoDetalle
from comprobantes.models import ComprobanteUnidadDeMedida
# Alta rápida de producto: se reusa tal cual el formulario que ya usa el
# renglón de Comprobante (mismo catálogo de productos, mismo patrón de
# "alta rápida embebida" -- ver ProductoDetalleCrearForm en
# comprobantes/forms.py), en vez de duplicarlo para Remito.
from comprobantes.forms import ProductoDetalleCrearForm  # noqa: F401  (reexportado para las vistas)

from .models import Acoplado, CondicionVenta, ObservacionEstandar, Remito, RemitoRenglon, Vehiculo

# Nombres exactos de los tipos de entidad (Rol) usados para filtrar los
# buscadores de transportista/chofer (ver entidades/migrations/
# 0006_seed_tipos_entidad.py, que los precarga).
ROL_TRANSPORTISTA = 'Transportista'
ROL_CHOFER = 'Chofer de Transporte'


# ---------------------------------------------------------------------------
# Alta / Modificación de Remito (cabecera)
# ---------------------------------------------------------------------------

class RemitoForm(forms.ModelForm):
    """Alta y modificación de la cabecera de un Remito.

    'contraparte' no es un campo del modelo: reemplaza a emisor/receptor de
    cara al usuario (ver Remito.tipo y Remito.contraparte, en models.py).
    Según el tipo elegido (Salida/Entrada), la vista (remito_form) arma
    emisor/receptor a partir de 'contraparte' y de la entidad propia
    (Fontana, ver settings.ENTIDAD_PROPIA_ID): en un remito de Salida,
    Fontana es el emisor y 'contraparte' el receptor; en uno de Entrada, es
    al revés.

    'transportista' y 'chofer' se buscan (ver template remito_form.html)
    entre las entidades que ya tengan ese tipo de entidad asignado
    (ROL_TRANSPORTISTA / ROL_CHOFER); si la que se busca no aparece, el
    mismo buscador permite crearla o sumarle el rol sin salir de la
    pantalla (ver entidades:entidad_crear_rapido)."""

    contraparte = forms.ModelChoiceField(
        queryset=Entidad.objects.all(),
        label='Cliente / Proveedor',
        widget=forms.HiddenInput(),
    )
    transportista = forms.ModelChoiceField(
        queryset=Entidad.objects.filter(roles__nombre=ROL_TRANSPORTISTA),
        required=False,
        widget=forms.HiddenInput(),
    )
    chofer = forms.ModelChoiceField(
        queryset=Entidad.objects.filter(roles__nombre=ROL_CHOFER),
        required=False,
        widget=forms.HiddenInput(),
    )
    vehiculo = forms.ModelChoiceField(
        queryset=Vehiculo.objects.filter(activo=True),
        required=False,
        widget=forms.HiddenInput(),
    )
    acoplado = forms.ModelChoiceField(
        queryset=Acoplado.objects.filter(activo=True),
        required=False,
        widget=forms.HiddenInput(),
    )
    observacion_estandar = forms.ModelChoiceField(
        queryset=ObservacionEstandar.objects.filter(activa=True),
        required=False,
        label='Recuperar una observación estándar',
        help_text='Al elegir una, se agrega al final del texto de Observaciones.',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    guardar_observacion_estandar = forms.BooleanField(
        required=False,
        label='Guardar el texto de Observaciones como observación estándar (para reutilizarlo en otros remitos)',
    )

    class Meta:
        model = Remito
        fields = [
            'tipo', 'punto_venta', 'numero', 'fecha', 'condicion_venta',
            'valor_declarado', 'transportista', 'chofer', 'vehiculo',
            'acoplado', 'observaciones',
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'punto_venta': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'numero': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'condicion_venta': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'valor_declarado': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['condicion_venta'].required = False
        self.fields['condicion_venta'].empty_label = '--- Sin especificar ---'
        # Los querysets "activo/a" de acá abajo, salvo 'contraparte' (nunca
        # se filtra por activo), incluyen además el valor que ya tuviera
        # guardado la instancia en edición, aunque haya pasado a estar
        # inactivo mientras tanto -- si no, Django rechazaría como "opción
        # inválida" un remito ya guardado con ese valor con sólo abrirlo y
        # volver a guardarlo sin tocar el campo.
        self.fields['condicion_venta'].queryset = self._queryset_activos(
            CondicionVenta.objects.filter(activa=True), 'condicion_venta',
        )
        self.fields['transportista'].queryset = self._queryset_activos(
            self.fields['transportista'].queryset, 'transportista',
        )
        self.fields['chofer'].queryset = self._queryset_activos(
            self.fields['chofer'].queryset, 'chofer',
        )
        self.fields['vehiculo'].queryset = self._queryset_activos(
            Vehiculo.objects.filter(activo=True), 'vehiculo',
        )
        self.fields['acoplado'].queryset = self._queryset_activos(
            Acoplado.objects.filter(activo=True), 'acoplado',
        )

    def _queryset_activos(self, queryset, nombre_campo):
        valor_actual_id = getattr(self.instance, f'{nombre_campo}_id', None)
        if valor_actual_id and not queryset.filter(pk=valor_actual_id).exists():
            modelo = queryset.model
            queryset = modelo.objects.filter(Q(pk__in=queryset.values('pk')) | Q(pk=valor_actual_id))
        return queryset


# ---------------------------------------------------------------------------
# Alta / Modificación de RemitoRenglon
# ---------------------------------------------------------------------------

class RemitoRenglonForm(forms.ModelForm):
    class Meta:
        model = RemitoRenglon
        fields = [
            'remito', 'producto', 'detalle_adicional', 'cantidad',
            'unidad_de_medida', 'kilogramos_enviados', 'kilogramos_confirmados',
        ]
        widgets = {
            # Se reemplazan por buscadores con autocompletado (ver
            # remito_renglon_form.html); estos inputs quedan ocultos y los
            # completa el JS de los buscadores.
            'remito': forms.HiddenInput(),
            'producto': forms.HiddenInput(),
            'detalle_adicional': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Detalle adicional (opcional)',
            }),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'unidad_de_medida': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'kilogramos_enviados': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'kilogramos_confirmados': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['remito'].queryset = Remito.objects.order_by('-fecha', '-id')
        self.fields['producto'].queryset = ProductoDetalle.objects.order_by('nombre')
        self.fields['unidad_de_medida'].queryset = ComprobanteUnidadDeMedida.objects.order_by('nombre')
        self.fields['unidad_de_medida'].required = False
        self.fields['cantidad'].required = False
        self.fields['detalle_adicional'].required = False
        self.fields['kilogramos_confirmados'].required = False


# ---------------------------------------------------------------------------
# Catálogos: Vehículo / Acoplado / Condición de venta / Observación estándar
# ---------------------------------------------------------------------------

class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = ['nombre', 'patente', 'activo', 'acoplados_habituales']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Ej: Iveco 1'}),
            'patente': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'acoplados_habituales': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # VehiculoCrearRapidoForm (alta rápida embebida, más abajo) hereda
        # este __init__ pero no incluye 'acoplados_habituales' en su Meta.
        if 'acoplados_habituales' not in self.fields:
            return
        self.fields['acoplados_habituales'].required = False
        self.fields['acoplados_habituales'].help_text = (
            'Acoplados que se van a poder elegir para este vehículo al cargar un remito. '
            'Si no se marca ninguno, se va a poder elegir cualquier acoplado activo.'
        )
        # Igual que en RemitoForm._queryset_activos: si el vehículo ya tenía
        # vinculado un acoplado que mientras tanto pasó a estar inactivo, se
        # lo sigue mostrando (y marcado) para no "perderlo" al editar.
        queryset = Acoplado.objects.filter(activo=True)
        if self.instance.pk:
            ya_vinculados = self.instance.acoplados_habituales.values_list('pk', flat=True)
            queryset = Acoplado.objects.filter(Q(pk__in=queryset.values('pk')) | Q(pk__in=ya_vinculados))
        self.fields['acoplados_habituales'].queryset = queryset.order_by('patente')


class VehiculoCrearRapidoForm(VehiculoForm):
    """Alta rápida embebida del buscador de vehículo, en el alta de Remito
    (mismo patrón que ProductoDetalleCrearForm, comprobantes/forms.py). No
    incluye 'acoplados_habituales': ese vínculo se arma después, editando el
    vehículo desde su propia pantalla (Catálogos > Vehículos)."""
    use_required_attribute = False

    class Meta(VehiculoForm.Meta):
        fields = ['nombre', 'patente', 'activo']


class AcopladoForm(forms.ModelForm):
    class Meta:
        model = Acoplado
        fields = ['patente', 'activo']
        widgets = {
            'patente': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AcopladoCrearRapidoForm(AcopladoForm):
    """Alta rápida embebida del buscador de acoplado, en el alta de
    Remito."""
    use_required_attribute = False


class CondicionVentaForm(forms.ModelForm):
    class Meta:
        model = CondicionVenta
        fields = ['nombre', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ObservacionEstandarForm(forms.ModelForm):
    class Meta:
        model = ObservacionEstandar
        fields = ['texto', 'activa']
        widgets = {
            'texto': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
