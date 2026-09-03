from django.forms import ModelForm
from django.db import models
from entidades.models import Entidad
from productos.models import ProductoDetalle
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

def crear_campo_producto():
    return forms.ModelChoiceField(
        queryset=ProductoDetalle.objects.all(), # Aquí defines el "otro modelo"
        label="Selecciona un producto",
        empty_label="--- Elige una opción ---",
        required=False

    )
def crear_campo_buscador_producto():
    return forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar producto...',
            'autocomplete': 'off'
        })
        )

def crear_campo_fecha():
    return forms.DateField(
        required=False,
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date'}
        ))

class BuscarConFechasForm(forms.Form):
    fecha_desde = crear_campo_fecha()
    fecha_hasta = crear_campo_fecha()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nuevo_orden = ['fecha_desde','fecha_hasta']
        self.order_fields(nuevo_orden) #orden de los inputs

"""

class BuscarSaldoProductoEntidadForm(BuscarSaldoProductoMovimientoComprobanteForm):
    buscador_emisor = crear_campo_buscador_emisor()
    buscador_producto = crear_campo_buscador_producto()
    emisor = crear_campo_emisor()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nuevo_orden = ['fecha_desde','fecha_hasta','buscador_emisor','emisor','buscador_producto','producto']
        self.order_fields(nuevo_orden) #orden de los inputs
"""

def crear_campo_fecha():
    return forms.DateField(
        required=False,
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date'}
        ))



