from django.contrib import admin
from .models import Inym_Operador
from .models import Entidad
from .models import Rol

admin.site.register(Inym_Operador)

# Register your models here.


#buscador entidad
@admin.register(Entidad)
class EntidadAdmin(admin.ModelAdmin):
    # Agrega o edita esta línea con los campos reales de Entidad
    search_fields = ('nombre', 'cuit')
    list_display = ('id', 'nombre', 'activo')
    list_filter = ('activo',)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    """"Tipos de entidad" (Transportista, Chofer de Transporte, etc.). Acá
    también se puede asignar/quitar entidades a un tipo (filter_horizontal),
    como alternativa a hacerlo desde el alta de la entidad."""
    search_fields = ('nombre',)
    list_display = ('id', 'nombre')
    filter_horizontal = ('entidades',)
