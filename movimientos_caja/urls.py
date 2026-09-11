from django.urls import path

from . import views

app_name = 'movimientos_caja'  # para poder usar {% url 'movimientos_caja:...' %} en los templates

urlpatterns = [
    # --- Alta / Modificación / Reportes de Movimiento de Caja ---
    path('alta/', views.movimiento_caja_form, name='movimiento_caja_alta'),
    path('modificar/', views.movimiento_caja_listado, name='movimiento_caja_modificar'),
    path('reportes/', views.movimiento_caja_reporte, name='movimiento_caja_reportes'),
    path('reportes/excel/', views.movimiento_caja_reporte_excel, name='movimiento_caja_reporte_excel'),
    path('reportes/pdf/', views.movimiento_caja_reporte_pdf, name='movimiento_caja_reporte_pdf'),
    path('reportes/ranking-entidades/', views.movimiento_caja_ranking_entidades, name='movimiento_caja_ranking_entidades'),
    path('reportes/ranking-entidades/excel/', views.movimiento_caja_ranking_entidades_excel, name='movimiento_caja_ranking_entidades_excel'),
    path('reportes/ranking-entidades/pdf/', views.movimiento_caja_ranking_entidades_pdf, name='movimiento_caja_ranking_entidades_pdf'),
    path('reportes/estado-caja/', views.movimiento_caja_estado, name='movimiento_caja_estado'),
    path('reportes/estado-caja/excel/', views.movimiento_caja_estado_excel, name='movimiento_caja_estado_excel'),
    path('reportes/estado-caja/pdf/', views.movimiento_caja_estado_pdf, name='movimiento_caja_estado_pdf'),
    path('<int:pk>/editar/', views.movimiento_caja_form, name='movimiento_caja_editar'),
    path('<int:pk>/eliminar/', views.movimiento_caja_eliminar, name='movimiento_caja_eliminar'),
    # --- Modificar en libro (asignar/editar libro, hoja y renglón) ---
    path('libro/', views.movimiento_caja_libro_listado, name='movimiento_caja_libro_modificar'),
    path('libro/<int:pk>/editar/', views.movimiento_caja_libro_editar, name='movimiento_caja_libro_editar'),
    # --- AJAX: cuentas bancarias de una entidad (para Alta/Modificación) ---
    path(
        'entidad/<int:entidad_id>/cuentas-bancarias/',
        views.movimiento_caja_entidad_cuentas_bancarias,
        name='movimiento_caja_entidad_cuentas_bancarias',
    ),
]
