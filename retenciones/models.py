# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from entidades.models import Entidad

class Retencion(models.Model):
    # Ver comentario del campo es_emisor más abajo.
    ES_EMISOR = 1
    NO_ES_EMISOR = 0

    id = models.IntegerField(primary_key=True)
    entidad = models.ForeignKey(Entidad, models.DO_NOTHING, db_column='id_entidad', blank=True, null=True)
    entidad_nombre = models.CharField(max_length=345, blank=True, null=True)
    # es_emisor = 1 o vacío (default, comportamiento histórico): Fontana
    # practicó/emitió esta retención -- se la retuvo a 'entidad' al pagarle
    # (por eso el PDF/Excel dice "CONSTANCIA DE RETENCIÓN" y trae firma: es
    # un documento que Fontana emite). es_emisor = 0: 'entidad' le practicó
    # la retención a Fontana al pagarle a Fontana (retención sufrida) -- acá
    # el PDF/Excel es solo un registro interno, no un comprobante que
    # Fontana emite. Mismo criterio y mismos choices que Comprobante.es_emisor
    # (ver comprobantes/models.py), agregado para que liquidaciones pueda
    # ofrecer las retenciones correctas según el tipo (pago/cobro) de cada
    # liquidación -- ver liquidaciones/views.py::_armar_items.
    es_emisor = models.IntegerField(
        blank=False,
        null=True,
        default=1,
        choices=[(1, 'Sí'), (0, 'No')],
    )
    subtotal = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    porcentaje = models.FloatField(blank=True, null=True)
    total = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    comprobante_string = models.CharField(max_length=425, blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    id_impuesto = models.ForeignKey('RetencionTipoImpuesto', models.DO_NOTHING, db_column='id_impuesto', blank=True, null=True)
    id_regimen = models.ForeignKey('RetencionTipoRegimen', models.DO_NOTHING, db_column='id_regimen', blank=True, null=True)
    tipo_comp_origen = models.IntegerField(blank=True, null=True)
    comprobante_origen = models.CharField(max_length=145, blank=True, null=True)
    fecha_comp_origen = models.DateField(blank=True, null=True)
    monto_comp_origen = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    id_condicion = models.IntegerField(blank=True, null=True)
    porcentaje_exclusion = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    tipo_doc_entidad = models.IntegerField(blank=True, null=True)
    id_operacion = models.IntegerField(blank=True, null=True)
    numero_certificado_afip = models.CharField(max_length=45, blank=True, null=True)
    agregado_desde = models.CharField(max_length=145, blank=True, null=True)
    año = models.IntegerField(blank=True, null=True,verbose_name='año')
    numero = models.IntegerField(blank=True, null=True)
    #id_asiento_contable = models.ForeignKey('AsientoContable', models.DO_NOTHING, db_column='id_asiento_contable', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'retencion'

    def __str__(self):
        return f'Id: {self.id} - {self.año}-{self.numero} Entidad: {self.entidad}'

class RetencionTipoImpuesto(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)
    class Meta:
        managed = False
        db_table = 'retencion_tipo_impuesto'
    def __str__(self):
        return f'Id: {self.id} - {self.nombre}'

class RetencionTipoRegimen(models.Model):
    id = models.IntegerField(primary_key=True)
    impuesto = models.ForeignKey(RetencionTipoImpuesto, models.DO_NOTHING, db_column='id_impuesto', blank=True, null=True)
    nombre = models.CharField(max_length=445, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'retencion_tipo_regimen'

    def __str__(self):
        return f'Id: {self.id} - {self.nombre} Impuesto: {self.impuesto}'



