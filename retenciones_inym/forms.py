from decimal import Decimal, ROUND_HALF_UP

from django import forms

from entidades.models import Inym_Operador
from .models import CertificadoNoAplicacionInym, InymRetencionTipo, RetencionInymNoAplicacionVinculo


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


def texto_operador_inym(operador):
    """Mismo criterio de etiqueta que fontana_escritorio usa para listar
    operadores INYM: entidad + tipo de operador, para poder distinguir
    cuando una misma entidad tiene más de un rol INYM (por ejemplo
    Productor y Secadero). Usado tanto por el <option>/valor precargado del
    buscador (ver OperadorInymChoiceField abajo y retenciones_inym/views.py)
    como por el resultado JSON del buscador (operador_inym_buscar)."""
    return f'{operador.entidad.nombre} ({operador.tipo_operador.nombre})'


class OperadorInymChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return texto_operador_inym(obj)


class CertificadoNoAplicacionSelect(forms.Select):
    """<select> que agrega a cada opción el operador INYM que validó el
    certificado (data-operador-valida), para que el JS del form pueda
    mostrar primero/sólo los del operador que nos retuvo."""
    operadores = {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        clave = str(getattr(value, 'value', value) or '')
        if clave:
            opcion['attrs']['data-operador-valida'] = self.operadores.get(clave, '')
        return opcion


class CertificadoNoAplicacionChoiceField(forms.ModelChoiceField):
    """Muestra en cada opción número, fecha, quién lo validó, total y saldo
    disponible. 'saldos' lo completa RetencionInymForm.__init__."""
    saldos = {}

    def label_from_instance(self, obj):
        from movimientos.templatetags.movimientos_extras import separador_miles
        partes = [f'N° {obj.numero}']
        if obj.fecha:
            partes.append(obj.fecha.strftime('%d/%m/%Y'))
        partes.append(f'validado por: {obj.nombre_valida}' if obj.nombre_valida else 'sin validar')
        if obj.total is not None:
            partes.append(f'total $ {separador_miles(obj.total)}')
        saldo = self.saldos.get(obj.id)
        if saldo is not None:
            partes.append(f'disponible $ {separador_miles(saldo)}')
        return ' — '.join(partes)


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
    # Pedido de Gastón (24/09/2026): reemplazar los <select> de Operador
    # emisor/retenido (con TODOS los operadores INYM cargados) por un
    # buscador con autocompletado, mismo patrón que
    # retenciones.forms.RetencionHeaderForm.entidad/entidad_nombre --
    # ModelChoiceField oculto (valida el id elegido, sigue restringido al
    # queryset) + CharField visible aparte para tipear y buscar (ver
    # retenciones_inym/views.py::operador_inym_buscar y
    # retencion_inym_form.html). El campo oculto sigue siendo la fuente de
    # verdad que se guarda -- el CharField de texto es sólo para la UI.
    operador_emisor = OperadorInymChoiceField(
        queryset=Inym_Operador.objects.select_related('entidad', 'tipo_operador'),
        # Pasó a ser obligatorio (25/09/2026, pedido de Gastón): un
        # operador_emisor vacío hace que la retención no calce con ninguna
        # dirección de liquidación (ver liquidaciones/views.py::_armar_items,
        # que exige que la otra parte sea explícitamente Fontana) aunque sí
        # aparezca como "pendiente de liquidar" en el listado general (que
        # sólo mira operador_retenido) -- quedaba visible pero imposible de
        # liquidar. Ver también el comando `auditar_operador_emisor_vacio`
        # para detectar los registros legacy que ya quedaron así (creados
        # antes de este cambio, o por una importación de Excel cuya fila no
        # traía el operador emisor).
        required=True,
        label='Operador emisor',
        widget=forms.HiddenInput(),
    )
    operador_emisor_nombre = forms.CharField(
        required=False,
        label='Operador emisor',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm operador-inym-buscador',
            'autocomplete': 'off',
            'placeholder': 'Buscar por nombre o CUIT...',
        }),
    )
    operador_retenido = OperadorInymChoiceField(
        queryset=Inym_Operador.objects.select_related('entidad', 'tipo_operador'),
        required=True,
        label='Operador retenido',
        widget=forms.HiddenInput(),
    )
    operador_retenido_nombre = forms.CharField(
        required=False,
        label='Operador retenido',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm operador-inym-buscador',
            'autocomplete': 'off',
            'placeholder': 'Buscar por nombre o CUIT...',
        }),
    )
    kgs = forms.DecimalField(
        required=False, label='Kgs', max_digits=20, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'id': 'id_kgs'}),
    )
    tarifa = forms.DecimalField(
        # Pedido de Gastón (24/09/2026): hasta 6 decimales -- hay tarifas
        # reales como 129,856600. OJO: la columna real de MySQL
        # (managed=False) también hay que ampliarla a mano, ver
        # sql/2026-09-24_ampliar_decimales_tarifa_retencion_inym.sql -- sin
        # correr ese script, MySQL sigue redondeando a 2 decimales al
        # guardar aunque este form ya acepte hasta 6.
        required=False, label='Tarifa', max_digits=20, decimal_places=6,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.000001', 'id': 'id_tarifa'}),
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

    # --- Certificado de no aplicación (02/10/2026, pedido de Gastón) ---
    # Las retenciones que le hacen a Fontana no se pueden bajar de INYM: se
    # reciben y se cargan a mano, y recién ahí se sabe si el que retuvo
    # descontó un certificado de no aplicación de Fontana. 'total' sigue
    # siendo el BRUTO (kgs x tarifa); lo realmente retenido es
    # total - importe_no_aplicado (es lo que se usa en liquidaciones).
    cert_no_aplicacion = CertificadoNoAplicacionChoiceField(
        queryset=CertificadoNoAplicacionInym.objects.none(),
        required=False,
        label='Certificado de no aplicación',
        widget=CertificadoNoAplicacionSelect(attrs={'class': 'form-control form-control-sm', 'id': 'id_cert_no_aplicacion'}),
    )
    importe_no_aplicado = forms.DecimalField(
        required=False, label='Importe no retenido (descontado con el certificado)',
        max_digits=20, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'id': 'id_importe_no_aplicado'}),
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
        # Certificados ofrecidos: los no eliminados en INYM con saldo
        # disponible, más el que ya esté vinculado a esta retención.
        from django.db.models import Q as _Q
        vinculados = []
        if instance_id is not None:
            vinculados = list(
                RetencionInymNoAplicacionVinculo.objects.filter(retencion_id=instance_id)
                .values_list('certificado_id', flat=True)
            )
        candidatos = (
            CertificadoNoAplicacionInym.objects
            .filter(_Q(fecha_eliminacion__isnull=True) | _Q(id__in=vinculados))
            .prefetch_related('aplicaciones')
            .order_by('-fecha', '-numero')
        )
        ids = []
        self.saldos_cert = {}
        for cert in candidatos:
            # Saldo disponible para ESTA retención: no cuenta lo que ya
            # tiene aplicado esta misma retención (si se está modificando).
            aplicado_otros = sum(
                (v.importe for v in cert.aplicaciones.all() if v.retencion_id != instance_id), Decimal('0')
            )
            saldo = (cert.total - aplicado_otros) if cert.total is not None else None
            self.saldos_cert[cert.id] = saldo
            if cert.id in vinculados or saldo is None or saldo > 0:
                ids.append(cert.id)
        self.fields['cert_no_aplicacion'].queryset = (
            CertificadoNoAplicacionInym.objects.filter(id__in=ids).order_by('-fecha', '-numero')
        )
        self.fields['cert_no_aplicacion'].saldos = self.saldos_cert
        self.fields['cert_no_aplicacion'].widget.operadores = {
            str(c.id): str(c.id_operador_valida or '') for c in candidatos if c.id in ids
        }

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
        # Certificado de no aplicación (02/10/2026).
        cert = cleaned.get('cert_no_aplicacion')
        importe_na = cleaned.get('importe_no_aplicado')
        if cert is None and importe_na:
            self.add_error('cert_no_aplicacion', 'Elegí el certificado de no aplicación al que corresponde ese importe.')
        elif cert is not None:
            if not importe_na or importe_na <= 0:
                self.add_error('importe_no_aplicado', 'Cargá el importe que se descontó con el certificado (mayor a 0).')
            else:
                total_bruto = cleaned.get('total')
                if total_bruto is not None and importe_na > total_bruto:
                    self.add_error(
                        'importe_no_aplicado',
                        f'No puede ser mayor que el total de la retención ({total_bruto}).',
                    )
                saldo = self.saldos_cert.get(cert.id)
                if saldo is not None and importe_na > saldo:
                    self.add_error(
                        'importe_no_aplicado',
                        f'El certificado N° {cert.numero} sólo tiene disponible {saldo} '
                        '(total del certificado menos lo ya descontado en otras retenciones).',
                    )

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


class ImportadorInymHistoricoForm(forms.Form):
    """Carga del Excel de INYM a la tabla histórica de análisis
    (RetencionInymHistorico) -- pedido de Gastón, 24/09/2026. A diferencia
    de ImportadorInymForm (importación operativa), acá fecha_desde y
    fecha_hasta son OBLIGATORIAS: no se puede cargar el archivo completo
    sin querer, porque van a aparecer muchas retenciones de fechas viejas
    que todavía no se manejaban con esta app."""
    archivo = forms.FileField(
        label='Excel de INYM',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm', 'accept': '.xls,.xlsx'}),
    )
    fecha_desde = forms.DateField(
        required=True,
        label='Fecha desde',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
    )
    fecha_hasta = forms.DateField(
        required=True,
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


class AnalisisKgsInymForm(forms.Form):
    """Filtros de la pantalla "Análisis Kgs INYM" (histórico) -- rango de
    fecha opcional, tipo de tarifa (OBLIGATORIO, ver abajo) y qué operador
    de la retención representa "quién entregó/recibió" los kgs (pedido de
    Gastón, 24/09/2026: para "Hoja verde" es el operador retenido; para
    otros tipos de tarifa todavía no está definido, así que se deja
    elegible en pantalla en vez de asumir uno solo).

    `id_tipo_tarifa` es obligatorio y SIN opción "todas" a propósito --
    pedido de Gastón (24/09/2026): "que no me permita mezclar los kgs de
    distintas tarifas" (kgs de Hoja verde y de Hoja verde y yerba mate
    canchada, por ejemplo, no son comparables/sumables entre sí). El valor
    por defecto es "Hoja verde" (se resuelve por nombre en la vista, no
    por id -- el id de cada tipo de tarifa lo define INYM, no es fijo)."""
    ROL_OPERADOR_CHOICES = [
        ('retenido', 'Operador retenido (quien recibe)'),
        ('emisor', 'Operador emisor (quien entrega)'),
    ]
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
    id_tipo_tarifa = forms.ModelChoiceField(
        queryset=InymRetencionTipo.objects.all().order_by('nombre'),
        required=True,
        empty_label=None,
        label='Tipo de tarifa',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    rol_operador = forms.ChoiceField(
        required=False,
        choices=ROL_OPERADOR_CHOICES,
        initial='retenido',
        label='Agrupar por',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get('fecha_desde')
        hasta = cleaned_data.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', '"Fecha hasta" no puede ser anterior a "Fecha desde".')
        if not cleaned_data.get('rol_operador'):
            cleaned_data['rol_operador'] = 'retenido'
        return cleaned_data
