from django.urls import path

from . import views

app_name = 'remitos'

urlpatterns = [
    # --- Alta / Modificar / Reportes de Remito ---
    path('alta/', views.remito_form, name='remito_alta'),
    path('modificar/', views.remito_listado, name='remito_modificar'),
    path('reportes/', views.remito_reporte, name='remito_reportes'),
    path('reportes/excel/', views.remito_reporte_excel, name='remito_reporte_excel'),
    path('reportes/pdf/', views.remito_reporte_pdf, name='remito_reporte_pdf'),
    path('<int:pk>/editar/', views.remito_form, name='remito_editar'),
    path('<int:pk>/eliminar/', views.remito_eliminar, name='remito_eliminar'),
    path('<int:pk>/imprimir/pdf/', views.remito_imprimir_pdf, name='remito_imprimir_pdf'),
    path('<int:pk>/imprimir/excel/', views.remito_imprimir_excel, name='remito_imprimir_excel'),
    path('entidad-buscar/', views.remito_entidad_buscar, name='entidad_buscar'),

    # --- Alta / Modificar / Reportes de RemitoRenglon ---
    path('renglon/alta/', views.remito_renglon_form, name='remito_renglon_alta'),
    path('renglon/modificar/', views.remito_renglon_listado, name='remito_renglon_modificar'),
    path('renglon/<int:pk>/editar/', views.remito_renglon_form, name='remito_renglon_editar'),
    path('renglon/<int:pk>/eliminar/', views.remito_renglon_eliminar, name='remito_renglon_eliminar'),
    path('renglon/remito-buscar/', views.remito_renglon_remito_buscar, name='remito_renglon_remito_buscar'),

    # --- Catálogo: Vehículo ---
    path('vehiculo/alta/', views.vehiculo_alta, name='vehiculo_alta'),
    path('vehiculo/listado/', views.vehiculo_listado, name='vehiculo_listado'),
    path('vehiculo/<int:pk>/editar/', views.vehiculo_editar, name='vehiculo_editar'),
    path('vehiculo/buscar/', views.vehiculo_buscar, name='vehiculo_buscar'),
    path('vehiculo/crear-rapido/', views.vehiculo_crear_rapido, name='vehiculo_crear_rapido'),

    # --- Catálogo: Acoplado ---
    path('acoplado/alta/', views.acoplado_alta, name='acoplado_alta'),
    path('acoplado/listado/', views.acoplado_listado, name='acoplado_listado'),
    path('acoplado/<int:pk>/editar/', views.acoplado_editar, name='acoplado_editar'),
    path('acoplado/buscar/', views.acoplado_buscar, name='acoplado_buscar'),
    path('acoplado/crear-rapido/', views.acoplado_crear_rapido, name='acoplado_crear_rapido'),

    # --- Catálogo: Condición de venta ---
    path('condicion-venta/alta/', views.condicion_venta_alta, name='condicion_venta_alta'),
    path('condicion-venta/listado/', views.condicion_venta_listado, name='condicion_venta_listado'),
    path('condicion-venta/<int:pk>/editar/', views.condicion_venta_editar, name='condicion_venta_editar'),

    # --- Catálogo: Observación estándar ---
    path('observacion/alta/', views.observacion_alta, name='observacion_alta'),
    path('observacion/listado/', views.observacion_listado, name='observacion_listado'),
    path('observacion/<int:pk>/editar/', views.observacion_editar, name='observacion_editar'),
]
