from django.contrib import admin

from .models import BancoCuentaTipoProducto, CuentaTipo, ProductoTipo

admin.site.register(ProductoTipo)
admin.site.register(CuentaTipo)
admin.site.register(BancoCuentaTipoProducto)
