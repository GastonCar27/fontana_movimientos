from django.contrib import admin
from .models import Inym_Operador
from .models import Entidad

admin.site.register(Inym_Operador)

# Register your models here.


#buscador entidad
@admin.register(Entidad)
class EntidadAdmin(admin.ModelAdmin):
    # Agrega o edita esta línea con los campos reales de Entidad
    search_fields = ('nombre', 'cuit') 
    list_display = ('id', 'nombre')
