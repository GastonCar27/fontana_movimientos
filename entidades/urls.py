from django.urls import path
from . import views
app_name = 'entidades' # para facilitar las rutas puedan repetir el nombre, indica que las rutas pertenecen a la app roles
urlpatterns=[
    path('search', views.RolSearchListView.as_view(), name='search'),
    path('entidad-buscar/', views.entidad_buscar, name='entidad_buscar'),
    path('entidad-crear-rapido/', views.entidad_crear_rapido, name='entidad_crear_rapido'),
    path('alta/', views.entidad_alta, name='alta'),
    path('listado/', views.entidad_listado, name='listado'),
    path('editar/<int:pk>/', views.entidad_editar, name='editar'),
    path('reportes/', views.entidad_reporte, name='reportes'),
    path('reportes/excel/', views.entidad_reporte_excel, name='reporte_excel'),
    path('reportes/pdf/', views.entidad_reporte_pdf, name='reporte_pdf'),

    # --- Alta / Modificación / Listado de tipos de entidad (Rol) ---
    path('tipo-entidad/alta/', views.rol_alta, name='rol_alta'),
    path('tipo-entidad/listado/', views.rol_listado, name='rol_listado'),
    path('tipo-entidad/editar/<int:pk>/', views.rol_editar, name='rol_editar'),
    path('tipo-entidad/listado/excel/', views.rol_listado_excel, name='rol_listado_excel'),
    path('tipo-entidad/listado/pdf/', views.rol_listado_pdf, name='rol_listado_pdf'),

    #path('<slug:slug>', views.RolDetailView.as_view(), name='rol'),  # id -> llave primaria
    path('<pk>',views.RolDetailView.as_view(),name='rol')#pk es el id
    #path('<slug:slug>', views.RolDetailView.as_view(), name='rol'),  # id -> llave primaria
]