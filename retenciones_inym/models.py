from decimal import Decimal

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
    # operador_emisor pasó a ser obligatorio (25/09/2026, pedido de Gastón --
    # caso real: la entidad 12650 tenía un certificado con este campo vacío,
    # que quedaba "pendiente de liquidar" en el listado general pero nunca
    # se podía ofrecer en el alta de liquidación, ver
    # liquidaciones/views.py::_armar_items). Ya no alcanza con exigirlo sólo
    # en RetencionInymForm: acá se refleja también en el modelo para que
    # quede obligatorio en cualquier ModelForm (por ejemplo el admin de
    # Django, que antes lo dejaba pasar vacío igual). Como esta tabla es
    # managed=False, este cambio sólo actualiza el estado del ORM -- la
    # restricción real en MySQL hay que agregarla a mano con
    # sql/2026-09-25_operador_emisor_not_null_retencion_inym.sql, y ANTES de
    # correr ese script hay que completar (con
    # `python manage.py auditar_operador_emisor_vacio`) cualquier fila vieja
    # que todavía lo tenga vacío -- si no, el ALTER TABLE va a fallar.
    operador_emisor = models.ForeignKey(Inym_Operador, models.DO_NOTHING, db_column='id_operador_emisor')
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
    # Pedido de Gastón (28/09/2026): fecha en que se cargó cada retención al
    # sistema y fecha del último cambio -- para poder ver de un vistazo hace
    # cuánto se agregó/tocó una fila, cosa que hoy no se podía saber (sólo
    # existía `agregado_desde`, que dice DESDE DÓNDE se cargó, no CUÁNDO).
    # auto_now_add/auto_now los completa Django solo, en cualquier .save()
    # hecho por el ORM (alta manual, importador de Excel, el histórico, y
    # también los comandos de corrección de este app) -- no hace falta
    # tocarlos a mano en ningún lado. Igual que id_certificado_inym, esta
    # tabla es managed=False: la migración de Django sólo actualiza el
    # estado del ORM, la columna real hay que agregarla a mano con
    # sql/2026-09-28_agregar_fechas_retencion_inym.sql (primero en la base
    # de pruebas si la hubiera, después en producción). Las filas ya
    # existentes van a quedar con estos dos campos en NULL (no hay forma de
    # reconstruir esa fecha para datos viejos) -- sólo las filas nuevas y
    # las que se vuelvan a guardar de acá en más van a tener el dato.
    #
    # OJO -- auto_now sólo actualiza el campo cuando el `save()` que hace
    # Django lo incluye: si algún código llama `.save(update_fields=[...])`
    # sin incluir 'fecha_modificado' en esa lista, el campo NO se actualiza
    # esa vez (es el caso, hoy, de los comandos de corrección de este app,
    # que usan update_fields para tocar un solo campo puntual a propósito).
    fecha_agregado = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    fecha_modificado = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'retencion_inym'

    def __str__(self):
        return f'Id.:{self.id} {self.fecha} Receptor:{self.operador_retenido} $:{self.total}'

    # --- Certificados de no aplicación (02/10/2026, pedido de Gastón) ---
    # 'total' es el importe BRUTO de la retención (kgs x tarifa, columna
    # IMPORTE del Excel de INYM). Si la retención tiene vinculado uno o más
    # certificados de no aplicación (RetencionInymNoAplicacionVinculo, columna
    # IMPORTE_NO_RETENIDO del Excel), lo realmente retenido es
    # total - importe no aplicado. Liquidaciones usa SIEMPRE el neto.

    @property
    def importe_no_aplicado(self):
        return sum((v.importe or Decimal('0') for v in self.no_aplicaciones.all()), Decimal('0'))

    @property
    def importe_neto(self):
        return (self.total or Decimal('0')) - self.importe_no_aplicado

    @property
    def certificados_no_aplicacion_texto(self):
        return ', '.join(str(v.certificado.numero) for v in self.no_aplicaciones.all())


def subquery_no_aplicado(campo_id_retencion):
    """Expresión SQL con la suma de lo no aplicado (certificados de no
    aplicación) de la retención INYM cuyo id está en `campo_id_retencion`
    (un OuterRef: ej. 'retencion_inym_id' desde LiquidacionRetencionInym, o
    'pk' desde RetencionInym). 0 si no tiene ninguno."""
    from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
    from django.db.models.functions import Coalesce
    dec = DecimalField(max_digits=20, decimal_places=2)
    return Coalesce(
        Subquery(
            RetencionInymNoAplicacionVinculo.objects
            .filter(retencion_id=OuterRef(campo_id_retencion))
            .order_by()
            .values('retencion_id')
            .annotate(s=Sum('importe'))
            .values('s'),
            output_field=dec,
        ),
        Value(Decimal('0')),
        output_field=dec,
    )


# RetencionInymNoAplicacion (tabla legacy `retencion_inym_no_aplicacion`) se
# sacó el 02/10/2026: la reemplazan CertificadoNoAplicacionInym y
# RetencionInymNoAplicacionVinculo (más abajo). La migración 0006 borra la
# tabla de la base SÓLO si está vacía y nada la referencia.


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


# ---------------------------------------------------------------------------
# Certificados de no aplicación de INYM (pedido de Gastón, 02/10/2026).
#
# Fontana (operador 181, secadero) emite certificados de no aplicación
# (hasta ahora casi siempre por "STOCK INICIAL - CAMBIO TARIFA"); el
# operador que nos retiene (ej. Establecimiento Las Marías) los "valida" y
# por ese importe NO nos retiene. En el Excel de retenciones INYM la
# retención trae IMPORTE (bruto) + IDCERT_NO_APLICACION + IMPORTE_NO_RETENIDO:
# lo realmente retenido es IMPORTE - IMPORTE_NO_RETENIDO.
#
# Tablas nuevas, managed=True (python manage.py migrate retenciones_inym).
# Reemplaza a la tabla legacy `retencion_inym_no_aplicacion` (ver migración
# 0006, que la borra si está vacía y sin vínculos).
# ---------------------------------------------------------------------------

class CertificadoNoAplicacionInym(models.Model):
    """Un certificado de no aplicación de INYM. Se crea solo al importar el
    Excel de retenciones (con lo que trae esa planilla: número e importe
    aplicado), y se completa/actualiza al importar el listado de
    certificados que se exporta desde INYM ("Listado Cert. de No
    Aplicación": fecha, período, vencimiento, total, quién lo validó...)."""
    id = models.AutoField(primary_key=True)
    numero = models.IntegerField(unique=True)  # IDCERT_NO_APLICACION de INYM
    id_operador_emisor = models.IntegerField(blank=True, null=True)  # IDOPERADOR (181 = Fontana secadero)
    cuit_emisor = models.CharField(max_length=20, blank=True, default='')
    tipo_oper_emisor = models.CharField(max_length=100, blank=True, default='')
    fecha = models.DateField(blank=True, null=True)
    periodo = models.DateField(blank=True, null=True)
    vencimiento = models.DateField(blank=True, null=True)
    total = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    # Tipo / tarifa / kgs: hoy el listado de INYM no los trae; quedan para
    # cargarlos si más adelante vienen en otra planilla.
    tipo = models.CharField(max_length=150, blank=True, default='')
    tarifa = models.DecimalField(max_digits=20, decimal_places=6, blank=True, null=True)
    kgs = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    # Operador que lo validó (el que nos retuvo y descontó el certificado).
    id_operador_valida = models.IntegerField(blank=True, null=True)
    tipo_oper_valida = models.CharField(max_length=100, blank=True, default='')
    nombre_valida = models.CharField(max_length=200, blank=True, default='')
    fecha_validacion = models.DateField(blank=True, null=True)
    fecha_eliminacion = models.DateField(blank=True, null=True)
    agregado_desde = models.CharField(max_length=45, blank=True, default='')
    fecha_agregado = models.DateTimeField(auto_now_add=True)
    fecha_modificado = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'certificado_no_aplicacion_inym'
        ordering = ['-fecha', '-numero']

    def __str__(self):
        return f'Cert. no aplicación N° {self.numero}'

    @property
    def importe_aplicado(self):
        return sum((v.importe or Decimal('0') for v in self.aplicaciones.all()), Decimal('0'))

    @property
    def saldo(self):
        if self.total is None:
            return None
        return self.total - self.importe_aplicado


class RetencionInymNoAplicacionVinculo(models.Model):
    """Cuánto de un certificado de no aplicación se descontó en una
    retención INYM (IMPORTE_NO_RETENIDO del Excel de retenciones). Una
    retención puede tener más de un certificado y un certificado puede
    repartirse entre varias retenciones (se controla con el saldo)."""
    id = models.AutoField(primary_key=True)
    retencion = models.ForeignKey(
        RetencionInym, models.DO_NOTHING, db_column='id_retencion_inym',
        db_constraint=False, related_name='no_aplicaciones',
    )
    certificado = models.ForeignKey(
        CertificadoNoAplicacionInym, models.PROTECT, db_column='id_certificado',
        related_name='aplicaciones',
    )
    importe = models.DecimalField(max_digits=20, decimal_places=2)
    agregado_desde = models.CharField(max_length=45, blank=True, default='')
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'retencion_inym_cert_no_aplicacion'
        constraints = [
            models.UniqueConstraint(fields=['retencion', 'certificado'], name='unico_retencion_cert_no_aplicacion'),
        ]

    def __str__(self):
        return f'Ret. INYM {self.retencion_id} - cert. {self.certificado_id}: {self.importe}'
