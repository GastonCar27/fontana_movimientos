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
    # Pedido de Gastón (24/09/2026): hasta 6 decimales -- hay tarifas reales
    # como 129,856600. La columna real en MySQL (managed=False) también hay
    # que ampliarla a mano, ver
    # sql/2026-09-24_ampliar_decimales_tarifa_retencion_inym.sql (primero en
    # la base de pruebas, después en producción -- mismo criterio que
    # id_certificado_inym más abajo). Sin correr ese script, MySQL sigue
    # redondeando a 2 decimales al guardar aunque el ORM ya declare 6 acá.
    tarifa = models.DecimalField(max_digits=20, decimal_places=6, blank=True, null=True)
    agregado_desde = models.CharField(max_length=45, blank=True, null=True)
    # N° de certificado de INYM (columna IDCERTIFICADO del Excel de importación).
    # OJO: NO es único por sí solo -- INYM lo numera por separado para cada
    # id_tipo_tarifa (por eso puede haber un certificado #32 de "Hoja verde" Y
    # un certificado #32 de "Hoja verde y yerba mate canchada"). La clave real
    # de no-duplicado al importar es (id_certificado_inym, id_tipo_tarifa).
    # Se agregó el 2026-09-15 junto con el importador de Excel de INYM; ver
    # retenciones_inym/importador.py y sql/2026-09-15_agregar_id_certificado_inym.sql
    # (esta tabla es managed=False, así que la migración de Django solo
    # actualiza el estado del ORM -- la columna real hay que crearla a mano
    # con ese script en cada base, primero en la de pruebas y después en
    # producción).
    id_certificado_inym = models.IntegerField(blank=True, null=True)
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

    def __str__(self):
        # Pedido de Gastón (24/09/2026): en el <select> de "Tipo de tarifa"
        # de retencion_inym_form.html (alta Y modificación comparten el
        # mismo template/form) faltaba este __str__, así que el ModelChoiceField
        # mostraba el string genérico de Django ("InymRetencionTipo object
        # (N)") en vez del nombre real de cada tipo de tarifa.
        return self.nombre or f'Tipo de tarifa {self.id}'


class RetencionInymHistorico(models.Model):
    """Tabla histórica, independiente de la operativa `retencion_inym` --
    pedido de Gastón (24/09/2026). Quiere poder importar el Excel completo
    (o un tramo grande) de INYM, con fecha desde/hasta, para armar un
    análisis estadístico de kgs por tipo de tarifa/año/mes -- SIN afectar
    el flujo operativo de liquidaciones, que sigue usando únicamente
    `retencion_inym` (cargada a demanda, retención por retención, a medida
    que se van liquidando).

    A diferencia de `RetencionInym` y el resto de las tablas de este app,
    ÉSTA es managed=True (tabla nueva, no una que ya existía en la base de
    Fontana) -- Gastón corre `makemigrations`/`migrate` él mismo, mismo
    criterio que las demás tablas nuevas de este proyecto.

    Guarda filas CRUDAS (una por retención del Excel, sin agregar), para
    poder rearmar cualquier análisis después sin reimportar. El importador
    (ver importador_historico.py):
      - Exige fecha desde/hasta (no se puede cargar "todo" sin querer).
      - Descarta las filas con `eliminacion` cargada en el Excel
        (retenciones anuladas del lado de INYM) -- pedido de Gastón,
        24/09/2026 ("Para esto no tomar en cuenta retenciones eliminadas").
      - Es idempotente por RANGO DE FECHA (no por certificado como el
        importador operativo): reimportar borra primero lo que ya había
        acá para ese mismo rango [fecha_desde, fecha_hasta] y vuelve a
        insertar desde cero. No hace falta un diff campo a campo como en
        el importador operativo porque acá no hay carga manual que
        proteger -- es de solo lectura para análisis.
    """
    fecha = models.DateField()
    periodo = models.DateField(blank=True, null=True)
    id_tipo_tarifa = models.ForeignKey(
        InymRetencionTipo, on_delete=models.PROTECT, db_column='id_tipo_tarifa',
    )
    operador_emisor = models.ForeignKey(
        Inym_Operador, on_delete=models.PROTECT, db_column='id_operador_emisor',
        related_name='retencion_inym_historico_emisor_set', blank=True, null=True,
    )
    operador_retenido = models.ForeignKey(
        Inym_Operador, on_delete=models.PROTECT, db_column='id_operador_retenido',
        related_name='retencion_inym_historico_retenido_set', blank=True, null=True,
    )
    kgs = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    tarifa = models.DecimalField(max_digits=20, decimal_places=6, blank=True, null=True)
    total = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    # N° de certificado INYM tal cual viene del Excel -- solo informativo acá
    # (no es clave de no-duplicado, ver criterio de idempotencia arriba).
    id_certificado_inym = models.IntegerField(blank=True, null=True)
    fecha_importacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'retencion_inym_historico'
        indexes = [
            models.Index(fields=['fecha']),
            models.Index(fields=['id_tipo_tarifa', 'fecha']),
        ]

    def __str__(self):
        return f'Histórico {self.id} - {self.fecha} - {self.id_tipo_tarifa}'
