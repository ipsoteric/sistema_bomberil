from django.urls import path
from .views import AdministracionInicioView, EstacionListaView, EstacionDetalleView, EstacionEditarView, EstacionCrearView

app_name = 'core_admin'

urlpatterns = [
    # Página Inicial
    path('', AdministracionInicioView.as_view(), name="ruta_inicio"),

    # Lista de estaciones
    path('estaciones/', EstacionListaView.as_view(), name='ruta_lista_estaciones'),

    # Ver detalle de estación
    path('estaciones/<int:pk>/', EstacionDetalleView.as_view(), name='ruta_ver_estacion'),

    # Editar estación
    path('estaciones/<int:pk>/editar/', EstacionEditarView.as_view(), name='ruta_editar_estacion'),

    # Crear estación
    path('estaciones/crear/', EstacionCrearView.as_view(), name='ruta_crear_estacion'),

]