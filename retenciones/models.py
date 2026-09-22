# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from entidades.models import Entidad
from comprobantes.models import Comprobante

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
    # Campo legacy: un solo impuesto relacionado. Se deja tal cual a nivel
    # de base de datos (no se borra ni se sincroniza automáticamente) por si
    # algún reporte u otra parte del sistema todavía lo lee, pero para
    # cargar/mostrar los impuestos vinculados a un régimen hay que usar el
    # campo `impuestos` (M2M) de más abajo, que permite más de uno.
    impuesto = models.ForeignKey(RetencionTipoImpuesto, models.DO_NOTHING, db_column='id_impuesto', blank=True, null=True)
    nombre = models.CharField(max_length=445, blank=True, null=True)
    # Impuestos vinculados a este régimen (M2M real, a través de
    # RetencionRegimenImpuesto). Un régimen como "Régimen de Retención y
    # Percepción Aplicable" puede aplicar a varios impuestos a la vez (IIBB
    # Corrientes, IIBB de otra jurisdicción, etc.), por eso ya no alcanza
    # con el FK simple `impuesto` de arriba.
    impuestos = models.ManyToManyField(
        RetencionTipoImpuesto,
        through='RetencionRegimenImpuesto',
        related_name='regimenes',
        blank=True,
    )

    class Meta:
        managed = False
        db_table = 'retencion_tipo_regimen'

    def __str__(self):
        return f'Id: {self.id} - {self.nombre}'


class RetencionRegimenImpuesto(models.Model):
    """Tabla de vínculo Régimen<->Impuesto. A diferencia de los demás
    modelos de este archivo, esta tabla es NUEVA (no espeja nada de la
    base legacy 'fontana'), así que va con managed=True: alcanza con correr
    `makemigrations`/`migrate` de forma normal, sin necesidad de SQL a
    mano ni de tocar la base a mano."""
    regimen = models.ForeignKey(RetencionTipoRegimen, on_delete=models.CASCADE, related_name='vinculos_impuesto')
    impuesto = models.ForeignKey(RetencionTipoImpuesto, on_delete=models.CASCADE, related_name='vinculos_regimen')

    class Meta:
        db_table = 'retencion_regimen_impuesto'
        constraints = [
            models.UniqueConstraint(fields=['regimen', 'impuesto'], name='unico_regimen_impuesto'),
        ]

    def __str__(self):
        return f'Régimen {self.regimen_id} <-> Impuesto {self.impuesto_id}'


class RetencionRenglon(models.Model):
    """Vincula una Retencion (el comprobante/certificado de retención
    completo -- una fila de `retencion`) con los Comprobante REALES sobre
    los que se practicó, uno por cada operación incluida en ese
    certificado.

    A diferencia de los campos sueltos que se tipeaban antes en el propio
    formulario de renglón (tipo_comp_origen, comprobante_origen, etc., que
    siguen existiendo en el modelo `Retencion` por compatibilidad pero ya
    no se completan para retenciones nuevas), acá el vínculo a Comprobante
    es real (FK): los datos de tipo/fecha/número del comprobante se leen
    directo del comprobante vinculado, no se duplican.

    Una Retencion puede no tener NINGÚN renglón acá -- es un caso válido
    (comportamiento histórico, de antes de que existiera este vínculo).

    Tabla NUEVA (no espeja nada de la base legacy 'fontana'), así que va
    con managed=True: alcanza con correr `makemigrations`/`migrate` de
    forma normal, sin necesidad de SQL a mano."""
    retencion = models.ForeignKey(Retencion, on_delete=models.CASCADE, related_name='renglones')
    comprobante = models.ForeignKey(Comprobante, on_delete=models.CASCADE, related_name='retencion_renglones')
    # Copia de retencion.id_impuesto/id_regimen al momento de guardar (ver
    # save() más abajo) -- se duplican acá (aunque ya están en la Retencion
    # header) para poder poner una restricción real de "no repetir la misma
    # retención (mismo impuesto+régimen) para el mismo comprobante", sin
    # depender de un JOIN. Gastón confirmó (22/09/2026) que un mismo
    # comprobante NUNCA debería recibir el mismo impuesto+régimen dos veces,
    # ni dentro del mismo certificado ni en certificados distintos.
    id_impuesto = models.ForeignKey(
        RetencionTipoImpuesto, on_delete=models.PROTECT, db_column='id_impuesto', related_name='+',
    )
    id_regimen = models.ForeignKey(
        RetencionTipoRegimen, on_delete=models.PROTECT, db_column='id_regimen', related_name='+',
    )
    # Base sobre la que se calculó la retención para este comprobante
    # puntual -- se precarga con el neto_gravado del comprobante elegido,
    # pero queda editable a mano (mismo criterio que ya existía para el
    # campo "Importe" del renglón viejo).
    neto_gravado = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    porcentaje = models.FloatField(blank=True, null=True)
    total = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'retencion_renglon'
        constraints = [
            models.UniqueConstraint(fields=['retencion', 'comprobante'], name='unico_retencion_comprobante'),
            models.UniqueConstraint(
                fields=['comprobante', 'id_impuesto', 'id_regimen'],
                name='unico_comprobante_impuesto_regimen',
            ),
        ]

    def save(self, *args, **kwargs):
        # id_impuesto/id_regimen siempre reflejan los de la Retencion header
        # a la que pertenece este renglón -- se sincronizan solos para que
        # nunca queden desactualizados si algo cambia el impuesto/régimen
        # de la Retencion después de creado el renglón.
        if self.retencion_id and (self.retencion.id_impuesto_id or self.retencion.id_regimen_id):
            self.id_impuesto_id = self.retencion.id_impuesto_id
            self.id_regimen_id = self.retencion.id_regimen_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Retención {self.retencion_id} - Comprobante {self.comprobante_id}'
