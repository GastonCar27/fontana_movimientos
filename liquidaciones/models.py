from decimal import Decimal
from django.db import models
from django.db.models import Sum, Case, When, F, Value, DecimalField
from django.db.models.functions import Coalesce, Cast
from entidades.models import Entidad
from comprobantes.models import Comprobante
from retenciones.models import Retencion
from retenciones_inym.models import RetencionInym
from movimientos_caja.models import MovimientoCaja


class Liquidacion(models.Model):
    id = models.IntegerField(primary_key=True)
    numero = models.CharField(max_length=145, blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    entidad = models.ForeignKey(Entidad, models.DO_NOTHING, db_column='id_entidad')
    debe = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    haber = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'liquidacion'

    def recalcular_totales(self, guardar=True):
        """
        Recalcula debe/haber sumando, en la base de datos, los montos de
        todos los ítems vinculados según su tipo ('debe' o 'haber').
        Es la ÚNICA fuente de verdad para este cálculo: la vista de alta/
        edición, el admin, o cualquier script deberían llamar a este método
        en vez de sumar manualmente.
        """
        total_debe = Decimal('0')
        total_haber = Decimal('0')

        # Comprobantes:
        # - en moneda distinta a PES: si el comprobante tiene un registro en
        #   comprobante_tipo_de_cambio, su monto se multiplica por ese tipo
        #   de cambio antes de sumar. Si no tiene (comprobante en pesos), el
        #   factor es 1 y el monto queda igual.
        # - Notas de Crédito: el campo 'total' de Comprobante siempre se
        #   guarda en positivo en la base, así que acá se le aplica el signo
        #   negativo cuando el nombre del tipo de comprobante contiene
        #   "nota de credito" (mismo criterio que liquidacion_diferencias,
        #   para que ambos cálculos den siempre el mismo resultado).
        factor_cambio = Coalesce(
            F('comprobante__tipo_de_cambio__tipo_de_cambio'),
            Value(Decimal('1')),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
        # Nota: multiplicar dos DecimalField en SQL (total * tipo_de_cambio)
        # devuelve un resultado con más decimales de los que declara
        # output_field (Django no lo redondea solo) — hay que forzarlo con
        # Cast(), si no el monto convertido queda con 4+ decimales en vez
        # de 2, y después no coincide con lo guardado en debe/haber.
        comprobantes_qs = self.comprobantes.annotate(
            monto_convertido=Cast(
                Case(
                    When(
                        comprobante__tipo_comprobante__nombre__icontains='nota de credito',
                        then=-F('comprobante__total') * factor_cambio,
                    ),
                    default=F('comprobante__total') * factor_cambio,
                    output_field=DecimalField(max_digits=20, decimal_places=4),
                ),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            )
        )

        # (related_manager, campo_monto_del_item_relacionado)
        fuentes = [
            (self.movimientos.all(), 'movimiento_caja__monto'),
            (comprobantes_qs, 'monto_convertido'),
            (self.retenciones.all(), 'retencion__total'),
            (self.retenciones_inym.all(), 'retencion_inym__total'),
        ]

        for queryset, campo_monto in fuentes:
            agregado = queryset.aggregate(
                debe=Sum(
                    Case(
                        When(tipo='debe', then=F(campo_monto)),
                        default=Value(0),
                        output_field=DecimalField(max_digits=20, decimal_places=2),
                    )
                ),
                haber=Sum(
                    Case(
                        When(tipo='haber', then=F(campo_monto)),
                        default=Value(0),
                        output_field=DecimalField(max_digits=20, decimal_places=2),
                    )
                ),
            )
            total_debe += agregado['debe'] or Decimal('0')
            total_haber += agregado['haber'] or Decimal('0')

        # Redondeo defensivo a 2 decimales en Python, para que lo que se
        # guarda (y lo que devuelve este método) tenga siempre la misma
        # cantidad de decimales que el campo debe/haber en la base.
        self.debe = total_debe.quantize(Decimal('0.01'))
        self.haber = total_haber.quantize(Decimal('0.01'))
        total_debe, total_haber = self.debe, self.haber
        if guardar:
            self.save(update_fields=['debe', 'haber'])
        return total_debe, total_haber

    @property
    def diferencia(self):
        return (self.debe or Decimal('0')) - (self.haber or Decimal('0'))


class LiquidacionComprobante(models.Model):
    comprobante = models.ForeignKey(Comprobante, models.DO_NOTHING, db_column='id_comprobante', related_name='liquidaciones')
    liquidacion = models.ForeignKey(Liquidacion, models.DO_NOTHING, db_column='id_liquidacion', related_name='comprobantes')
    tipo = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'liquidacion_comprobante'


class LiquidacionRetencion(models.Model):
    retencion = models.ForeignKey(Retencion, models.DO_NOTHING, db_column='id_retencion', related_name='liquidaciones')
    liquidacion = models.ForeignKey(Liquidacion, models.DO_NOTHING, db_column='id_liquidacion', related_name='retenciones')
    tipo = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'liquidacion_retencion'


class LiquidacionRetencionInym(models.Model):
    liquidacion = models.ForeignKey(Liquidacion, models.DO_NOTHING, db_column='id_liquidacion', related_name='retenciones_inym')
    retencion_inym = models.ForeignKey(RetencionInym, models.DO_NOTHING, db_column='id_retencion_inym', related_name='liquidaciones')
    tipo = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'liquidacion_retencion_inym'


class LiquidacionMovimiento(models.Model):
    liquidacion = models.ForeignKey(Liquidacion, models.DO_NOTHING, db_column='id_liquidacion', related_name='movimientos')
    movimiento_caja = models.ForeignKey(MovimientoCaja, models.DO_NOTHING, db_column='id_movimiento', related_name='liquidaciones')
    tipo = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'liquidacion_movimiento'