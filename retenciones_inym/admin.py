from django.contrib import admin
from liquidaciones.admin_filters import SinLiquidacionFilterBase
from .models import RetencionInym


class SinLiquidacionFilter(SinLiquidacionFilterBase):
    related_field = 'liquidaciones'  # related_name que pusiste en LiquidacionRetencionInym.retencion_inym


@admin.register(RetencionInym)
class RetencionInymAdmin(admin.ModelAdmin):
    list_filter = (SinLiquidacionFilter,)
    # resto de tu configuración (list_display, search_fields, etc.)