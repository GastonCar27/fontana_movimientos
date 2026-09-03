from django.contrib import admin

from .models import Empleado


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    search_fields = ('nombre', 'apellido', 'documento')
    list_display = ('id', 'apellido', 'nombre', 'documento', 'activo')
    list_filter = ('activo',)
