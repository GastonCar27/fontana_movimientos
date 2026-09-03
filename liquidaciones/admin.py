from django.contrib import admin
from django.db.models import F, DecimalField
from django.db.models.functions import Coalesce
from .models import (
    Liquidacion,
    LiquidacionComprobante,
    LiquidacionRetencion,
    LiquidacionRetencionInym,
    LiquidacionMovimiento,
)


@admin.register(Liquidacion)
class LiquidacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero', 'fecha', 'entidad', 'debe', 'haber', 'saldo')
    list_filter = ('entidad',)
    search_fields = ('numero',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _saldo=Coalesce(F('debe'), 0, output_field=DecimalField()) -
                   Coalesce(F('haber'), 0, output_field=DecimalField())
        )

    @admin.display(description='Saldo', ordering='_saldo')
    def saldo(self, obj):
        return obj._saldo


@admin.register(LiquidacionComprobante)
class LiquidacionComprobanteAdmin(admin.ModelAdmin):
    list_display = ('id', 'liquidacion', 'comprobante', 'tipo')
    list_filter = ('tipo',)


@admin.register(LiquidacionRetencion)
class LiquidacionRetencionAdmin(admin.ModelAdmin):
    list_display = ('id', 'liquidacion', 'retencion', 'tipo')
    list_filter = ('tipo',)


@admin.register(LiquidacionRetencionInym)
class LiquidacionRetencionInymAdmin(admin.ModelAdmin):
    list_display = ('id', 'liquidacion', 'retencion_inym', 'tipo')
    list_filter = ('tipo',)


@admin.register(LiquidacionMovimiento)
class LiquidacionMovimientoAdmin(admin.ModelAdmin):
    list_display = ('id', 'liquidacion', 'movimiento_caja', 'tipo')
    list_filter = ('tipo',)
# Register your models here.
