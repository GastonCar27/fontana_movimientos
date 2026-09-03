
from entidades.models import Entidad
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