from django.db import models

# Create your models here.


class Rol(models.Model):
    """"Tipo de entidad" (Transportista, Chofer de Transporte, Productor de
    H.V. de Té, etc.). El nombre del modelo/tabla (Rol / rol_entidad) es
    histórico; de cara al usuario se lo llama "tipo de entidad". Una
    Entidad puede tener más de un tipo (ver el M2M 'entidades' de acá
    abajo, con related_name='roles' -> entidad.roles.all())."""
    nombre = models.CharField(max_length=100, blank=True, null=True)
    slug = models.SlugField(editable=False,blank=True, null=True)
    # M2M declarado acá (en Rol, managed=True) y no en Entidad (managed=False,
    # tabla legada) para que Django pueda crear/migrar la tabla intermedia
    # sin problema. related_name='roles' habilita entidad.roles.all() /
    # Entidad.objects.filter(roles__nombre=...).
    entidades = models.ManyToManyField('Entidad', related_name='roles', blank=True)
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
    # Agregado por migración (ver 0004_entidad_activo): por ahora todas las
    # entidades ya cargadas quedan en True (default de la columna en la
    # base). No se borra ninguna entidad: para "darla de baja" se la marca
    # activo=False.
    activo = models.BooleanField(default=True)

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


