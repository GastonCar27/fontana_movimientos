from django.urls import path

from . import views

app_name = 'retenciones_inym'  # para poder usar {% url 'retenciones_inym:...' %} en los templates

urlpatterns = [
    path('ranking-entidades/', views.retencion_inym_ranking_entidades, name='ranking_entidades'),
    path('ranking-entidades/excel/', views.retencion_inym_ranking_entidades_excel, name='ranking_entidades_excel'),
    path('ranking-entidades/pdf/', views.retencion_inym_ranking_entidades_pdf, name='ranking_entidades_pdf'),
]
