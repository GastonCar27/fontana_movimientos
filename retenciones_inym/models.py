from django.db import models
from entidades.models import Inym_Operador
# Create your models here.
# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.



class RetencionInym(models.Model):
    id = models.IntegerField(primary_key=True)
    fecha = models.DateField(blank=True, null=True)
    periodo = models.DateField(blank=True, null=True)
    id_tipo_tarifa = models.ForeignKey('InymRetencionTipo', models.DO_NOTHING, db_column='id_tipo_tarifa', blank=True, null=True)
    operador_emisor = models.ForeignKey(Inym_Operador, models.DO_NOTHING, db_column='id_operador_emisor', blank=True, null=True)
    operador_retenido = models.ForeignKey(Inym_Operador, models.DO_NOTHING, db_column='id_operador_retenido', related_name='retencioninym_id_operador_retenido_set', blank=True, null=True)
    kgs = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    total = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    eliminacion = models.DateField(blank=True, null=True)
    tarifa = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    agregado_desde = models.CharField(max_length=45, blank=True, null=True)
    #id_asiento_contable = models.ForeignKey('AsientoContable', models.DO_NOTHING, db_column='id_asiento_contable', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'retencion_inym'

    def __str__(self):
        return f'Id.:{self.id} {self.fecha} Receptor:{self.operador_retenido} $:{self.total}'


class RetencionInymNoAplicacion(models.Model):
    id = models.IntegerField(primary_key=True)
    id_certificado_inym_no_aplicacion = models.IntegerField(blank=True, null=True)
    total = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'retencion_inym_no_aplicacion'


class RetencionInymOrigen(models.Model):
    #no entiendo está tabla, pq no uso el origen de la misma retencion inym
    id = models.IntegerField(primary_key=True)
    ##creo que esta mal el nombre de operador_retenido
    operador_origen = models.ForeignKey(Inym_Operador, models.DO_NOTHING, db_column='id_operador_origen', related_name='retencion_inym_origen_con_entidad', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'retencion_inym_origen'


class InymRetencionTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'inym_retencion_tipo'
