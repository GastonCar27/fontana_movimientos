from django.db import models


class ItemTipo(models.Model):
    """Categoría de un producto/ítem (ej.: Producto, Servicio, etc.)."""
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'item_tipo'

    def __str__(self):
        return f'{self.id} - {self.nombre}'


class ProductoDetalle(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)
    item_tipo = models.ForeignKey(
        ItemTipo,
        models.DO_NOTHING,
        db_column='id_item_tipo',
        blank=True,
        null=True,
        related_name='productos',
    )

    def __str__(self):
        return f'{self.id} - {self.nombre}'

    class Meta:
        managed = False
        db_table = 'producto_detalle'

