from django.contrib import admin
from .models import (
    Comprobante,
    ComprobanteTipoDeCambio,
    ComprobanteRenglon,
    ComprobanteRenglonDetalle,
)
from liquidaciones.admin_filters import SinLiquidacionFilterBase
# Register your models here.
class SinLiquidacionFilter(SinLiquidacionFilterBase):
    related_field = 'liquidaciones'  # related_name que pusiste en LiquidacionRetencionInym.retencion_inym


class ComprobanteTipoDeCambioInline(admin.StackedInline):
    model = ComprobanteTipoDeCambio
    extra = 0


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_filter = (SinLiquidacionFilter,)
    list_display  = (
        'id',
        'fecha',
        'entidad_emisor',
        'tipo_comprobante',
        'punto_de_venta',
        'numero',
        'total',
        'moneda',
    )
    inlines = (ComprobanteTipoDeCambioInline,)


@admin.register(ComprobanteTipoDeCambio)
class ComprobanteTipoDeCambioAdmin(admin.ModelAdmin):
    list_display = ('comprobante', 'tipo_de_cambio')


class ComprobanteRenglonDetalleInline(admin.StackedInline):
    model = ComprobanteRenglonDetalle
    extra = 0


@admin.register(ComprobanteRenglon)
class ComprobanteRenglonAdmin(admin.ModelAdmin):
    list_display = ('id', 'comprobante', 'producto', 'total', 'id_cuenta_contable', 'id_asiento_contable')
    list_filter = ('producto',)
    search_fields = ('id', 'comprobante__id')
    inlines = (ComprobanteRenglonDetalleInline,)
