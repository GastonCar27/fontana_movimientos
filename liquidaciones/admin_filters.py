# liquidaciones/admin_filters.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class SinLiquidacionFilterBase(admin.SimpleListFilter):
    title = _('liquidación')
    parameter_name = 'sin_liquidacion'
    related_field = 'liquidaciones'  # se sobreescribe si hace falta

    def lookups(self, request, model_admin):
        return (
            ('si', _('Sin liquidación')),
            ('no', _('Con liquidación')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'si':
            return queryset.filter(**{f'{self.related_field}__isnull': True})
        if self.value() == 'no':
            return queryset.filter(**{f'{self.related_field}__isnull': False})
        return queryset