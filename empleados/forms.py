from django import forms

from .models import Empleado


class EmpleadoForm(forms.ModelForm):
    class Meta:
        model = Empleado
        fields = ['nombre', 'apellido', 'documento', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'documento': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
