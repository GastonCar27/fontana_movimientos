from django import forms


class RankingEntidadesForm(forms.Form):
    """Filtro (fecha de la retención y, opcionalmente, excluir a Fontana)
    para el ranking de entidades retenidas por monto total de retenciones
    INYM. Mismo patrón que comprobantes.forms.RankingEntidadesForm /
    movimientos_caja.forms.RankingEntidadesForm."""
    fecha_desde = forms.DateField(
        required=False,
        label='Fecha desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        label='Fecha hasta',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    excluir_fontana = forms.BooleanField(
        required=False,
        label='Excluir Fontana (entidad propia)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get('fecha_desde')
        hasta = cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', '"Fecha hasta" no puede ser anterior a "Fecha desde".')
        return cleaned_data
