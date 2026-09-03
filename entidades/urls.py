from django.urls import path
from . import views
app_name = 'entidades' # para facilitar las rutas puedan repetir el nombre, indica que las rutas pertenecen a la app roles
urlpatterns=[
    path('search', views.RolSearchListView.as_view(), name='search'),
    path('entidad-buscar/', views.entidad_buscar, name='entidad_buscar'),
    #path('<slug:slug>', views.RolDetailView.as_view(), name='rol'),  # id -> llave primaria
    path('<pk>',views.RolDetailView.as_view(),name='rol')#pk es el id
    #path('<slug:slug>', views.RolDetailView.as_view(), name='rol'),  # id -> llave primaria
]