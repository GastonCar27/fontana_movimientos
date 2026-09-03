from django.urls import path

from . import views

app_name = 'productos'

urlpatterns = [
    path('buscar/', views.producto_buscar, name='buscar'),

    # --- Alta / Modificar / Reportes de ProductoDetalle ---
    path('alta/', views.producto_alta, name='producto_alta'),
    path('modificar/', views.producto_listado, name='producto_modificar'),
    path('<int:pk>/editar/', views.producto_editar, name='producto_editar'),
    path('reportes/', views.producto_reporte, name='producto_reportes'),
    path('reportes/excel/', views.producto_reporte_excel, name='producto_reporte_excel'),
    path('reportes/pdf/', views.producto_reporte_pdf, name='producto_reporte_pdf'),
]
