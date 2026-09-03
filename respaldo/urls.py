from django.urls import path

from . import views

app_name = 'respaldo'
urlpatterns = [
    path('', views.respaldo_bd, name='backup'),
    path('descargar/<str:nombre>/', views.descargar_backup, name='backup_descargar'),
]
