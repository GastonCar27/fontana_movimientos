from django.contrib import admin

from .models import SolicitudCompra, SolicitudCompraRenglon, SolicitudCompraRenglonComprobanteRenglon


class SolicitudCompraRenglonInline(admin.TabularInline):
    model = SolicitudCompraRenglon
    extra = 1


@admin.register(SolicitudCompra)
class SolicitudCompraAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'numero', 'fecha', 'entidad', 'solicitante', 'responsable_retiro', 'estado',
        'creado_por', 'creado', 'modificado',
    )
    list_filter = ('estado',)
    search_fields = ('numero', 'entidad__nombre')
    readonly_fields = ('creado', 'modificado', 'creado_por')
    inlines = [SolicitudCompraRenglonInline]


@admin.register(SolicitudCompraRenglonComprobanteRenglon)
class SolicitudCompraRenglonComprobanteRenglonAdmin(admin.ModelAdmin):
    list_display = ('id', 'solicitud_renglon', 'comprobante_renglon', 'creado')
