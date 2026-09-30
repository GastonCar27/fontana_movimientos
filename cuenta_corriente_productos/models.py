from decimal import Decimal

from django.db import models
from django.db.models import Sum, Case, When, F, Value, DecimalField
from django.utils import timezone

from entidades.models import Entidad
from productos.models import ProductoDetalle
from movimientos.models import Movimiento
from comprobantes.models import ComprobanteRenglon, ComprobanteUnidadDeMedida


class EstadoCuentaMovimiento(models.Model):
    """
    Estado de cuenta (abierto/cerrado) de un Movimiento de producto (kg).

    Un movimiento "abierto" todavía puede recibir más comprobantes
    vinculados (ver ComprobanteRenglonMovimiento) -- por ejemplo porque
    falta un ajuste de precio pendiente sobre esos mismos kgs (anticipo +
    ajustes, ver ComprobanteRenglonMovimiento). Un movimiento "cerrado" ya
    no se espera que reciba más vínculos, aunque nada a nivel de base de
    datos lo impide: el estado es puramente informativo, para poder
    filtrar qué kgs quedan pendientes de facturar/ajustar y cuáles ya
    están totalmente saldados (pantalla "Movimientos abiertos").

    Todo Movimiento nace "abierto" implícitamente: si no tiene fila acá,
    se lo considera abierto (ver `esta_abierto`). Esta tabla solo guarda
    una fila para los movimientos que alguien marcó explícitamente como
    Cerrado (o que se reabrieron después de haber estado cerrados).
    """
    ABIERTO = 'abierto'
    CERRADO = 'cerrado'
    ESTADOS = [
        (ABIERTO, 'Abierto'),
        (CERRADO, 'Cerrado'),
    ]

    movimiento = models.OneToOneField(
        Movimiento,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='estado_cuenta',
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ABIERTO)
    cerrado_el = models.DateTimeField(blank=True, null=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = 'estado de cuenta de movimiento'
        verbose_name_plural = 'estados de cuenta de movimientos'
        db_table = 'cta_cte_estado_movimiento'

    def __str__(self):
        return f'Movimiento {self.movimiento_id} - {self.get_estado_display()}'

    def cerrar(self, guardar=True):
        self.estado = self.CERRADO
        self.cerrado_el = timezone.now()
        if guardar:
            self.save()

    def reabrir(self, guardar=True):
        self.estado = self.ABIERTO
        self.cerrado_el = None
        if guardar:
            self.save()

    @classmethod
    def esta_abierto(cls, movimiento_id):
        """True si el movimiento está abierto (o no tiene fila acá, que
        equivale a "abierto" por default)."""
        estado = (
            cls.objects.filter(movimiento_id=movimiento_id)
            .values_list('estado', flat=True)
            .first()
        )
        return estado != cls.CERRADO


class ComprobanteRenglonMovimiento(models.Model):
    """
    Vincula un renglón de comprobante (comprobantes.ComprobanteRenglon) con
    el Movimiento de producto (kg) que ese renglón factura o ajusta.

    Un mismo movimiento puede tener varios renglones vinculados a lo largo
    del tiempo -- ej.: un anticipo y, más adelante, uno o más ajustes de
    precio sobre esos mismos kgs -- por eso NO hay unique en 'movimiento'
    solo, sino en el par (renglon, movimiento), para no poder vincular dos
    veces el mismo renglón al mismo movimiento por error.

    Este vínculo por sí solo NO clasifica el monto como debe/haber: esa
    clasificación se define recién al incluir el renglón en una
    LiquidacionProducto (ver LiquidacionProductoComprobanteRenglon.tipo).
    Mientras tanto, el monto del renglón aparece como "pendiente de
    liquidar" en la cuenta corriente de la entidad.
    """
    renglon = models.ForeignKey(
        ComprobanteRenglon,
        on_delete=models.CASCADE,
        related_name='vinculos_movimiento',
    )
    movimiento = models.ForeignKey(
        Movimiento,
        on_delete=models.CASCADE,
        related_name='vinculos_comprobante',
    )
    # Cuántos Kg (u otra unidad) del movimiento cubre ESTE vínculo en
    # particular. Se agregó porque un mismo movimiento puede necesitar
    # más de un renglón para cubrirse por completo (anticipo + ajustes de
    # precio, ver docstring de la clase) y un renglón puede facturar
    # menos cantidad que la suma de los movimientos que se le vinculan de
    # una sola vez ("Vincular por bloques") -- sin este campo, un
    # movimiento con CUALQUIER vínculo se consideraba 100% cubierto,
    # aunque el renglón vinculado facturara menos Kg de los que tiene el
    # movimiento, y esa diferencia dejaba de aparecer como pendiente.
    #
    # Puede quedar en null en vínculos viejos (de antes de este campo):
    # se interpreta como "se asume que este vínculo cubre el movimiento
    # completo", igual que el comportamiento previo a agregar el campo.
    # Los vínculos nuevos (creados por las vistas de este archivo) SIEMPRE
    # lo completan con un valor real.
    cantidad_kg = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True,
        verbose_name='cantidad (Kg u otra unidad) cubierta por este vínculo',
    )
    observaciones = models.CharField(max_length=255, blank=True)
    guardado_el = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'vínculo renglón-movimiento'
        verbose_name_plural = 'vínculos renglón-movimiento'
        db_table = 'cta_cte_comprobante_renglon_movimiento'
        constraints = [
            models.UniqueConstraint(fields=['renglon', 'movimiento'], name='cta_cte_renglon_movimiento_unico'),
        ]
        ordering = ['-guardado_el']

    def __str__(self):
        return f'Renglón {self.renglon_id} - Movimiento {self.movimiento_id}'


class LiquidacionProducto(models.Model):
    """
    Cierre/liquidación en pesos de la cuenta corriente de producto de una
    entidad: agrupa, para una entidad y un producto, los renglones de
    comprobante ya vinculados a movimientos (ComprobanteRenglonMovimiento)
    que se decide "cerrar" en este momento, y guarda los totales debe/haber
    resultantes.

    Mismo patrón que liquidaciones.Liquidacion (recalcular_totales() como
    única fuente de verdad), pero acá los "ítems" son renglones de
    comprobante en vez de comprobantes enteros: lo que importa es el
    producto (kg) facturado en ESE renglón, no el comprobante completo (que
    puede mezclar productos distintos en renglones distintos).
    """
    entidad = models.ForeignKey(Entidad, on_delete=models.PROTECT, related_name='liquidaciones_producto')
    producto = models.ForeignKey(ProductoDetalle, on_delete=models.PROTECT, related_name='liquidaciones_producto')
    numero = models.CharField(max_length=145, blank=True)
    fecha = models.DateField()
    debe_pesos = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0'))
    haber_pesos = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0'))
    observaciones = models.TextField(blank=True)
    guardado_el = models.DateTimeField(auto_now_add=True)
    modificado_el = models.DateTimeField(auto_now=True, verbose_name='fecha de edición')

    class Meta:
        verbose_name = 'liquidación de producto'
        verbose_name_plural = 'liquidaciones de producto'
        db_table = 'cta_cte_liquidacion_producto'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Liquidación {self.numero or self.id} - {self.entidad} - {self.producto}'

    def recalcular_totales(self, guardar=True):
        """
        Única fuente de verdad para debe_pesos/haber_pesos: suma, en base
        de datos, el total de cada renglón vinculado según su tipo
        ('debe'/'haber') -- mismo criterio que Liquidacion.recalcular_totales.
        """
        agregado = self.renglones.aggregate(
            debe=Sum(
                Case(
                    When(tipo='debe', then=F('renglon__total')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
            haber=Sum(
                Case(
                    When(tipo='haber', then=F('renglon__total')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            ),
        )
        self.debe_pesos = (agregado['debe'] or Decimal('0')).quantize(Decimal('0.01'))
        self.haber_pesos = (agregado['haber'] or Decimal('0')).quantize(Decimal('0.01'))
        if guardar:
            self.save(update_fields=['debe_pesos', 'haber_pesos'])
        return self.debe_pesos, self.haber_pesos

    @property
    def diferencia_pesos(self):
        return (self.debe_pesos or Decimal('0')) - (self.haber_pesos or Decimal('0'))


class LiquidacionProductoComprobanteRenglon(models.Model):
    """
    Ítem de una LiquidacionProducto: un renglón de comprobante (ya vinculado
    a algún movimiento vía ComprobanteRenglonMovimiento) que se incluye en
    este cierre, con su tipo (debe/haber).

    'renglon' es OneToOneField a propósito: un mismo renglón no puede
    quedar incluido en más de una liquidación (no se puede "cobrar" dos
    veces la misma plata), a diferencia de ComprobanteRenglonMovimiento,
    que sí permite que un mismo movimiento (los mismos kgs) tenga varios
    renglones vinculados a lo largo del tiempo.
    """
    TIPOS = [
        ('debe', 'Debe'),
        ('haber', 'Haber'),
    ]

    liquidacion = models.ForeignKey(
        LiquidacionProducto,
        on_delete=models.CASCADE,
        related_name='renglones',
    )
    renglon = models.OneToOneField(
        ComprobanteRenglon,
        on_delete=models.CASCADE,
        related_name='liquidacion_producto',
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)

    class Meta:
        verbose_name = 'renglón de liquidación de producto'
        verbose_name_plural = 'renglones de liquidación de producto'
        db_table = 'cta_cte_liquidacion_producto_comprobante_renglon'

    def __str__(self):
        return f'Liquidación {self.liquidacion_id} - Renglón {self.renglon_id} ({self.tipo})'


class ProductoEquivalenciaKg(models.Model):
    """
    Cuántos Kg equivale 1 unidad de una unidad de medida (Bolsa, Bolsón,
    Pack, etc.) para un producto puntual -- ej.: 1 Bolsa de YERBA MATE 'LA
    HUELLA' 4X2Kg = 8kg.

    Sirve para "Vincular por bloques": tanto un Movimiento como un
    ComprobanteRenglon pueden estar cargados en cualquier unidad -- un
    Movimiento no tiene restricción de catálogo, y un renglón de
    comprobante fiscal TAMPOCO factura siempre en Kg (puede estar en
    cualquier unidad válida para AFIP, ej. "Unidad", salvo Bolsa/Bolsón,
    exclusivas de movimientos y remitos -- ver
    comprobantes.models.IDS_UNIDADES_SOLO_REMITOS). Sin una equivalencia
    cargada acá, dos cosas en unidades distintas no se pueden vincular
    entre sí (quedan en unidades no comparables). Con una fila acá para
    (producto, unidad), esa conversión a Kg se hace sola de los dos lados
    en "Vincular por bloques" y "Pendientes por producto" (ver
    cuenta_corriente_productos.views._total_movimiento_en_kg /
    _total_renglon_en_kg).

    Pantalla de alta/listado/editar en "Cuenta corriente de productos" >
    "Equivalencias de unidades" (agregada 30/09/2026 a pedido de Gastón,
    para que él mismo pueda cargar/editar estos casos sin tener que pedir
    un cambio de código cada vez que aparece un producto nuevo con este
    problema). Caso real que motivó esto: producto YERBA MATE 'LA HUELLA'
    4X2Kg (id 1088), entidad Don Basilio (movimiento en Bolsa). Ampliado el
    mismo día tras otro caso real con el mismo producto, entidad Purralef
    Alonso Enrique: acá era el RENGLÓN el que estaba en una unidad
    distinta de Kg ("Unidad"), no el movimiento -- el primer diseño sólo
    convertía el lado del movimiento, asumiendo (incorrectamente) que el
    renglón siempre factura en Kg.
    """
    producto = models.ForeignKey(
        ProductoDetalle,
        on_delete=models.CASCADE,
        related_name='equivalencias_kg',
    )
    unidad = models.ForeignKey(
        ComprobanteUnidadDeMedida,
        on_delete=models.CASCADE,
        related_name='equivalencias_kg',
        verbose_name='Unidad (no Kg)',
    )
    factor_kg = models.DecimalField(
        max_digits=12, decimal_places=4,
        verbose_name='Kg por unidad',
        help_text='Cuántos Kg equivale 1 unidad de esta unidad de medida para este producto (ej.: 8 si 1 Bolsa son 8kg).',
    )
    guardado_el = models.DateTimeField(auto_now_add=True)
    modificado_el = models.DateTimeField(auto_now=True, verbose_name='fecha de edición')

    class Meta:
        verbose_name = 'equivalencia de unidad a Kg'
        verbose_name_plural = 'equivalencias de unidades a Kg'
        db_table = 'cta_cte_producto_equivalencia_kg'
        constraints = [
            models.UniqueConstraint(fields=['producto', 'unidad'], name='cta_cte_producto_unidad_equivalencia_unica'),
        ]
        ordering = ['producto__nombre', 'unidad__nombre']

    def __str__(self):
        return f'{self.producto} -- 1 {self.unidad} = {self.factor_kg} Kg'
