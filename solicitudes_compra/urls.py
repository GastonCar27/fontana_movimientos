from django.urls import path

from . import views

app_name = 'solicitudes_compra'

urlpatterns = [
    path('', views.solicitud_list, name='listado'),
    path('alta/', views.solicitud_form, name='alta'),
    path('<int:pk>/editar/', views.solicitud_form, name='editar'),
    path('<int:pk>/eliminar/', views.solicitud_eliminar, name='eliminar'),
    path('<int:pk>/vincular/', views.solicitud_vincular, name='vincular'),
    path('<int:pk>/pdf/', views.solicitud_pdf, name='pdf'),
    path('<int:pk>/excel/', views.solicitud_excel, name='excel'),
]
