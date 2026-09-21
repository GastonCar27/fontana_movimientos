import re

from django.conf import settings
from django.db import models
from django.utils import timezone

from entidades.models import Entidad


class SolicitudCompra(models.Model):
    """"Solicitud de entrega": el papel que se le da a un empleado para que
    retire mercadería de un proveedor (entidad). Cada solicitud tiene uno o
    más renglones (SolicitudCompraRenglon) con lo que se va a retirar,
    descripto tal como lo pide quien arma la solicitud — que muchas veces no
    coincide con el nombre exacto con el que el proveedor factura eso mismo
    (ver SolicitudCompraRenglonComprobanteRenglon).

    'solicitante' y 'responsable_retiro' son Entidad (no un modelo Empleado
    aparte): se filtran en el form/buscador por tipo de entidad (Rol) --
    'Autorizado a solicitar' y 'Autorizado a retirar' respectivamente,
    ver ROL_AUTORIZADO_SOLICITAR / ROL_AUTORIZADO_RETIRO acá abajo y
    services/buscadores.py + entidades/migrations/0009_seed_tipos_entidad_empleado.py.
    La categoría 'Empleado' es sólo descriptiva y no habilita por sí sola
    ninguno de estos dos campos."""

    ROL_AUTORIZADO_SOLICITAR = 'Autorizado a solicitar'
    ROL_AUTORIZADO_RETIRO = 'Autorizado a retirar'

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

    numero = models.CharField('Número', max_length=20, unique=True, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    entidad = models.ForeignKey(
        Entidad, on_delete=models.PROTECT, related_name='solicitudes_compra', verbose_name='Proveedor',
    )
    solicitante = models.ForeignKey(
        Entidad, on_delete=models.PROTECT, related_name='solicitudes_como_solicitante',
        verbose_name='Solicitante (autoriza el pedido)',
    )
    responsable_retiro = models.ForeignKey(
        Entidad, on_delete=models.PROTECT, related_name='solicitudes_como_responsable_retiro',
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
        # El form (SolicitudCompraForm) ya viene con el número sugerido
        # precargado (ver siguiente_numero_solicitud más abajo y
        # views.solicitud_form), así que en el uso normal esto casi nunca
        # hace falta -- queda como red de seguridad para que una solicitud
        # nueva nunca se guarde con 'numero' vacío (chocaría con la
        # siguiente, porque el campo es unique=True).
        if self.pk is None and not self.numero:
            self.numero = siguiente_numero_solicitud()
        super().save(*args, **kwargs)


def siguiente_numero_solicitud():
    """Calcula el próximo número correlativo para una solicitud nueva:
    busca el mayor número ya usado -- mirando sólo los dígitos de 'numero',
    para que no importe que las solicitudes anteriores a este cambio hayan
    quedado con el prefijo histórico 'OC-' (ej. 'OC-125') -- y le suma 1.
    Devuelve un string simple, sin prefijo (ej. '126'), que es el formato
    que se usa de acá en adelante; las solicitudes viejas conservan su
    'OC-125' tal cual, no se tocan. Usado tanto para precargar el campo en
    el form (views.solicitud_form) como de red de seguridad en el save()
    de acá arriba."""
    maximo = 0
    for numero in SolicitudCompra.objects.exclude(numero='').values_list('numero', flat=True):
        digitos = re.sub(r'\D', '', numero or '')
        if digitos:
            maximo = max(maximo, int(digitos))
    return str(maximo + 1)


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
    # Estado propio del renglón (independiente del estado general de la
    # solicitud, SolicitudCompra.estado): reutiliza las mismas opciones,
    # porque un renglón puede ir avanzando de a uno (ej. uno ya retirado y
    # otro todavía pendiente dentro de la misma solicitud). El form
    # (form.html) suma además un control para aplicar un mismo estado a
    # todos los renglones de una, como atajo -- no reemplaza poder
    # cambiarlos uno por uno.
    estado = models.CharField(
        'Estado', max_length=12, choices=SolicitudCompra.ESTADO_CHOICES, default=SolicitudCompra.ESTADO_PENDIENTE,
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


class ProductoGenerico(models.Model):
    """Catálogo propio y liviano de descripciones ya usadas en renglones de
    Solicitud de Compra (ej. "gasoil"), para poder reutilizarlas por
    autocompletado en vez de tipearlas de nuevo cada vez -- ver el buscador
    'producto_generico_buscar' en views.py y su uso en form.html.

    A propósito NO es el catálogo formal de productos (productos.ProductoDetalle,
    ligado a lo que se factura/AFIP y usado por comprobantes): acá entra
    cualquier texto "vulgar" que se haya tipeado en una descripción, así que
    mezclarlo con ese catálogo lo ensuciaría. Tampoco tiene relación (FK)
    con SolicitudCompraRenglon.descripcion, que sigue siendo texto libre --
    este catálogo sólo alimenta las sugerencias del buscador, y se completa
    solo (ver _registrar_productos_genericos en views.py) cada vez que se
    guarda una solicitud con una descripción nueva. Arrancó con un backfill
    de las descripciones ya cargadas (ver migración 0006_producto_generico)."""

    nombre = models.CharField(max_length=255, unique=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'solicitud_compra_producto_generico'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


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
