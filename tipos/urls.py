from django.urls import path

from . import views

app_name = 'tipos'

urlpatterns = [
    path('<slug:slug>/', views.tipo_listado, name='listado'),
    path('<slug:slug>/alta/', views.tipo_alta, name='alta'),
    path('<slug:slug>/<int:pk>/editar/', views.tipo_modificar, name='modificar'),
    path('<slug:slug>/<int:pk>/eliminar/', views.tipo_eliminar, name='eliminar'),
]
