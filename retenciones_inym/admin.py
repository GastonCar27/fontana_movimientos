from django.contrib import admin
from liquidaciones.admin_filters import SinLiquidacionFilterBase
from .models import RetencionInym


class SinLiquidacionFilter(SinLiquidacionFilterBase):
    related_field = 'liquidaciones'  # related_name que pusiste en LiquidacionRetencionInym.retencion_inym


@admin.register(RetencionInym)
class RetencionInymAdmin(admin.ModelAdmin):
    list_filter = (SinLiquidacionFilter,)
    # resto de tu configuración (list_display, search_fields, etc.)

from .models import CertificadoNoAplicacionInym, RetencionInymNoAplicacionVinculo  # noqa: E402


@admin.register(CertificadoNoAplicacionInym)
class CertificadoNoAplicacionInymAdmin(admin.ModelAdmin):
    list_display = ('numero', 'fecha', 'periodo', 'total', 'nombre_valida', 'fecha_validacion', 'fecha_eliminacion')
    search_fields = ('numero', 'nombre_valida')


@admin.register(RetencionInymNoAplicacionVinculo)
class RetencionInymNoAplicacionVinculoAdmin(admin.ModelAdmin):
    list_display = ('retencion_id', 'certificado', 'importe', 'agregado_desde', 'fecha_agregado')
