from django.contrib import admin
from .models import Caja, LibroCaja, LibroMovim, MovimientoCaja,MovimientoCajaEmisor,MovimientoCajaConcepto,MovimientoCajaNumero,MovimientoCajaDiferido
from django import forms
from liquidaciones.admin_filters import SinLiquidacionFilterBase
#para buscar entidad

class SinLiquidacionFilter(SinLiquidacionFilterBase):
    related_field = 'liquidaciones'  # related_name que pusiste en LiquidacionMovimiento.movimiento_caja

@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero', 'nombre')


@admin.register(LibroCaja)
class LibroCajaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'caja', 'saldo_inicial', 'fecha_creacion')
    list_filter = ('caja',)


@admin.register(LibroMovim)
class LibroMovimAdmin(admin.ModelAdmin):
    list_display = ('movimiento_caja__id', 'movimiento_caja__receptor', 'movimiento_caja__monto', 'libro', 'hoja', 'renglon')
    list_filter = ('libro__caja', 'libro','hoja')
    ordering = ('movimiento_caja__id',)

    fields = (
        'ver_id_movimiento',
        'ver_fecha_emision',
        'ver_receptor',
        'ver_numero',
        'ver_monto',
        'libro',
        'hoja',
        'renglon',
    )

    readonly_fields = (
        'ver_id_movimiento',
        'ver_receptor',
        'ver_monto',
        'ver_numero',
        'ver_fecha_emision',
    )



    @admin.display(description='ID Movimiento')
    def ver_id_movimiento(self, obj):
        return obj.movimiento_caja_id if obj and obj.movimiento_caja_id else "S/A"

    @admin.display(description='Receptor')
    def ver_receptor(self, obj):
        try:
            if obj and obj.movimiento_caja and obj.movimiento_caja.receptor:
                return obj.movimiento_caja.receptor.nombre
        except Exception:
            pass
        return "S/A"

    @admin.display(description='Monto')
    def ver_monto(self, obj):
        try:
            if obj and obj.movimiento_caja:
                return obj.movimiento_caja.monto
        except Exception:
            pass
        return "-"

    @admin.display(description='Número')
    def ver_numero(self, obj):
        try:
            if obj and obj.movimiento_caja:
                return getattr(obj.movimiento_caja, 'numero', 'S/A')
        except Exception:
            pass
        return "S/A"

    @admin.display(description='Fecha de emisión')
    def ver_fecha_emision(self, obj):
        try:
            if obj and obj.movimiento_caja:
                return getattr(obj.movimiento_caja, 'emision', 'S/A')
        except Exception:
            pass
        return "S/A"
# --- 1. FORMULARIO INLINE LIMPIO ---
class LibroMovimInlineForm(forms.ModelForm):
    class Meta:
        model = LibroMovim
        fields = ('libro', 'hoja', 'renglon')  # Solo los campos reales que se guardan en la base de datos

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Por defecto, cargamos todos los libros para que nunca aparezca vacío
        self.fields['libro'].queryset = LibroCaja.objects.all()

        # 2. Si ya existe una relación o movimiento cargado, filtramos por la caja correspondiente
        if self.instance and self.instance.pk:
            try:
                if hasattr(self.instance, 'movimiento_caja') and self.instance.movimiento_caja:
                    caja_id = self.instance.movimiento_caja.caja_id
                    if caja_id:
                        self.fields['libro'].queryset = LibroCaja.objects.filter(caja_id=caja_id)
            except Exception:
                pass


# --- 2. CLASE INLINE CON MÉTODOS SEGUROS DE SOLO LECTURA ---
class LibroMovimInline(admin.StackedInline):
    model = LibroMovim
    form = LibroMovimInlineForm
    extra = 0
    max_num = 1
    can_delete = True
    
    # Aquí listamos los métodos informativos de abajo y los campos editables
    fields = (
        'ver_id_movimiento', 
        'ver_receptor', 
        'ver_monto', 
        'ver_numero', 
        'libro', 
        'hoja', 
        'renglon'
    )
    
    # Apuntan exactamente a los métodos declarados abajo en esta misma clase
    readonly_fields = (
        'ver_id_movimiento', 
        'ver_receptor', 
        'ver_monto', 
        'ver_numero'
    )

    # --- MÉTODOS INFORMATIVOS (Ahora sí son atributos/métodos de la clase Inline) ---
    @admin.display(description='ID Movimiento')
    def ver_id_movimiento(self, obj):
        return obj.movimiento_caja_id if obj and obj.movimiento_caja_id else "S/A"

    @admin.display(description='Receptor')
    def ver_receptor(self, obj):
        try:
            if obj and obj.movimiento_caja and obj.movimiento_caja.receptor:
                return obj.movimiento_caja.receptor.nombre
        except Exception:
            pass
        return "S/A"

    @admin.display(description='Monto')
    def ver_monto(self, obj):
        try:
            if obj and obj.movimiento_caja:
                return obj.movimiento_caja.monto
        except Exception:
            pass
        return "-"

    @admin.display(description='Número')
    def ver_numero(self, obj):
        try:
            if obj and obj.movimiento_caja:
                return getattr(obj.movimiento_caja, 'numero', 'S/A')
        except Exception:
            pass
        return "S/A"    
# --- 2. INLINE PARA EL EMISOR (Con buscador de Entidades) ---
class MovimientoCajaEmisorInline(admin.StackedInline):
    model = MovimientoCajaEmisor
    extra = 0
    max_num = 1
    can_delete = True
    # Habilita el autocompletado para buscar la entidad emisora
    autocomplete_fields = ('id_entidad',)


# --- 3. INLINE PARA EL CONCEPTO (Opcional) ---
class MovimientoCajaConceptoInline(admin.StackedInline):
    model = MovimientoCajaConcepto
    extra = 0
    max_num = 1
    can_delete = True


# --- 4. INLINE PARA EL NÚMERO (Opcional) ---
class MovimientoCajaNumeroInline(admin.StackedInline):
    model = MovimientoCajaNumero
    extra = 0
    max_num = 1
    can_delete = True

# --- 5. INLINE PARA EL DIFERIDO (Opcional) ---
class MovimientoCajaDiferidoInline(admin.StackedInline):
    model = MovimientoCajaDiferido
    extra = 0
    max_num = 1
    can_delete = True

# --- CONFIGURACIÓN PRINCIPAL DE MOVIMIENTO CAJA ---
@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = ('id', 'caja', 'monto', 'receptor')
    list_filter = ('caja', 'tipo',SinLiquidacionFilter,)
    
    # Autocompletado para el receptor principal del movimiento
    autocomplete_fields = ('receptor',)
    
    # Integramos todos los inlines en la misma pantalla de edición
    inlines = [
        MovimientoCajaEmisorInline,
        MovimientoCajaConceptoInline,
        MovimientoCajaNumeroInline,
        MovimientoCajaDiferidoInline,
        LibroMovimInline,
    ]

    class Media:
        js = ('js/filtrar_libros_por_caja.js',)