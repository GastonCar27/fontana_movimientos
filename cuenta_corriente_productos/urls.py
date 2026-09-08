from django.urls import path

from . import views

app_name = 'cuenta_corriente_productos'

urlpatterns = [
    path('', views.movimientos_abiertos, name='movimientos_abiertos'),
    path('movimiento/<int:movimiento_id>/cerrar/', views.cerrar_movimiento, name='cerrar_movimiento'),
    path('movimiento/<int:movimiento_id>/reabrir/', views.reabrir_movimiento, name='reabrir_movimiento'),
    path('movimiento/<int:movimiento_id>/vincular/', views.vincular_renglon, name='vincular_renglon'),
    path('vinculo/<int:vinculo_id>/desvincular/', views.desvincular_renglon, name='desvincular_renglon'),
    path('cuenta-corriente/', views.cuenta_corriente_entidad, name='cuenta_corriente'),
    path('liquidacion/alta/', views.liquidacion_alta, name='liquidacion_alta'),
    path('diferencias/', views.diferencias, name='diferencias'),
    path('liquidacion/<int:pk>/recalcular/', views.recalcular_liquidacion, name='recalcular_liquidacion'),
]
