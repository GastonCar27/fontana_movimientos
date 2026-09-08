from django.contrib import admin
from django.urls import path
from django.urls import include


from . import views
urlpatterns =[
    path('',views.login_view,name='login'),
    path('admin/', admin.site.urls),
    path('usuarios/login',views.login_view,name='login'),
    path('usuarios/logout', views.logout_view, name='logout'),
    path('usuarios/registro', views.register, name='register'),
    path('panel/', views.panel, name='panel'),
    path('roles/',include('entidades.urls')),
    path('movimiento/',include('movimientos.urls')),
    path('comprobante/',include('comprobantes.urls')),
    path('remitos/', include('remitos.urls')),
    path('liquidaciones/', include('liquidaciones.urls')),
    path('movimiento-caja/', include('movimientos_caja.urls')),
    path('respaldo/', include('respaldo.urls')),
    path('retenciones/', include('retenciones.urls')),
    path('retenciones-inym/', include('retenciones_inym.urls')),
    path('tipos/', include('tipos.urls')),
    path('empleados/', include('empleados.urls')),
    path('solicitudes-compra/', include('solicitudes_compra.urls')),
    path('productos/', include('productos.urls')),
    path('cuenta-corriente-productos/', include('cuenta_corriente_productos.urls')),


]
