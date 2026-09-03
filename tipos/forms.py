from django import forms


class BootstrapModelForm(forms.ModelForm):
    """ModelForm base que le agrega la clase de Bootstrap a todos sus
    campos automáticamente, para no tener que repetir el widget en cada
    caso del registro (la mayoría son un único CharField 'nombre')."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            clases_actuales = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (clases_actuales + ' form-control form-control-sm').strip()


def form_class_para(config):
    """Arma dinámicamente el ModelForm para el modelo/campos de esta
    entrada del registro (tipos/registry.py)."""
    return forms.modelform_factory(
        config['model'],
        form=BootstrapModelForm,
        fields=[nombre_campo for nombre_campo, _etiqueta in config['campos']],
    )
