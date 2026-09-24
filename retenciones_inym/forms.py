from decimal import Decimal, ROUND_HALF_UP

from django import forms

from entidades.models import Inym_Operador
from .models import InymRetencionTipo


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


class OperadorInymChoiceField(forms.ModelChoiceField):
    """Mismo criterio de etiqueta que Inym_Operador.__str__ / que
    fontana_escritorio usa para listar operadores INYM: entidad + tipo de
    operador, para poder distinguir cuando una misma entidad tiene más de
    un rol INYM (por ejemplo Productor y Secadero)."""

    def label_from_instance(self, obj):
        return f'{obj.entidad.nombre} ({obj.tipo_operador.nombre})'


class RetencionInymForm(forms.Form):
    """Alta / edición de UN registro de `retencion_inym`. A diferencia de
    `retenciones` (donde varias filas comparten año+número y forman "un
    comprobante"), acá cada fila es un registro completo en sí mismo -- no
    hay agrupamiento, así que este form cubre todos los campos de la fila
    de una sola vez.

    Nota sobre `eliminacion`: NO es una baja lógica de esta app -- es un
    dato que viene tal cual del registro oficial de INYM (la fecha en la
    que esa retención fue anulada/eliminada del lado de INYM), así que se
    conserva como cualquier otro campo importado, editable igual que el
    resto."""

    fecha = forms.DateField(
        label='Fecha',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    periodo = forms.DateField(
        required=False,
        label='Período',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    id_tipo_tarifa = forms.ModelChoiceField(
        queryset=InymRetencionTipo.objects.all().order_by('nombre'),
        required=False,
        label='Tipo de tarifa',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    operador_emisor = OperadorInymChoiceField(
        queryset=Inym_Operador.objects.select_related('entidad', 'tipo_operador').order_by('entidad__nombre'),
        required=False,
        label='Operador emisor',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    operador_retenido = OperadorInymChoiceField(
        queryset=Inym_Operador.objects.select_related('entidad', 'tipo_operador').order_by('entidad__nombre'),
        required=True,
        label='Operador retenido',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    kgs = forms.DecimalField(
        required=False, label='Kgs', max_digits=20, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'id': 'id_kgs'}),
    )
    tarifa = forms.DecimalField(
        required=False, label='Tarifa', max_digits=20, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'id': 'id_tarifa'}),
    )
    total = forms.DecimalField(
        required=False, label='Total', max_digits=20, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'id': 'id_total'}),
    )
    eliminacion = forms.DateField(
        required=False,
        label='Fecha de eliminación (según registro oficial de INYM)',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    id_certificado_inym = forms.IntegerField(
        required=True,
        label='N° certificado INYM',
        help_text='Obligatorio: es lo que usa el importador de Excel para reconocer esta '
                   'retención y no cargarla dos veces (ver "editado por app"/historial, '
                   '24/09/2026). Se repite entre retenciones de distinto tipo de tarifa, '
                   'pero no dentro del mismo tipo de tarifa.',
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
    )

    def __init__(self, *args, instance_id=None, **kwargs):
        """instance_id: pk de la retención que se está modificando (None en
        alta) -- se necesita para que la validación de "no repetido dentro
        del mismo tipo de tarifa" no se dispare contra sí misma al guardar
        sin cambiar nada. Pedido de Gastón, 24/09/2026 (ver bug de la
        importación que creó una copia en vez de reconocer la retención
        2868 -- pasó porque "N° cert. INYM" podía quedar vacío en una carga
        manual; de acá en más es obligatorio y no se puede repetir)."""
        self.instance_id = instance_id
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        # El total se recalcula del lado del servidor cuando hay kgs y
        # tarifa cargados (kgs × tarifa), para no confiar ciegamente en lo
        # que haya hecho el cálculo en vivo del JS del navegador. Si falta
        # alguno de los dos, se respeta el total tal como se cargó (por
        # ejemplo un registro importado del Excel de INYM que ya trae el
        # total pero no siempre kgs/tarifa desglosados).
        kgs = cleaned.get('kgs')
        tarifa = cleaned.get('tarifa')
        if kgs is not None and tarifa is not None:
            cleaned['total'] = (kgs * tarifa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # "N° cert. INYM" no puede repetirse dentro del mismo tipo de
        # tarifa (ver models.py::RetencionInym.id_certificado_inym) -- se
        # valida acá porque este form no es un ModelForm. Pedido de
        # Gastón, 24/09/2026.
        id_certificado_inym = cleaned.get('id_certificado_inym')
        id_tipo_tarifa = cleaned.get('id_tipo_tarifa')
        if id_certificado_inym is not None and id_tipo_tarifa is not None:
            from .models import RetencionInym
            existe = RetencionInym.objects.filter(
                id_certificado_inym=id_certificado_inym, id_tipo_tarifa=id_tipo_tarifa,
            )
            if self.instance_id is not None:
                existe = existe.exclude(id=self.instance_id)
            duplicada = existe.first()
            if duplicada is not None:
                self.add_error(
                    'id_certificado_inym',
                    f'Ya existe la retención {duplicada.id} con este N° de certificado y este '
                    'tipo de tarifa.',
                )
        return cleaned


class ImportadorInymForm(forms.Form):
    """Alta masiva de retenciones INYM desde el Excel que exporta el portal
    de INYM ('Listado Comprobantes de Retención', .xls o .xlsx). Filtra por
    un lapso de fecha para no tener que importar el archivo completo cada
    vez, y el propio importador se encarga de no duplicar lo que ya esté
    cargado (ver retenciones_inym/importador.py)."""
    archivo = forms.FileField(
        label='Excel de INYM',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm', 'accept': '.xls,.xlsx'}),
    )
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

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get('fecha_desde')
        hasta = cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', '"Fecha hasta" no puede ser anterior a "Fecha desde".')
        return cleaned_data
