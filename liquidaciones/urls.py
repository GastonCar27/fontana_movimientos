from django.urls import path

from . import views

app_name = 'liquidaciones'

urlpatterns = [
    path('', views.liquidacion_list, name='listado'),
    path('alta/', views.liquidacion_form, name='alta'),
    path('<int:pk>/editar/', views.liquidacion_form, name='editar'),
    path('<int:pk>/eliminar/', views.liquidacion_eliminar, name='eliminar'),
    path('<int:pk>/pdf/', views.liquidacion_pdf, name='pdf'),
    path('<int:pk>/excel/', views.liquidacion_excel, name='excel'),
    path('reporte/', views.liquidacion_reporte, name='reporte'),
    path('ranking-entidades/', views.liquidacion_ranking_entidades, name='ranking_entidades'),
    path('ranking-entidades/excel/', views.liquidacion_ranking_entidades_excel, name='ranking_entidades_excel'),
    path('ranking-entidades/pdf/', views.liquidacion_ranking_entidades_pdf, name='ranking_entidades_pdf'),
    path('entidad-buscar/', views.entidad_buscar, name='entidad_buscar'),
    path('item-sin-liquidar-buscar/', views.item_sin_liquidar_buscar, name='item_sin_liquidar_buscar'),
    path('diferencias/', views.liquidacion_diferencias, name='diferencias'),
    path('<int:pk>/recalcular/', views.liquidacion_recalcular, name='recalcular'),

    # --- Sin liquidar (listados filtrables por Entidad / fecha desde-hasta) ---
    path('sin-liquidar/comprobantes/', views.sin_liquidar_comprobantes, name='sin_liquidar_comprobantes'),
    path('sin-liquidar/movimientos-caja/', views.sin_liquidar_movimientos_caja, name='sin_liquidar_movimientos_caja'),
    path('sin-liquidar/retenciones/', views.sin_liquidar_retenciones, name='sin_liquidar_retenciones'),
    path('sin-liquidar/retenciones-inym/', views.sin_liquidar_retenciones_inym, name='sin_liquidar_retenciones_inym'),
    path('sin-liquidar/<str:tipo>/excel/', views.sin_liquidar_excel, name='sin_liquidar_excel'),
    path('sin-liquidar/<str:tipo>/pdf/', views.sin_liquidar_pdf, name='sin_liquidar_pdf'),
]