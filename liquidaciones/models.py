from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Sum, Case, When, F, Value, DecimalField
from django.db.models.functions import Coalesce, Cast
from entidades.models import Entidad
from comprobantes.models import Comprobante
from retenciones.models import Retencion
from retenciones_inym.models import RetencionInym, subquery_no_aplicado
from movimientos_caja.models import MovimientoCaja

# Mismo valor y mismo patrón (constante local por app) que ya usan
# retenciones, movimientos_caja, remitos, comprobantes, etc.
ENTIDAD_PROPIA_ID = 100


def es_nota_de_credito(nombre_tipo):
    """True si el nombre del tipo de comprobante es una Nota de Crédito
    (con o sin tilde, sin importar mayúsculas). Mismo criterio que el
    filtro SQL `tipo_comprobante__nombre__icontains='nota de credito'`
    (la collation de MySQL ignora tildes)."""
    import unicodedata
    texto = unicodedata.normalize('NFKD', nombre_tipo or '')
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch)).lower()
    return 'nota de credito' in texto


# Regla de signo de las Notas de Crédito en una liquidación (unificada el
# 02/10/2026, pedido de Gastón: el listado mostraba distinto saldo que la
# pantalla de edición cuando había una NC en Haber). El 'total' de un
# Comprobante se guarda siempre en positivo; una NC siempre REDUCE el saldo
# (Debe - Haber), esté del lado que esté:
#   * NC en DEBE  -> resta del Debe (se toma en negativo).
#   * NC en HABER -> suma al Haber (en positivo, como un pago).
# Antes, recalcular_totales/Diferencias la tomaban en negativo en los DOS
# lados (en Haber eso la hacía AUMENTAR el saldo), y la pantalla de edición
# y el PDF/Excel nunca le cambiaban el signo. Ahora todos usan esta regla.


class Liquidacion(models.Model):
    # Pago: nosotros le pagamos a la entidad (proveedor) -- comportamiento
    # histórico, el único que existía antes de septiembre de 2026. Cobro:
    # la entidad (cliente) nos paga a nosotros -- para vincular un recibo
    # con la factura que nosotros le emitimos. Determina qué comprobantes/
    # movimientos ofrece _armar_items() (ver liquidaciones/views.py) y qué
    # textos usan la pantalla y las exportaciones (ver liquidaciones/
    # documentos.py): "Comprobantes a Pagar"/"Pago" vs "Comprobantes a
    # Cobrar"/"Cobro". Una vez creada la liquidación, el tipo no se cambia
    # (los ítems ya vinculados quedarían inconsistentes).
    TIPO_PAGO = 'pago'
    TIPO_COBRO = 'cobro'
    TIPO_CHOICES = [(TIPO_PAGO, 'Pago (nosotros pagamos)'), (TIPO_COBRO, 'Cobro (nos pagan)')]

    id = models.IntegerField(primary_key=True)
    numero = models.CharField(max_length=145, blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    entidad = models.ForeignKey(Entidad, models.DO_NOTHING, db_column='id_entidad')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default=TIPO_PAGO)
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
        # - Notas de Crédito: ver la regla de signo arriba de la clase
        #   (es_nota_de_credito): en DEBE se toman en negativo, en HABER en
        #   positivo. Mismo criterio en liquidacion_diferencias, el form
        #   de alta/edición (JS) y el PDF/Excel.
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
                        tipo='debe',
                        comprobante__tipo_comprobante__nombre__icontains='nota de credito',
                        then=-F('comprobante__total') * factor_cambio,
                    ),
                    default=F('comprobante__total') * factor_cambio,
                    output_field=DecimalField(max_digits=20, decimal_places=4),
                ),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            )
        )

        # Movimientos de caja: un cheque depositado o una transferencia
        # recibida a favor de Fontana puede estar guardado en NEGATIVO por
        # la convención del libro de banco (ahí negativo = a favor
        # nuestro), pero acá hay que sumarlo en positivo -- mismo criterio
        # que MovimientoCaja.necesita_invertir_signo_liquidacion
        # (movimientos_caja/models.py), llevado a SQL porque acá se suma
        # con Sum() en la base. Se invierte cuando (1) el receptor es la
        # propia Fontana y (2) el monto está guardado en negativo -- por
        # construcción esto nunca puede afectar una liquidación de PAGO,
        # donde el receptor siempre es la otra entidad (ver _armar_items en
        # liquidaciones/views.py). NO se exige además que el movimiento ya
        # tenga asignado un libro de banco (hoja/renglón) -- se sacó esa
        # condición el 23/09/2026 porque con datos reales (e-cheqs de
        # Gastón) un movimiento puede estar en negativo sin tener todavía
        # ese asiento formal cargado, y esa condición de más hacía que
        # nunca se corrigiera. No cambia el monto guardado en la base
        # (pedido de Gastón, 23/09/2026).
        movimientos_qs = self.movimientos.annotate(
            monto_para_liquidacion=Case(
                When(
                    movimiento_caja__receptor_id=ENTIDAD_PROPIA_ID,
                    movimiento_caja__monto__lt=0,
                    then=-F('movimiento_caja__monto'),
                ),
                default=F('movimiento_caja__monto'),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            )
        )

        # (related_manager, campo_monto_del_item_relacionado)
        fuentes = [
            (movimientos_qs, 'monto_para_liquidacion'),
            (comprobantes_qs, 'monto_convertido'),
            (self.retenciones.all(), 'retencion__total'),
            # Retenciones INYM: NETO de certificados de no aplicación
            # (02/10/2026): total bruto - lo descontado con certificados.
            (
                self.retenciones_inym.annotate(
                    monto_neto=Coalesce(
                        F('retencion_inym__total'), Value(Decimal('0')),
                        output_field=DecimalField(max_digits=20, decimal_places=2),
                    ) - subquery_no_aplicado('retencion_inym_id'),
                ),
                'monto_neto',
            ),
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

    # --- Liquidaciones provisorias / englobadas (pedido de Gastón,
    # 02/10/2026; ver LiquidacionProvisoria más abajo) ---

    @property
    def info_provisoria(self):
        """El registro LiquidacionProvisoria de esta liquidación, o None si
        no es provisoria."""
        try:
            return self.provisoria
        except ObjectDoesNotExist:
            return None

    @property
    def es_provisoria(self):
        return self.info_provisoria is not None

    @property
    def englobada_en(self):
        """Liquidación definitiva en la que quedó englobada (o None)."""
        info = self.info_provisoria
        return info.englobada_en if info is not None else None

    def liquidaciones_englobadas(self):
        """Liquidaciones provisorias englobadas en ésta (queryset)."""
        return Liquidacion.objects.filter(provisoria__englobada_en=self).select_related('entidad').order_by('fecha', 'id')

    @property
    def saldo_englobadas(self):
        """Suma de las diferencias (debe - haber) de las provisorias
        englobadas en ésta."""
        total = Decimal('0')
        for liq in self.liquidaciones_englobadas():
            total += liq.diferencia
        return total

    @property
    def saldo_consolidado(self):
        """Diferencia propia + diferencias de todas las provisorias
        englobadas. Es el saldo "real" de la definitiva: si da 0, el grupo
        quedó cerrado. NO se guarda en debe/haber (esos siguen siendo sólo
        los ítems propios, para que reportes y rankings no sumen dos veces
        lo mismo)."""
        return self.diferencia + self.saldo_englobadas


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


class LiquidacionProvisoria(models.Model):
    """Marca una liquidación como PROVISORIA y, más adelante, en qué
    liquidación definitiva quedó ENGLOBADA (pedido de Gastón, 02/10/2026).

    Caso de uso: en los cobros de yerba canchada el cliente descuenta una
    retención provisoria (anticipo de la retención INYM oficial que hace a
    fin de mes). Cada cobro del mes se liquida como siempre pero tildado
    "Provisoria": queda con saldo, sin cargar ninguna retención inventada.
    Cuando llega lo que cierra el mes (la retención oficial, un pago),
    se arma una liquidación definitiva con esos ítems y se le
    agregan las provisorias: el saldo consolidado (propio + el de las
    englobadas) debería dar 0.

    * Una fila por liquidación provisoria (OneToOne). Si no hay fila, la
      liquidación es normal.
    * englobada_en NULL = provisoria pendiente; con valor = ya englobada.
    * Sólo se pueden englobar provisorias de la MISMA entidad y el MISMO tipo
      (cobro/pago) que la definitiva; una definitiva no puede ser a su
      vez provisoria (no hay cadenas).
    * No toca la tabla legacy 'liquidacion' ni los ítems de ninguna
      liquidación: las provisorias conservan sus comprobantes/
      movimientos, que siguen contando como liquidados.

    Tabla nueva, managed=True (python manage.py migrate liquidaciones).
    Sin FK real en la base (db_constraint=False) para no depender del
    tipo exacto de la columna legacy liquidacion.id -- mismo criterio que
    comprobantes.ComprobanteNoRecibido."""
    id = models.AutoField(primary_key=True)
    liquidacion = models.OneToOneField(
        Liquidacion,
        models.DO_NOTHING,
        db_column='id_liquidacion',
        db_constraint=False,
        related_name='provisoria',
    )
    englobada_en = models.ForeignKey(
        Liquidacion,
        models.DO_NOTHING,
        db_column='id_liquidacion_definitiva',
        db_constraint=False,
        blank=True,
        null=True,
        related_name='provisorias_englobadas',
    )
    fecha_marcada = models.DateTimeField(auto_now_add=True)
    fecha_englobada = models.DateTimeField(blank=True, null=True)
    usuario = models.CharField(max_length=150, blank=True, default='')

    class Meta:
        managed = True
        db_table = 'liquidacion_provisoria'

    def __str__(self):
        estado = f'englobada en {self.englobada_en_id}' if self.englobada_en_id else 'pendiente'
        return f'Provisoria {self.liquidacion_id} ({estado})'
