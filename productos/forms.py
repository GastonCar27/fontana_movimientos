from django import forms

from .models import ProductoDetalle, ItemTipo


class ProductoDetalleForm(forms.ModelForm):
    """Alta y modificación de un producto/ítem del catálogo (producto_detalle):
    nombre y categoría (item_tipo).

    Es el formulario "canónico" de esta alta (Tipos > Productos > Alta); el
    buscador de producto embebido en el alta de renglón de comprobante
    (comprobantes.forms.ProductoDetalleCrearForm) hereda de acá para no
    duplicar el mismo formulario dos veces.
    """

    class Meta:
        model = ProductoDetalle
        fields = ['nombre', 'item_tipo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].required = True
        self.fields['nombre'].widget.attrs['class'] = 'form-control form-control-sm'
        self.fields['item_tipo'].required = True
        self.fields['item_tipo'].queryset = ItemTipo.objects.order_by('nombre')
        self.fields['item_tipo'].empty_label = '--- Elegí una categoría ---'
        self.fields['item_tipo'].widget.attrs['class'] = 'form-control form-control-sm'
