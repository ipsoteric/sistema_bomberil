from django.urls import path
from .views import (
    InventarioInicioView, 
    InventarioPruebasView, 
    grafico_existencias_por_categoria,
    AreaListaView,
    CompartimentoListaView,
    AreaCrearView,
    AreaDetalleView,
    CompartimentoCrearView,
    AreaEditarView,
    CatalogoGlobalListView,
    ApiGetProductoGlobalSKU,
    ApiAnadirProductoLocal,
    ProductoGlobalCrearView,
    ProductoLocalListView,
    ProductoLocalEditView,
    ProveedorListView,
    ProveedorCrearView
    )

app_name = 'gestion_inventario'

urlpatterns = [
    # Página Inicial de la gestión de inventario
    path('', InventarioInicioView.as_view(), name="ruta_inicio"),
    # Pruebas
    path('pruebas/', InventarioPruebasView.as_view(), name="ruta_pruebas"),
    # Obtener datos para gráfico de total existencias por categoría (API)
    path('existencias_por_categoria/', grafico_existencias_por_categoria, name="ruta_obtener_grafico_categoria"),

    # Lista de áreas
    path('areas/', AreaListaView.as_view(), name="ruta_lista_areas"),
    # Lista de compartimentos
    path('compartimentos/', CompartimentoListaView.as_view(), name='ruta_lista_compartimentos'),
    # Crear área
    path('areas/crear/', AreaCrearView.as_view(), name="ruta_crear_area"),
    # Gestionar detalle de un área
    path('areas/<int:ubicacion_id>/gestionar/', AreaDetalleView.as_view(), name='ruta_gestionar_area'),
    # Crear compartimento para un área
    path('areas/<int:ubicacion_id>/compartimentos/crear/', CompartimentoCrearView.as_view(), name='ruta_crear_compartimento'),
    # Editar área
    path('areas/<int:ubicacion_id>/editar/', AreaEditarView.as_view(), name='ruta_editar_area'),

    # Catálogo global de productos
    path('catalogo-global/', CatalogoGlobalListView.as_view(), name='ruta_catalogo_global'),
    path('api/producto-global-sku/<int:pk>/', ApiGetProductoGlobalSKU.as_view(), name='api_get_producto_global_sku'),
    path('api/anadir-producto-local/', ApiAnadirProductoLocal.as_view(), name='api_anadir_producto_local'),
    # Crear nuevo producto global
    path('catalogo-global/crear/', ProductoGlobalCrearView.as_view(), name='ruta_crear_producto_global'),

    # Catálogo local de productos
    path('catalogo-local/', ProductoLocalListView.as_view(), name='ruta_catalogo_local'),
    # Editar producto local
    path('catalogo-local/editar/<int:pk>/', ProductoLocalEditView.as_view(), name='ruta_editar_producto_local'),

    # Lista de proveedores
    path('proveedores/', ProveedorListView.as_view(), name='ruta_lista_proveedores'),
    # Crear proveedor
    path('proveedores/crear/', ProveedorCrearView.as_view(), name='ruta_crear_proveedor'),
]