# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.

from django.db import models
from productos.models import ProductoDetalle
from entidades.models import Entidad

class ComprobanteUnidadDeMedida(models.Model):
    id = models.CharField(primary_key=True, max_length=2)
    nombre = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'comprobante_unidad_de_medida'

    def __str__(self):
        return f'{self.id} - {self.nombre}'


# Ids de esta misma tabla que NO vienen del padrón de AFIP: se agregaron a
# mano (ver migración comprobantes/migrations/0003_seed_unidades_remitos.py)
# para poder usar en Remitos unidades reales del negocio (Bolsón, Bolsa) que
# AFIP no contempla. remitos.models.RemitoRenglon.unidad_de_medida y
# movimientos.models.Movimiento.unidad_de_medida apuntan a esta misma tabla
# (no tienen catálogo propio), así que estas filas quedan disponibles ahí
# sin más cambios. Se excluyen explícitamente del desplegable de
# ComprobanteRenglonDetalleForm (ver comprobantes.forms) para que nunca
# terminen usadas en un comprobante fiscal real -- el día que se conecte el
# webservice de AFIP, esa exclusión sigue siendo necesaria.
IDS_UNIDADES_SOLO_REMITOS = ['BN', 'BS']


class DocumentoTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    tipo = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'documento_tipo'
    def __str__(self):
        return f'{self.id} - {self.tipo}'

class ComprobanteTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)
    id_afip = models.CharField(max_length=45, blank=False, null=True)
    abreviatura = models.CharField(max_length=6, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'comprobante_tipo'

    def __str__(self):
        return f'{self.id} - {self.nombre}'
        
class SectorTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sector_tipo'# This is an auto-generated Django model module.

    def __str__(self):
        return f'{self.id} - {self.nombre}'
    
class IvaTipo(models.Model):
    id_afip = models.IntegerField(blank=True, null=True)
    producto = models.OneToOneField(
        ProductoDetalle,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name= "producto_iva_tipo",
        db_column='id_producto' 
    )

    class Meta:
        managed = False
        db_table = 'iva_tipo'


    


class Comprobante(models.Model):
    id = models.IntegerField(primary_key=True)
    entidad_emisor = models.ForeignKey(Entidad, models.DO_NOTHING, db_column='id_entidad',related_name='entidad_emisor_comprobante')
    tipo_comprobante = models.ForeignKey(ComprobanteTipo, models.DO_NOTHING, db_column='id_tipo_comp', blank=True, null=True)
    tipo_documento_entidad = models.ForeignKey(DocumentoTipo, models.DO_NOTHING, db_column='id_tipo_documento', blank=True, null=True)   
    id_cuenta = models.IntegerField(blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    neto_gravado = models.FloatField(blank=True, null=True)
    recargo = models.FloatField(blank=True, null=True)
    impuesto = models.FloatField(blank=True, null=True)
    total = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    entidad_nombre = models.CharField(max_length=345, blank=True, null=True)
    comprobante_string = models.CharField(max_length=145, blank=True, null=True)
    punto_de_venta = models.IntegerField(blank=True, null=True)
    numero = models.IntegerField(blank=True, null=True)
    otros_tributos = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    exento = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    agregado_desde = models.CharField(max_length=45, blank=True, null=True)
    es_emisor = models.IntegerField(
        blank=False,
        null=True,
        default=1,
        choices=[(1, 'Sí'), (0, 'No')],
    )
    moneda = models.CharField(max_length=4, blank=True, null=True)
    neto_no_gravado = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fecha_contabilizacion = models.DateField(blank=True, null=True)
    iva = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    detalle = models.CharField(max_length=345, blank=True, null=True)
    numero_hasta = models.IntegerField(blank=True, null=True)
    codigo_autorizacion = models.FloatField(blank=True, null=True)
    

    class Meta:
        managed = False
        db_table = 'comprobante'


class ComprobanteTipoDeCambio(models.Model):
    """
    Tipo de cambio de un comprobante en moneda distinta a pesos (PES).
    Relación 1 a 1 con Comprobante: solo existe un registro para los
    comprobantes que están en moneda extranjera.
    """
    comprobante = models.OneToOneField(
        Comprobante,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='tipo_de_cambio',
        db_column='id'
    )
    tipo_de_cambio = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'comprobante_tipo_de_cambio'

    def __str__(self):
        return f'{self.comprobante_id} - {self.tipo_de_cambio}'


class ComprobanteRenglon(models.Model):
    id = models.IntegerField(primary_key=True)
    # ForeignKey (no OneToOneField): un comprobante puede tener varios
    # renglones. En la base 'id_comprobante' es un índice normal, no
    # único; con OneToOneField Django exigía como máximo un renglón por
    # comprobante y rechazaba el alta de un segundo renglón sin avisar
    # (el error de "ya existe" quedaba en un campo oculto).
    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.CASCADE,
        related_name= "renglon_comprobante",
        db_column='id_comprobante'
    )
    producto = models.ForeignKey(ProductoDetalle, models.DO_NOTHING, db_column='id_producto')
    total = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    id_cuenta_contable = models.IntegerField(blank=True, null=True)
    id_asiento_contable = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'comprobante_renglon'

class ComprobanteRenglonDetalle(models.Model):
    comprobante_renglon = models.OneToOneField(
        ComprobanteRenglon,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name= "renglon_detalle_comprobante",
        db_column='id' 
    )
    cantidad = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    unidad_de_medida = models.ForeignKey(ComprobanteUnidadDeMedida, models.DO_NOTHING, db_column='id_unidad_de_medida', blank=True, null=True)
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    bonificacion = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    iva_tipo = models.ForeignKey(
        ProductoDetalle,
        on_delete=models.DO_NOTHING,
        db_column='id_iva_tipo',
        blank=True,
        null=True,
        related_name='renglones_detalle_iva',
    )
    sector_tipo = models.ForeignKey(SectorTipo, models.DO_NOTHING, db_column='id_sector_tipo')

    class Meta:
        managed = False
        db_table = 'comprobante_renglon_detalle'