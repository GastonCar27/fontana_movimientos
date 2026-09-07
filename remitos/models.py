"""
Modelos del alta/modificación de Remitos (ver
documentacion/Manual_Alta_Modificacion_Remitos.docx para el diseño completo
y documentacion/Manual_Tecnico_Remitos.docx para el detalle de tablas y
relaciones ya construidas).

Son todas tablas NUEVAS (a diferencia de entidad/comprobante/movimiento,
que son tablas legadas con managed=False): se dejan managed=True a
propósito para que Django las cree y las vaya migrando solo de acá en
adelante.
"""

from django.conf import settings
from django.db import models

from entidades.models import Entidad
from productos.models import ProductoDetalle
from comprobantes.models import ComprobanteUnidadDeMedida
from movimientos.models import Movimiento


# Id de la entidad "Fontana S.A." (ver también settings.ENTIDAD_PROPIA_ID,
# que es la fuente de verdad; se repite acá como default sólo por si algún
# entorno viejo no tiene el setting cargado).
ENTIDAD_PROPIA_ID = getattr(settings, 'ENTIDAD_PROPIA_ID', 100)


class Vehiculo(models.Model):
    """Camión/chasis identificado por un nombre (ej. 'Iveco 1') y su
    patente. El acoplado que lleva en un viaje puntual NO se guarda acá,
    porque puede cambiar con el tiempo (ver Acoplado y Remito.acoplado): la
    combinación vehículo+acoplado de cada viaje se registra en el propio
    Remito."""
    nombre = models.CharField(max_length=100)
    patente = models.CharField(max_length=20, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'remito_vehiculo'
        ordering = ['nombre']
        verbose_name = 'vehículo'
        verbose_name_plural = 'vehículos'

    def __str__(self):
        return f'{self.nombre} ({self.patente})'


class Acoplado(models.Model):
    """Acoplado identificado por su patente, independiente del vehículo: un
    mismo acoplado puede combinarse con distintos vehículos según el viaje
    (ver Vehiculo y Remito.vehiculo/Remito.acoplado)."""
    patente = models.CharField(max_length=20, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'remito_acoplado'
        ordering = ['patente']
        verbose_name = 'acoplado'
        verbose_name_plural = 'acoplados'

    def __str__(self):
        return self.patente


class CondicionVenta(models.Model):
    """Catálogo editable de condiciones de venta de un Remito (Contado,
    Cuenta Corriente, etc.). Tiene su propia pantalla de Alta/Modificación
    (no es sólo de /admin/) porque se espera que se sigan agregando valores
    con el tiempo (pedido explícito)."""
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'remito_condicion_venta'
        ordering = ['nombre']
        verbose_name = 'condición de venta'
        verbose_name_plural = 'condiciones de venta'

    def __str__(self):
        return self.nombre


class ObservacionEstandar(models.Model):
    """Texto de observación reutilizable entre remitos: se puede recuperar
    desde el alta de Remito en vez de volver a tipearlo cada vez (pedido
    explícito, porque "muchas veces se repiten")."""
    texto = models.CharField(max_length=500, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'remito_observacion_estandar'
        ordering = ['texto']
        verbose_name = 'observación estándar'
        verbose_name_plural = 'observaciones estándar'

    def __str__(self):
        return self.texto


class Remito(models.Model):
    """Cabecera de un Remito (comprobante de traslado de mercadería).

    'punto_venta' y 'numero' vienen preimpresos en el papel del talonario:
    los carga a mano quien hace el alta (no los asigna el sistema, a
    diferencia por ejemplo del id de Entidad). Son únicos por emisor (ver
    Meta.constraints): dos emisores distintos sí pueden repetir el mismo
    número, cada uno con su propio talonario.

    'tipo' define cuál de las dos partes es Fontana S.A. (la entidad
    propia, ver ENTIDAD_PROPIA_ID / settings.ENTIDAD_PROPIA_ID): en un
    remito de Salida, Fontana es 'emisor' y la otra entidad es 'receptor';
    en uno de Entrada es al revés. De cara al usuario esto se simplifica a
    un único campo "Cliente/Proveedor" (ver RemitoForm.contraparte, en
    forms.py, y la property 'contraparte' de acá abajo)."""

    TIPO_SALIDA = 'salida'
    TIPO_ENTRADA = 'entrada'
    TIPO_CHOICES = [
        (TIPO_SALIDA, 'Salida (Fontana emite el remito)'),
        (TIPO_ENTRADA, 'Entrada (Fontana recibe el remito)'),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default=TIPO_SALIDA)
    punto_venta = models.PositiveIntegerField('Punto de venta')
    numero = models.PositiveIntegerField('Número')
    fecha = models.DateField()
    emisor = models.ForeignKey(
        Entidad, on_delete=models.PROTECT, related_name='remitos_emitidos',
        db_column='id_entidad_emisor',
    )
    receptor = models.ForeignKey(
        Entidad, on_delete=models.PROTECT, related_name='remitos_recibidos',
        db_column='id_entidad_receptor',
    )
    condicion_venta = models.ForeignKey(
        CondicionVenta, on_delete=models.SET_NULL, blank=True, null=True, related_name='remitos',
    )
    valor_declarado = models.DecimalField(
        'Valor declarado', max_digits=14, decimal_places=2, blank=True, null=True,
    )
    transportista = models.ForeignKey(
        Entidad, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='remitos_como_transportista',
    )
    chofer = models.ForeignKey(
        Entidad, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='remitos_como_chofer',
    )
    vehiculo = models.ForeignKey(
        Vehiculo, on_delete=models.SET_NULL, blank=True, null=True, related_name='remitos',
    )
    acoplado = models.ForeignKey(
        Acoplado, on_delete=models.SET_NULL, blank=True, null=True, related_name='remitos',
    )
    observaciones = models.TextField(blank=True)
    guardado_el = models.DateTimeField(auto_now_add=True)
    modificado_el = models.DateTimeField(auto_now=True, verbose_name='fecha de edición')

    class Meta:
        db_table = 'remito'
        ordering = ['-fecha', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['emisor', 'punto_venta', 'numero'], name='remito_unico_por_emisor',
            ),
        ]

    def __str__(self):
        return f'{self.punto_venta:04d}-{self.numero:08d}'

    @property
    def es_salida(self):
        return self.emisor_id == ENTIDAD_PROPIA_ID

    @property
    def contraparte(self):
        """La entidad que no es Fontana: el cliente si es un remito de
        Salida, el proveedor si es de Entrada. Ver también
        RemitoForm.contraparte, en forms.py."""
        return self.receptor if self.es_salida else self.emisor


class RemitoRenglon(models.Model):
    """Un renglón (línea de detalle) de un Remito: un producto, la cantidad
    enviada y, opcionalmente, el vínculo con el Movimiento de productos que
    representa ese traslado (ver remitos.views._sincronizar_movimiento_renglon).

    'kilogramos_enviados' es el peso con el que se despachó desde origen;
    'kilogramos_confirmados' es el peso real que se pesó/facturó en destino,
    quede cargarse más tarde si difiere del enviado (por ej. se envían 700kg
    pero en destino pesan 690kg, que es lo que después se factura). El
    Movimiento vinculado usa siempre el peso "definitivo" -- el confirmado
    si ya se cargó, o si no, el enviado -- actualizándose en el mismo
    registro en vez de crear uno nuevo, para no duplicar el saldo del
    producto (ver kilogramos_definitivos)."""

    remito = models.ForeignKey(Remito, on_delete=models.CASCADE, related_name='renglones')
    orden = models.PositiveIntegerField(default=1)
    producto = models.ForeignKey(
        ProductoDetalle, on_delete=models.PROTECT, related_name='renglones_remito',
    )
    detalle_adicional = models.CharField(
        'Detalle adicional', max_length=200, blank=True,
        help_text='Aclaración libre sobre este renglón (ej. lote, calidad, etc.).',
    )
    cantidad = models.DecimalField(
        'Cantidad', max_digits=12, decimal_places=2, blank=True, null=True,
        help_text='Cantidad de bultos/unidades (ej. cantidad de bolsas), si corresponde.',
    )
    unidad_de_medida = models.ForeignKey(
        ComprobanteUnidadDeMedida, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='renglones_remito',
    )
    kilogramos_enviados = models.DecimalField('Kg. enviados', max_digits=12, decimal_places=2)
    kilogramos_confirmados = models.DecimalField(
        'Kg. confirmados en destino', max_digits=12, decimal_places=2, blank=True, null=True,
        help_text='Completar cuando se sepa el peso real recibido/facturado en destino, si difiere del enviado.',
    )
    movimiento = models.OneToOneField(
        Movimiento, on_delete=models.SET_NULL, blank=True, null=True, related_name='renglon_remito',
    )

    class Meta:
        db_table = 'remito_renglon'
        ordering = ['remito', 'orden', 'id']
        verbose_name = 'renglón de remito'
        verbose_name_plural = 'renglones de remito'

    def __str__(self):
        return f'{self.remito} - {self.producto}'

    @property
    def kilogramos_definitivos(self):
        """El peso a usar para el Movimiento vinculado (ver docstring de la
        clase): el confirmado si ya se cargó, o si no, el enviado."""
        return self.kilogramos_confirmados if self.kilogramos_confirmados is not None else self.kilogramos_enviados
