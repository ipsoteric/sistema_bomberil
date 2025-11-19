from django.urls import path
from .views import (
    AdministracionInicioView, 
    EstacionListaView, 
    EstacionDetalleView, 
    EstacionEditarView, 
    EstacionCrearView, 
    EstacionEliminarView, 
    EstacionSwitchView, 
    ProductoGlobalListView, 
    ProductoGlobalCreateView, 
    ProductoGlobalUpdateView, 
    ProductoGlobalDeleteView, 
    UsuarioListView, 
    UsuarioCreateView
)

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

    # Eliminar estación
    path('estaciones/<int:pk>/eliminar/', EstacionEliminarView.as_view(), name='ruta_eliminar_estacion'),

    # Acceder a una estación
    path('estaciones/<int:pk>/ingresar/', EstacionSwitchView.as_view(), name='ruta_acceder_estacion'),

    # Catálogo global de productos
    path('catalogo-global/', ProductoGlobalListView.as_view(), name='ruta_catalogo_global'),

    # Crear producto global
    path('catalogo-global/crear/', ProductoGlobalCreateView.as_view(), name='ruta_crear_producto_global'),

    # Editar producto global
    path('catalogo-global/<int:pk>/editar/', ProductoGlobalUpdateView.as_view(), name='ruta_editar_producto_global'),

    # Eliminar producto global
    path('catalogo-global/<int:pk>/eliminar/', ProductoGlobalDeleteView.as_view(), name='ruta_eliminar_producto_global'),

    # Lista de usuarios
    path('usuarios/', UsuarioListView.as_view(), name='ruta_lista_usuarios'),

    path('usuarios/crear/', UsuarioCreateView.as_view(), name='ruta_crear_usuario'),
]