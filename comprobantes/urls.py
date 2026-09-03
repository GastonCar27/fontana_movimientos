from django.urls import path
from . import views
from comprobantes.views import RenglonComprobanteUpdateView
app_name = 'comprobantes' # para facilitar las rutas puedan repetir el nombre, indica que las rutas pertenecen a la app que esta aca
urlpatterns=[
    # --- Alta / Modificar / Reportes de Comprobante ---
    path('alta/', views.comprobante_form, name='comprobante_alta'),
    path('modificar/', views.comprobante_listado, name='comprobante_modificar'),
    path('reportes/', views.comprobante_reporte, name='comprobante_reportes'),
    path('reportes/ranking-entidades/', views.comprobante_ranking_entidades, name='comprobante_ranking_entidades'),
    path(
        'reportes/ranking-entidades/excel/',
        views.comprobante_ranking_entidades_excel,
        name='comprobante_ranking_entidades_excel',
    ),
    path(
        'reportes/ranking-entidades/pdf/',
        views.comprobante_ranking_entidades_pdf,
        name='comprobante_ranking_entidades_pdf',
    ),
    path('<int:pk>/editar/', views.comprobante_form, name='comprobante_editar'),
    path('<int:pk>/eliminar/', views.comprobante_eliminar, name='comprobante_eliminar'),
    path('<int:pk>/exportar/excel/', views.comprobante_exportar_excel, name='comprobante_exportar_excel'),
    path('<int:pk>/exportar/pdf/', views.comprobante_exportar_pdf, name='comprobante_exportar_pdf'),
    path('entidad-buscar/', views.comprobante_entidad_buscar, name='entidad_buscar'),

    # --- Alta / Modificar / Reportes de ComprobanteRenglon ---
    path('renglon/alta/', views.comprobante_renglon_form, name='comprobante_renglon_alta'),
    path('renglon/modificar/', views.comprobante_renglon_listado, name='comprobante_renglon_modificar'),
    path('renglon/reportes/', views.comprobante_renglon_reporte, name='comprobante_renglon_reportes'),
    path('renglon/<int:pk>/editar/', views.comprobante_renglon_form, name='comprobante_renglon_editar'),
    path('renglon/<int:pk>/eliminar/', views.comprobante_renglon_eliminar, name='comprobante_renglon_eliminar'),
    path('renglon/comprobante-buscar/', views.comprobante_renglon_comprobante_buscar, name='comprobante_renglon_comprobante_buscar'),
    path('renglon/producto-buscar/', views.comprobante_renglon_producto_buscar, name='comprobante_renglon_producto_buscar'),
    path('renglon/producto-crear/', views.comprobante_renglon_producto_crear, name='comprobante_renglon_producto_crear'),

    path('buscar_comprobante_renglon', views.buscar_comprobante_renglon_para_movimiento, name='buscar_renglon'),
    path('buscar_comprobante_renglon', views.buscar_comprobante_renglon_para_movimiento, name='buscar_renglon'),
    path('buscar-comprobantes-por-entidad', views.buscar_comprobantes_por_fechas_y_entidad, name='buscar_comprobantes_por_entidad'),
    path('exportar/excel/', views.generar_excel_completo, name='generar_excel_completo'), #ojo que el orden importa, si esta por ultimo no encuentra
    path('<int:pk>/update/', RenglonComprobanteUpdateView.as_view() , name='renglon_comprobante_update'),
    path('eliminar', views.remove_renglon_comprobante, name='renglon_comprobante_remove'),

]