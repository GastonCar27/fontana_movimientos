from django.urls import path

from . import views

app_name = 'retenciones_inym'  # para poder usar {% url 'retenciones_inym:...' %} en los templates

urlpatterns = [
    path('', views.retencion_inym_listado, name='listado'),
    path('listado/excel/', views.retencion_inym_listado_excel, name='listado_excel'),
    path('listado/pdf/', views.retencion_inym_listado_pdf, name='listado_pdf'),
    path('alta/', views.retencion_inym_alta, name='alta'),
    path('operador-buscar/', views.operador_inym_buscar, name='operador_buscar'),
    path('<int:pk>/modificar/', views.retencion_inym_modificar, name='modificar'),
    path('<int:pk>/eliminar/', views.retencion_inym_eliminar, name='eliminar'),
    path('importar/', views.retencion_inym_importar, name='importar'),
    path('importar/diferencias/excel/', views.retencion_inym_importar_diferencias_excel, name='importar_diferencias_excel'),
    path('importar/diferencias/pdf/', views.retencion_inym_importar_diferencias_pdf, name='importar_diferencias_pdf'),

    path('ranking-entidades/', views.retencion_inym_ranking_entidades, name='ranking_entidades'),
    path('ranking-entidades/excel/', views.retencion_inym_ranking_entidades_excel, name='ranking_entidades_excel'),
    path('ranking-entidades/pdf/', views.retencion_inym_ranking_entidades_pdf, name='ranking_entidades_pdf'),

    # Tabla histórica de análisis (RetencionInymHistorico) -- pedido de
    # Gastón, 24/09/2026. Ver retenciones_inym/importador_historico.py.
    path('historico/importar/', views.retencion_inym_historico_importar, name='historico_importar'),
    path('analisis-kgs/', views.retencion_inym_analisis_kgs, name='analisis_kgs'),
    path(
        'analisis-kgs/operadores/excel/', views.retencion_inym_analisis_kgs_operadores_excel,
        name='analisis_kgs_operadores_excel',
    ),
    path(
        'analisis-kgs/operadores/pdf/', views.retencion_inym_analisis_kgs_operadores_pdf,
        name='analisis_kgs_operadores_pdf',
    ),
    path(
        'analisis-kgs/varianza/excel/', views.retencion_inym_analisis_kgs_varianza_excel,
        name='analisis_kgs_varianza_excel',
    ),
    path(
        'analisis-kgs/varianza/pdf/', views.retencion_inym_analisis_kgs_varianza_pdf,
        name='analisis_kgs_varianza_pdf',
    ),
    path(
        'analisis-kgs/mensual/excel/', views.retencion_inym_analisis_kgs_mensual_excel,
        name='analisis_kgs_mensual_excel',
    ),
    path(
        'analisis-kgs/mensual/pdf/', views.retencion_inym_analisis_kgs_mensual_pdf,
        name='analisis_kgs_mensual_pdf',
    ),
]
