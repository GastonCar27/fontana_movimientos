from django.contrib import admin

from .models import (
    ComprobanteRenglonMovimiento,
    EstadoCuentaMovimiento,
    LiquidacionProducto,
    LiquidacionProductoComprobanteRenglon,
)


class LiquidacionProductoComprobanteRenglonInline(admin.TabularInline):
    model = LiquidacionProductoComprobanteRenglon
    extra = 0


@admin.register(LiquidacionProducto)
class LiquidacionProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero', 'fecha', 'entidad', 'producto', 'debe_pesos', 'haber_pesos')
    list_filter = ('producto',)
    search_fields = ('numero', 'entidad__nombre')
    inlines = [LiquidacionProductoComprobanteRenglonInline]


@admin.register(EstadoCuentaMovimiento)
class EstadoCuentaMovimientoAdmin(admin.ModelAdmin):
    list_display = ('movimiento', 'estado', 'cerrado_el')
    list_filter = ('estado',)
    search_fields = ('movimiento__id_movimiento',)


@admin.register(ComprobanteRenglonMovimiento)
class ComprobanteRenglonMovimientoAdmin(admin.ModelAdmin):
    list_display = ('id', 'renglon', 'movimiento', 'guardado_el')
    search_fields = ('renglon__id', 'movimiento__id_movimiento')
