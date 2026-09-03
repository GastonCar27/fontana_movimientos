from django.urls import path

from . import views

app_name = 'empleados'

urlpatterns = [
    path('', views.empleado_list, name='listado'),
    path('buscar/', views.empleado_buscar, name='buscar'),
    path('alta/', views.empleado_form, name='alta'),
    path('<int:pk>/editar/', views.empleado_form, name='editar'),
    path('<int:pk>/eliminar/', views.empleado_eliminar, name='eliminar'),
]
