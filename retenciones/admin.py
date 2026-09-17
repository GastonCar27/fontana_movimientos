# retenciones/admin.py
from django.contrib import admin
from liquidaciones.admin_filters import SinLiquidacionFilterBase
from .models import Retencion, RetencionTipoRegimen,RetencionTipoImpuesto


class SinLiquidacionFilter(SinLiquidacionFilterBase):
    related_field = 'liquidaciones'


@admin.register(Retencion)
class RetencionAdmin(admin.ModelAdmin):
    list_display = ('id', 'año', 'numero', 'es_emisor', 'entidad', 'total')
    list_filter = (SinLiquidacionFilter, 'es_emisor')
    # resto de tu configuración (search_fields, etc.)



admin.site.register(RetencionTipoImpuesto)
admin.site.register(RetencionTipoRegimen)




# Register your models here.
