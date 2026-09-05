from django.urls import path
from . import views
app_name = 'entidades' # para facilitar las rutas puedan repetir el nombre, indica que las rutas pertenecen a la app roles
urlpatterns=[
    path('search', views.RolSearchListView.as_view(), name='search'),
    path('entidad-buscar/', views.entidad_buscar, name='entidad_buscar'),
    path('alta/', views.entidad_alta, name='alta'),
    path('listado/', views.entidad_listado, name='listado'),
    path('editar/<int:pk>/', views.entidad_editar, name='editar'),
    path('reportes/', views.entidad_reporte, name='reportes'),
    path('reportes/excel/', views.entidad_reporte_excel, name='reporte_excel'),
    path('reportes/pdf/', views.entidad_reporte_pdf, name='reporte_pdf'),
    #path('<slug:slug>', views.RolDetailView.as_view(), name='rol'),  # id -> llave primaria
    path('<pk>',views.RolDetailView.as_view(),name='rol')#pk es el id
    #path('<slug:slug>', views.RolDetailView.as_view(), name='rol'),  # id -> llave primaria
]