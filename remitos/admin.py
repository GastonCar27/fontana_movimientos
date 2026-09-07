from django.contrib import admin

from .models import Acoplado, CondicionVenta, ObservacionEstandar, Remito, RemitoRenglon, Vehiculo


class RemitoRenglonInline(admin.TabularInline):
    model = RemitoRenglon
    extra = 0


@admin.register(Remito)
class RemitoAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'punto_venta', 'numero', 'fecha', 'emisor', 'receptor')
    list_filter = ('tipo',)
    search_fields = ('numero', 'emisor__nombre', 'receptor__nombre')
    inlines = [RemitoRenglonInline]


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'patente', 'activo')
    search_fields = ('nombre', 'patente')


@admin.register(Acoplado)
class AcopladoAdmin(admin.ModelAdmin):
    list_display = ('id', 'patente', 'activo')
    search_fields = ('patente',)


@admin.register(CondicionVenta)
class CondicionVentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'activa')
    search_fields = ('nombre',)


@admin.register(ObservacionEstandar)
class ObservacionEstandarAdmin(admin.ModelAdmin):
    list_display = ('id', 'texto', 'activa')
    search_fields = ('texto',)
