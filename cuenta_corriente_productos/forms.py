from django import forms

from comprobantes.models import ComprobanteUnidadDeMedida
from productos.models import ProductoDetalle

from .models import ProductoEquivalenciaKg

# Mismo id que views.UNIDAD_MEDIDA_KILOGRAMOS_ID (no se importa de ahí para
# no generar un import circular entre views.py y este archivo).
UNIDAD_MEDIDA_KILOGRAMOS_ID = '01'


class ProductoEquivalenciaKgForm(forms.ModelForm):
    """
    Alta/edición de una fila de "Equivalencias de unidades" (ver
    ProductoEquivalenciaKg). El producto se elige con el mismo buscador
    con autocompletado que el resto de la app (campo oculto, completado
    por JS -- ver equivalencia_kg_form.html), igual que
    comprobantes.forms.ComprobanteRenglonForm.
    """
    class Meta:
        model = ProductoEquivalenciaKg
        fields = ['producto', 'unidad', 'factor_kg']
        widgets = {
            'producto': forms.HiddenInput(),
            'unidad': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'factor_kg': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
        }
        labels = {
            'factor_kg': 'Kg por unidad',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = ProductoDetalle.objects.order_by('nombre')
        # Nunca tiene sentido una equivalencia de Kg a Kg -- el destino de
        # la conversión siempre es Kg (ver views._total_movimiento_en_kg).
        self.fields['unidad'].queryset = (
            ComprobanteUnidadDeMedida.objects.exclude(pk=UNIDAD_MEDIDA_KILOGRAMOS_ID).order_by('nombre')
        )
        self.fields['unidad'].label = 'Unidad (no Kg)'

    def clean(self):
        cleaned = super().clean()
        producto = cleaned.get('producto')
        unidad = cleaned.get('unidad')
        if producto and unidad:
            ya_existe = ProductoEquivalenciaKg.objects.filter(producto=producto, unidad=unidad)
            if self.instance.pk:
                ya_existe = ya_existe.exclude(pk=self.instance.pk)
            if ya_existe.exists():
                self.add_error(
                    'unidad',
                    f'Ya existe una equivalencia cargada para {producto} en esa unidad -- '
                    'modificá esa fila en vez de crear una nueva.',
                )
        return cleaned
