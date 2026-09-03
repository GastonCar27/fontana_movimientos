from django.urls import path

from . import views

app_name = 'retenciones'

urlpatterns = [
    path('', views.retencion_listado, name='listado'),
    path('alta/', views.retencion_alta, name='alta'),
    path('<int:anio>/<int:numero>/modificar/', views.retencion_modificar, name='modificar'),
    path('<int:anio>/<int:numero>/eliminar/', views.retencion_eliminar, name='eliminar'),
    path('<int:anio>/<int:numero>/pdf/', views.retencion_pdf, name='pdf'),
    path('<int:anio>/<int:numero>/excel/', views.retencion_excel, name='excel'),

    # Ret. Impuestos
    path('tipos/impuestos/', views.retencion_tipo_impuesto_listado, name='tipo_impuesto_listado'),
    path('tipos/impuestos/alta/', views.retencion_tipo_impuesto_alta, name='tipo_impuesto_alta'),
    path('tipos/impuestos/<int:pk>/editar/', views.retencion_tipo_impuesto_modificar, name='tipo_impuesto_modificar'),
    path('tipos/impuestos/<int:pk>/eliminar/', views.retencion_tipo_impuesto_eliminar, name='tipo_impuesto_eliminar'),

    # Ret. Regimenes
    path('tipos/regimenes/', views.retencion_tipo_regimen_listado, name='tipo_regimen_listado'),
    path('tipos/regimenes/alta/', views.retencion_tipo_regimen_alta, name='tipo_regimen_alta'),
    path('tipos/regimenes/<int:pk>/editar/', views.retencion_tipo_regimen_modificar, name='tipo_regimen_modificar'),
    path('tipos/regimenes/<int:pk>/eliminar/', views.retencion_tipo_regimen_eliminar, name='tipo_regimen_eliminar'),
]
