from django.db import models

# Catálogos "tipo" que ya existen como tabla en la base de datos pero que,
# a diferencia de sector_tipo / comprobante_tipo / etc., no tenían todavía
# ningún modelo Django que los representara (no aparecen como Foreign Key
# de ningún otro modelo ya definido en el resto de las apps, así que no
# tienen una app "dueña" natural). Viven acá, en la app tipos, junto con
# el resto del motor genérico de alta/modificación/listado.


class ProductoTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'producto_tipo'

    def __str__(self):
        return f'{self.id} - {self.nombre}'


class CuentaTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=245, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cuenta_tipo'

    def __str__(self):
        return f'{self.id} - {self.nombre}'


class BancoCuentaTipoProducto(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'banco_cuenta_tipo_producto'

    def __str__(self):
        return f'{self.id} - {self.nombre}'
