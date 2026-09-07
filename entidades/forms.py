
from entidades.models import Entidad, Rol
from django import forms

def crear_campo_emisor():
    return forms.ModelChoiceField(
        required=False,
        queryset=Entidad.objects.all(), # Aquí defines el "otro modelo"
        label="Selecciona un emisor",
        empty_label="--- Elige una opción ---"
    )

def crear_campo_buscador_emisor():
    return forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar emisor...',
            'autocomplete': 'off'
        })
        )
class BuscarEntidadEmisorForm(forms.Form):
    buscador_emisor = crear_campo_buscador_emisor()
    emisor = crear_campo_emisor()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nuevo_orden = ['buscador_emisor','emisor']
        self.order_fields(nuevo_orden) #orden de los inputs


class EntidadRolRapidoForm(forms.Form):
    """Alta rápida embebida (ver patrón ProductoDetalleCrearForm en
    comprobantes/forms.py) de una Entidad para asignarle, de una, un tipo de
    entidad (Rol) puntual. Pensado para los buscadores de transportista/
    chofer del alta de Remito, pero reusable por cualquier pantalla que
    necesite "crear o sumarle el rol a una entidad existente que no lo
    tiene" sin salir de su propio formulario. Si ya existe una entidad con
    el mismo CUIT no se crea de nuevo: sólo se le agrega el rol si no lo
    tenía (ver entidades.views.entidad_crear_rapido)."""
    use_required_attribute = False

    nombre = forms.CharField(
        max_length=105,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
    )
    cuit = forms.CharField(
        max_length=45,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
    )


class RolForm(forms.ModelForm):
    """Alta y modificación de un "tipo de entidad" (Rol). El slug se calcula
    solo (ver rol_alta/rol_editar en views.py), no se pide en el formulario."""

    class Meta:
        model = Rol
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].required = True


class EntidadAltaForm(forms.ModelForm):
    """Alta de una Entidad nueva. El id NO se pide acá: lo calcula la vista
    (ver siguiente_id_entidad en views.py), priorizando el primero libre
    entre 2815 y 3000. 'roles' es la relación inversa M2M con Rol (los
    "tipos de entidad"); como es inversa, Django no la arma sola en el
    ModelForm, así que se declara a mano y se guarda a mano en la vista
    (entidad.roles.set(...))."""

    roles = forms.ModelMultipleChoiceField(
        queryset=Rol.objects.all().order_by('nombre'),
        required=False,
        label='Tipos de entidad',
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Entidad
        fields = [
            'nombre', 'cuit', 'documento_nro', 'direccion', 'localidad',
            'provincia', 'codpos', 'codigo', 'iva', 'activo',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'cuit': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'documento_nro': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'localidad': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'provincia': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'codpos': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'codigo': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'iva': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }