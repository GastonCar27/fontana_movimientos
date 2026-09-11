# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from entidades.models import Entidad
from django.core.exceptions import ValidationError


class BancoCuentaTipoMovim(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'bancocuenta_tipomovim'

    def __str__(self):
        return f"{self.id} - {self.nombre}"

class Caja(models.Model):
    id = models.IntegerField(primary_key=True)
    numero = models.FloatField(blank=True, null=True)
    nombre = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'bancocuenta'

    def __str__(self):
        return f"{self.id} - {self.nombre}"


class LibroCaja(models.Model):
    id = models.IntegerField(primary_key=True)
    caja = models.ForeignKey(Caja,on_delete=models.PROTECT, db_column='id_bancocuenta', blank=False, null=False)
    nombre = models.CharField(max_length=45, blank=True, null=True)
    saldo_inicial = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    # Fecha de creación del libro: se completa sola a partir de ahora
    # (auto_now_add) para cualquier libro nuevo. Para los libros que ya
    # existían al agregar este campo, se completó una única vez con un
    # comando de gestión (backfill_fecha_creacion_libros) usando la fecha
    # de emisión del movimiento más viejo cargado en cada uno; puede quedar
    # en null si ese libro no tiene ningún movimiento cargado.
    fecha_creacion = models.DateField(blank=True, null=True, auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'banco_cuenta_libro'

    def __str__(self):
        return f"{self.id} - {self.nombre}"




class MovimientoCaja(models.Model):
    id = models.IntegerField(primary_key=True, blank=True) #Blank True pq si no lo agrego, me lo agrega el save con max id
    caja = models.ForeignKey(
        Caja,
          models.DO_NOTHING,
            db_column='idBancoCuenta',
              blank=False,
                null=False
                )  # Field name made lowercase.
    emision = models.DateField(blank=True, null=True)
    monto = models.DecimalField(max_digits=20, decimal_places=2, blank=False, null=False)
    tipo = models.ForeignKey(
        BancoCuentaTipoMovim,
        on_delete=models.PROTECT,  # Evita borrar tipos usados
        related_name="movimiento_caja_tipo",
        db_column="id_tipoMov",
    )
    receptor = models.ForeignKey(
    Entidad,
    models.DO_NOTHING,
    db_column='id_entidad',
    related_name='receptor_movimiento_caja',
    null=True,
    blank=True,
    )
    efectivizacion = models.DateField(blank=True, null=True)
    #asiento_contable = models.ForeignKey('AsientoContable', models.DO_NOTHING, db_column='id_asiento_contable', blank=True, null=True)
    
    @property
    def numero(self):
        # Intentamos obtener el número desde la relación cacheada en memoria (si se usa select_related)
        try:
            if hasattr(self, 'rel_numero') and self.rel_numero is not None:
                return self.rel_numero.numero
        except Exception:
            pass
        
        # Si no está en memoria, recién ahí consultamos la base de datos de forma segura
        numero_val = MovimientoCajaNumero.objects.filter(pk=self.pk).values_list('numero', flat=True).first()
        return numero_val if numero_val is not None else None
    
    @property
    def concepto(self):
        """
        Permite acceder directamente al nombre del concepto o al objeto concepto.
        Retorna la instancia de MovimientoCajaConceptoTipo si existe, o None si no.
        """
        relacion = getattr(self, 'rel_concepto', None)
        return relacion.concepto_tipo if relacion else None

    @property
    def emisor(self):
        """
        Retorna la entidad emisora asociada o la entidad por defecto (id=100).
        """
        try:
            if self.emisor_relacion and self.emisor_relacion.id_entidad:
                return self.emisor_relacion.id_entidad
        except (MovimientoCajaEmisor.DoesNotExist, AttributeError):
            pass
        
        # .first() devuelve la instancia de la Entidad o None si no existe el ID 100
        entidad_defecto = Entidad.objects.filter(id=100).first()
        return entidad_defecto
    def clean(self):
        super().clean()
        # Validamos el libro a través de la relación 'asiento_libro' (LibroMovim)
        asiento = getattr(self, 'asiento_libro', None)
        if asiento and self.caja_id:
            # Traemos directamente el id de la caja del libro usando _id
            libro_caja_id = LibroCaja.objects.filter(pk=asiento.libro_id).values_list('caja_id', flat=True).first()
            
            # Comparamos únicamente los números de ID (enteros)
            if libro_caja_id and libro_caja_id != self.caja_id:
                raise ValidationError({
                    'caja': f"El libro asignado no pertenece a la caja seleccionada."
                })
    def save(self, *args, **kwargs):
        if not self.id:
            ultimo_id = MovimientoCaja.objects.aggregate(
                models.Max('id')
            )['id__max'] or 0
            self.id = ultimo_id + 1

        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        managed = False
        db_table = 'movimiento_caja'
    """
    def __str__(self):
        nombre_receptor = "S/A"
        try:
            if self.receptor_id and hasattr(self, 'receptor') and self.receptor:
                nombre_receptor = self.receptor.nombre
        except Exception:
            pass
        return f"Id:{self.id} Emisión:{self.emision or 'S/A'} Receptor: {nombre_receptor} Monto:{self.monto}"
    """
class LibroMovim(models.Model):
   # La PK de esta tabla es al mismo tiempo la FK que apunta a movimiento_caja
    movimiento_caja = models.OneToOneField(
        MovimientoCaja,
        on_delete=models.CASCADE,
        db_column='id',             # <--- Su propia PK conecta con el id de movimiento_caja
        primary_key=True,           # <--- Indicar que es la PK de bancocuentalibro_movim
        related_name='asiento_libro'
    )
    
    libro = models.ForeignKey(
        LibroCaja, 
        on_delete=models.PROTECT, 
        db_column='id_libro',       # <--- Apunta a la FK id_libro
        verbose_name="Libro de Caja"
    )

    
    
    hoja = models.IntegerField(null=True, blank=True, verbose_name="Número de Hoja")
    renglon = models.IntegerField(null=True, blank=True, verbose_name="Número de Renglón")

    class Meta:
        db_table = 'bancocuentalibro_movim'

    def __str__(self):
        return f"Asiento Libro: {self.libro.nombre} (Hoja: {self.hoja or 'S/A'})"

    

class MovimientoCajaBancoCuentaEntidad(models.Model):
    id = models.OneToOneField(MovimientoCaja, models.DO_NOTHING, db_column='id', primary_key=True)
    numero_cuenta_entidad_destino = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'movimiento_caja_banco_cuenta_entidad'

class BancoSucursal(models.Model):
    id = models.IntegerField(primary_key=True)
    id_banco = models.IntegerField(blank=True, null=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)
    codigo = models.CharField(max_length=3, blank=True, null=True)
    id_ciudad = models.IntegerField(blank=True, null=True)
    direccion = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'banco_sucursal'

class BancoCuentaTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'banco_cuenta_tipo'


class ProductoTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'producto_tipo'

    def __str__(self):
        return f'{self.id} - {self.nombre}'


class BancoCuentaEntidad(models.Model):
    id = models.IntegerField(primary_key=True)
    sucursal = models.ForeignKey(BancoSucursal, models.DO_NOTHING, db_column='id_sucursal', blank=True, null=True)
    cuenta_tipo = models.ForeignKey(BancoCuentaTipo, models.DO_NOTHING, db_column='id_cuenta_tipo', blank=False, null=False)
    producto_tipo = models.ForeignKey(
        ProductoTipo,
        models.DO_NOTHING,
        db_column='id_producto_tipo',
        blank=True,
        null=True,
        related_name='cuentas_bancarias',
    )
    entidad = models.ForeignKey(Entidad, models.DO_NOTHING, db_column='id_entidad', blank=True, null=True)
    cbu = models.CharField(max_length=30, blank=True, null=True)
    numero = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'banco_cuenta_entidad'



class MovimientoCajaDiferido(models.Model):
    id = models.OneToOneField(MovimientoCaja, models.DO_NOTHING, db_column='id', primary_key=True)
    diferido = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'movimiento_caja_diferido'


class MovimientoCajaEmisor(models.Model):
    # El id es FK a MovimientoCaja y funciona como PK
    id = models.OneToOneField(
        MovimientoCaja,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='id',
        related_name='emisor_relacion'
    )
    # Relación con la tabla Entidad (puede ser nula)
    id_entidad = models.ForeignKey(
        Entidad,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_entidad',
        related_name='movimiento_caja_emisor'
    )

    class Meta:
        db_table = 'movimiento_caja_emisor'


class MovimientoCajaNumero(models.Model):
    # Al definir primary_key=True, Django usa este campo como PK 
    # y como Foreign Key hacia MovimientoCaja al mismo tiempo (sin crear una columna 'id' extra).
    movimiento_caja = models.OneToOneField(
        MovimientoCaja,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='rel_numero',
        db_column='id'
    )
    numero = models.IntegerField()
    #numero = models.IntegerField(unique=True) saque esto para permitir que el numero se repita
    class Meta:
        db_table = 'movimiento_caja_numero'







class AsientoContable(models.Model):
    id = models.IntegerField(primary_key=True)
    detalle = models.CharField(max_length=245, blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    id_cuenta_contable = models.IntegerField(blank=True, null=True)
    acumulador = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    importe = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    es_debe = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'asiento_contable'



class MovimientoCajaConceptoTipo(models.Model):
    id = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=145, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'movimiento_caja_concepto_tipo'
    def __str__(self):
        return f"{self.id} - {self.nombre}"

        
class MovimientoCajaConcepto(models.Model):
    # 'primary_key=True' indica que este campo es la PK de la tabla.
    # 'db_column="id"' le dice a Django que la columna física en la DB se llama 'id'.
    movimiento_caja = models.OneToOneField(
        MovimientoCaja,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='id',  # <--- Mapea con el nombre exacto de la columna en tu SQL
        related_name='rel_concepto'
    )
    
    # Suponiendo que la FK al tipo de concepto en SQL se llame id_concepto:
    concepto_tipo = models.ForeignKey(
        MovimientoCajaConceptoTipo,
        on_delete=models.PROTECT,
        db_column='id_concepto',  # <--- Especifica también el nombre si en SQL se llama 'id_concepto'
        related_name='movimiento_caja_concepto'
    )
    class Meta:
        db_table = 'movimiento_caja_concepto'

    def __str__(self):
        return f"Movimiento #{self.movimiento_caja_id} -> Concepto: {self.concepto_tipo.nombre}"





