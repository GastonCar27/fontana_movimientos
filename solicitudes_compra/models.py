from django.conf import settings
from django.db import models
from django.utils import timezone

from empleados.models import Empleado
from entidades.models import Entidad


class SolicitudCompra(models.Model):
    """"Solicitud de entrega": el papel que se le da a un empleado para que
    retire mercadería de un proveedor (entidad). Cada solicitud tiene uno o
    más renglones (SolicitudCompraRenglon) con lo que se va a retirar,
    descripto tal como lo pide quien arma la solicitud — que muchas veces no
    coincide con el nombre exacto con el que el proveedor factura eso mismo
    (ver SolicitudCompraRenglonComprobanteRenglon)."""

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_RETIRADA = 'retirada'
    ESTADO_FACTURADA = 'facturada'
    ESTADO_CANCELADA = 'cancelada'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_RETIRADA, 'Retirada'),
        (ESTADO_FACTURADA, 'Facturada'),
        (ESTADO_CANCELADA, 'Cancelada'),
    ]

    numero = models.CharField(max_length=20, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    entidad = models.ForeignKey(
        Entidad, on_delete=models.PROTECT, related_name='solicitudes_compra', verbose_name='Proveedor',
    )
    solicitante = models.ForeignKey(
        Empleado, on_delete=models.PROTECT, related_name='solicitudes_como_solicitante',
        verbose_name='Solicitante (autoriza el pedido)',
    )
    responsable_retiro = models.ForeignKey(
        Empleado, on_delete=models.PROTECT, related_name='solicitudes_como_responsable_retiro',
        verbose_name='Autorizado a retirar',
    )
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_compra_creadas', verbose_name='Creado por',
        # No se expone en SolicitudCompraForm: lo completa solo la vista
        # (solicitud_form, en views.py) con request.user al crear la
        # solicitud, tomando el usuario logueado (login de Django). Queda
        # null=True porque las solicitudes cargadas antes de este cambio no
        # tienen ese dato, y por si alguna vez se crea una sin usuario en
        # sesión (no debería pasar, el sitio exige login para todo).
    )

    class Meta:
        db_table = 'solicitud_compra'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return self.numero or f'Solicitud {self.pk}'

    def save(self, *args, **kwargs):
        es_nueva = self.pk is None
        super().save(*args, **kwargs)
        if es_nueva and not self.numero:
            self.numero = f'OC-{self.pk}'
            super().save(update_fields=['numero'])


class SolicitudCompraRenglon(models.Model):
    """Un ítem pedido dentro de una solicitud de compra: cantidad, formato
    (unidad) y descripción tal como se pide (puede ser un nombre "vulgar",
    ej. "gasoil", que después el proveedor factura con otro nombre, ej.
    "X-10"). 'producto_sugerido' es opcional: un puntero de referencia al
    catálogo de productos, por si ya se sabe con qué coincide."""

    PRIORIDAD_URGENTE = 'urgente'
    PRIORIDAD_MEDIA = 'media'
    PRIORIDAD_BAJA = 'baja'
    PRIORIDAD_CHOICES = [
        (PRIORIDAD_URGENTE, 'Urgente'),
        (PRIORIDAD_MEDIA, 'Media'),
        (PRIORIDAD_BAJA, 'Baja'),
    ]

    solicitud = models.ForeignKey(SolicitudCompra, on_delete=models.CASCADE, related_name='renglones')
    cantidad = models.DecimalField(max_digits=12, decimal_places=2)
    unidad_medida = models.CharField('U. de Medida', max_length=45, blank=True, default='Unidad')
    prioridad = models.CharField(
        'Prioridad', max_length=10, choices=PRIORIDAD_CHOICES, default=PRIORIDAD_MEDIA,
    )
    descripcion = models.CharField(max_length=255)
    sector = models.ForeignKey(
        'comprobantes.SectorTipo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='renglones_solicitud_compra',
        verbose_name='Sector',
    )
    producto_sugerido = models.ForeignKey(
        'productos.ProductoDetalle', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='renglones_solicitud_compra',
        verbose_name='Producto de catálogo (si ya se sabe con qué coincide)',
    )

    class Meta:
        db_table = 'solicitud_compra_renglon'
        ordering = ['id']

    def __str__(self):
        return f'{self.cantidad} {self.unidad_medida} {self.descripcion}'.strip()

    @property
    def vinculado(self):
        return self.vinculos.exists()


class SolicitudCompraRenglonComprobanteRenglon(models.Model):
    """Vínculo manual entre un renglón de una solicitud de compra (nombre
    "vulgar", ej. "gasoil") y el renglón real de la factura que después
    llegó (ej. "X-10", tal como lo carga el proveedor), para los casos en
    que el nombre no coincide y no se puede armar un match automático. Se
    permite más de un vínculo por renglón (ej. si se retiró en dos
    facturas distintas)."""

    solicitud_renglon = models.ForeignKey(
        SolicitudCompraRenglon, on_delete=models.CASCADE, related_name='vinculos',
    )
    comprobante_renglon = models.ForeignKey(
        'comprobantes.ComprobanteRenglon', on_delete=models.CASCADE, related_name='vinculos_solicitud_compra',
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'solicitud_compra_renglon_comprobante_renglon'
        constraints = [
            models.UniqueConstraint(
                fields=['solicitud_renglon', 'comprobante_renglon'],
                name='unique_vinculo_solicitud_renglon_comprobante_renglon',
            ),
        ]

    def __str__(self):
        return f'{self.solicitud_renglon_id} <-> renglón de factura {self.comprobante_renglon_id}'
