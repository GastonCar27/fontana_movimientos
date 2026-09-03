from django.urls import path,include
from django.views.generic import RedirectView
from movimientos.views import RecepcionHvYerbaMateListView,MovimientoHvYerbaMateUpdateView,MovimientoHvYerbaMateDetailView
from . import views

app_name = 'movimientos' # para facilitar las rutas puedan repetir el nombre, indica que las rutas pertenecen a la app que esta aca
urlpatterns=[
    path('', views.recepcion, name='recepcion'),

    # --- Alta / Modificación / Reportes de Movimiento (gestión genérica de productos) ---
    path('gestion/alta/', views.movimiento_form, name='movimiento_alta'),
    path('gestion/modificar/', views.movimiento_listado, name='movimiento_modificar'),
    path('gestion/reportes/', views.movimiento_reporte, name='movimiento_reportes'),
    path('gestion/ranking-productores/', views.movimiento_ranking_productores, name='movimiento_ranking_productores'),
    path('gestion/ranking-productores/excel/', views.movimiento_ranking_productores_excel, name='movimiento_ranking_productores_excel'),
    path('gestion/ranking-productores/pdf/', views.movimiento_ranking_productores_pdf, name='movimiento_ranking_productores_pdf'),
    path('gestion/<int:pk>/editar/', views.movimiento_form, name='movimiento_editar'),
    path('gestion/<int:pk>/eliminar/', views.movimiento_eliminar, name='movimiento_eliminar'),

    path('recepcion_hv_yerba_mate', views.recepcion_hv_yerba_mate, name='recepcion_hv_yerba_mate'),
    path('recepcion_hv_yerba_mate/<int:numero_nuevo>/', views.recepcion_hv_yerba_mate, name='recepcion_hv_yerba_mate_nueva'),
    path('listado_recepcion_hv_yerba_mate', RecepcionHvYerbaMateListView.as_view(),name='listado_recepcion_hv_yerba_mate'),
    path('reporte_hv_yerba_mate/', views.reporte_hv_yerba_mate, name='reporte_hv_yerba_mate'),
    path('reporte_hv_yerba_mate/excel/', views.reporte_hv_yerba_mate_excel, name='reporte_hv_yerba_mate_excel'),
    path('reporte_hv_yerba_mate/pdf/', views.reporte_hv_yerba_mate_pdf, name='reporte_hv_yerba_mate_pdf'),
    path('reporte_hv_yerba_mate/excel_yerba/', views.reporte_hv_yerba_mate_excel_yerba, name='reporte_hv_yerba_mate_excel_yerba'),
    # Redirección de la URL vieja (rota) del listado de HV Yerba Mate hacia el nuevo reporte,
    # por si quedó algún link o bookmark guardado apuntando a la ruta anterior.
    path('movimientos_hv_ym_list', RedirectView.as_view(pattern_name='movimientos:reporte_hv_yerba_mate', permanent=False), name='movimientos-hv-yerba-mate-listado'),
    path('listado_movimiento', views.MovimientoSearchListView.as_view(),name='listado_movimiento'),
    path('eliminar', views.remove_movimiento, name='remove'),
    path('buscar-saldo-producto', views.vista_buscar_saldo_producto, name='buscar_saldo_producto_en_comprobantes'),
    path('buscar-saldo-producto_entidad', views.vista_buscar_saldo_producto_entidad, name='buscar_saldo_producto_en_comprobantes_por_entidad'),
    path('salida_canchada', views.salida_yerba_mate_canchada, name='salida_canchada'),
    path('salida', views.salida, name='salida'),
    path('mi_vista_buscar', views.mi_vista_buscar, name='buscar_movimiento_2'),

    path('<pk>', views.MovimientoDetailView.as_view(),name='movimiento'),
    path('movimiento_hv_yerba_mate/<pk>', views.MovimientoHvYerbaMateDetailView.as_view(),name='movimiento-hv-yerba-mate'),
    path('<int:pk>/update/', MovimientoHvYerbaMateUpdateView.as_view() , name='movimiento_update'),
    path('movimiento_hv_yerba_mate/<int:pk>/eliminar/', views.movimiento_hv_yerba_mate_eliminar, name='movimiento_hv_yerba_mate_eliminar'),
    path('exportar_/excel/', views.generar_excel_completo, name='accion_listado_movimiento'),
    path('exportar/excel_agrupado/', views.generar_excel_inym_emisor_agrupado, name='accion_listado_inym_emisor_agrupado'),
  
   
    #path('<int:pk>/update/', views.movimiento_update, name='movimento_update'),

# other patterns…
    #path("select2/", include("django_select2.urls")),
]