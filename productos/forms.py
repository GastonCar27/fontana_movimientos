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

    def clean_nombre(self):
        """Avisa (con un error de formulario, no en silencio) si ya existe
        un producto con el mismo nombre -- pedido explícito, para no dar de
        alta el mismo producto dos veces por error. La comparación no
        distingue mayúsculas/minúsculas ni espacios de más al principio o
        al final, y al editar se excluye el propio producto (si no,
        guardarlo sin cambiar el nombre "chocaría" contra sí mismo)."""
        nombre = self.cleaned_data['nombre'].strip()
        duplicados = ProductoDetalle.objects.filter(nombre__iexact=nombre)
        if self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)
        existente = duplicados.first()
        if existente:
            raise forms.ValidationError(
                f'Ya existe un producto con ese nombre: "{existente}". '
                'Si es un producto distinto, usá un nombre que lo diferencie.'
            )
        return nombre
