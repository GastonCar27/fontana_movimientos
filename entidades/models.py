from django.db import models

# Create your models here.


class Rol(models.Model):
    nombre = models.CharField(max_length=100, blank=True, null=True)
    slug = models.SlugField(editable=False,blank=True, null=True)
    class Meta:
        managed = True #no detecta cambios si esta en falso
        db_table = 'rol_entidad'
        verbose_name_plural = 'roles'

    def __str__(self):
        return f'{self.id} - {self.nombre}'

class Entidad(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=105, blank=True, null=True)
    cuit = models.CharField(max_length=45, blank=True, null=True)
    direccion = models.CharField(max_length=145, blank=True, null=True)
    documento_nro = models.IntegerField(blank=True, null=True)
    codigo = models.IntegerField(blank=True, null=True)
    localidad = models.CharField(max_length=145, blank=True, null=True)
    codpos = models.CharField(max_length=45, blank=True, null=True)
    iva = models.CharField(max_length=45, blank=True, null=True)
    provincia = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'entidad'

    def __str__(self):
        return f'{self.id} - {self.nombre}'


class Inym_Operador_Tipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=105, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'inym_operador_tipo'

    def __str__(self):
        return f'{self.nombre}'


class Inym_Operador(models.Model):
    id = models.IntegerField(primary_key=True)
    entidad = models.ForeignKey(Entidad, models.DO_NOTHING, db_column='id_entidad')
    tipo_operador = models.ForeignKey(Inym_Operador_Tipo, models.DO_NOTHING, db_column='id_operador_tipo')

    class Meta:
        managed = False
        db_table = 'inym_operador'

    def __str__(self):
        return f'{self.entidad.id} - {self.entidad.nombre} Op.Inym: {self.id} - {self.tipo_operador}'


