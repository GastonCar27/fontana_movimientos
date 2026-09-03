from django.db import models
from entidades.models import Entidad
from entidades.models import Inym_Operador
from productos.models import ProductoDetalle
from comprobantes.models import ComprobanteUnidadDeMedida


class Movimiento(models.Model):
    id_movimiento = models.AutoField(primary_key=True)
    producto = models.ForeignKey(ProductoDetalle, models.DO_NOTHING, db_column='id_producto')
    fecha = models.DateField(blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    entidad_emisor = models.ForeignKey(Entidad, models.DO_NOTHING, db_column='id_entidad_emisor',related_name='entidad_emisor_movimiento')
    entidad_receptor = models.ForeignKey(Entidad, models.DO_NOTHING, db_column='id_entidad_receptor',related_name='entidad_receptor')
    numero = models.IntegerField(blank=True, null=True)
    unidad_de_medida = models.ForeignKey(ComprobanteUnidadDeMedida, models.DO_NOTHING, db_column='id_unidad_de_medida', blank=True, null=True)
    guardado_el = models.DateTimeField(auto_now_add=True)
    modificado_el = models.DateTimeField(auto_now=True,verbose_name='fecha de edición',null=True)
    constraints = [
            models.UniqueConstraint(
                fields=['numero', 'producto'], 
                name='unique_numero_producto'
            )
            ]
    class Meta:
        managed = False ##para que cree
        db_table = 'movimiento'
    
    def save(self, *args, **kwargs):
        # Si es un movimiento de hv de yerba mate, la entidad emisora/receptora
        # se deriva del inym_operador_origen/destino recién elegido en el
        # formulario (self ya trae esos valores nuevos en memoria antes de
        # guardar). Antes esto se volvía a leer de la base de datos con
        # MovimientoHvYerbaMate.objects.get(pk=self.pk), lo que traía el
        # operador VIEJO (el que todavía estaba guardado) en vez del que se
        # acababa de seleccionar al modificar, y por eso la entidad mostrada
        # no cambiaba aunque el INYM Operador sí se hubiera actualizado.
        if hasattr(self, 'inym_operador_origen_id') and self.inym_operador_origen_id:
            self.entidad_emisor = self.inym_operador_origen.entidad
        if hasattr(self, 'inym_operador_destino_id') and self.inym_operador_destino_id:
            self.entidad_receptor = self.inym_operador_destino.entidad
        # 2. Se ejecuta el guardado original de Django
        super().save(*args, **kwargs)



class MovimientoPesaje(models.Model):
    movimiento = models.OneToOneField(
        Movimiento,
        on_delete=models.CASCADE,
        primary_key=True,
        parent_link=True, #indica que es la relación con el padre
        related_name= "movimiento_pesaje" 
    )
    bruto = models.FloatField(blank=True, null=True)
    tara = models.FloatField(blank=True, null=True)
    descuento = models.FloatField(blank=True, null=True)
    fecha_ingreso = models.DateField(blank=True, null=True)
    fecha_salida = models.DateField(blank=True, null=True)
    hora_ingreso = models.TimeField(blank=True, null=True)
    hora_salida = models.TimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'movimiento_pesaje'


class MovimientoHvYerbaMate(Movimiento):
    movimiento = models.OneToOneField(
        Movimiento,
        on_delete=models.CASCADE,
        primary_key=True,
        parent_link=True, #indica que es la relación con el padre
    )


    inym_operador_origen = models.ForeignKey(Inym_Operador, models.DO_NOTHING, db_column='id_inym_operador_origen', blank=True, null=True,related_name='inym_operador_origen')
    inym_operador_destino = models.ForeignKey(Inym_Operador, models.DO_NOTHING, db_column='id_inym_operador_destino', blank=True, null=True,related_name='inym_operador_destino')

    class Meta:
        managed = True ##para que cree
        db_table = 'movimiento_hv_yerba_mate'

