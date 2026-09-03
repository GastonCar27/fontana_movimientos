# retenciones/admin.py
from django.contrib import admin
from liquidaciones.admin_filters import SinLiquidacionFilterBase
from .models import Retencion, RetencionTipoRegimen,RetencionTipoImpuesto


class SinLiquidacionFilter(SinLiquidacionFilterBase):
    related_field = 'liquidaciones'


@admin.register(Retencion)
class RetencionAdmin(admin.ModelAdmin):
    list_filter = (SinLiquidacionFilter,)
    # resto de tu configuración (list_display, search_fields, etc.)



admin.site.register(RetencionTipoImpuesto)
admin.site.register(RetencionTipoRegimen)




# Register your models here.
