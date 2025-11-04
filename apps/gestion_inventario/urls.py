from django.urls import path
from .views import (
    InventarioInicioView, 
    InventarioPruebasView, 
    grafico_existencias_por_categoria,
    AreaListaView,
    AreaCrearView,
    AreaEditarView,
    UbicacionDetalleView,
    CompartimentoListaView,
    CompartimentoDetalleView,
    CompartimentoCrearView,
    CompartimentoEditView,
    CatalogoGlobalListView,
    ApiGetProductoGlobalSKU,
    ApiAnadirProductoLocal,
    ProductoGlobalCrearView,
    ProductoLocalListView,
    ProductoLocalEditView,
    ProveedorListView,
    ProveedorCrearView,
    ProveedorDetalleView,
    ContactoPersonalizadoCrearView,
    ContactoPersonalizadoEditarView,
    StockActualListView,
    VehiculoListaView,
    RecepcionStockView,
    AgregarStockACompartimentoView
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
    # Detalle de Compartimento
    path('compartimentos/<int:compartimento_id>/detalle/', CompartimentoDetalleView.as_view(), name='ruta_detalle_compartimento'),
    # Editar Compartimento
    path('compartimentos/<int:compartimento_id>/editar/', CompartimentoEditView.as_view(), name='ruta_editar_compartimento'),
    # Crear área
    path('areas/crear/', AreaCrearView.as_view(), name="ruta_crear_area"),
    # Gestionar detalle de una ubicación
    path('ubicaciones/<int:ubicacion_id>/gestionar/', UbicacionDetalleView.as_view(), name='ruta_gestionar_ubicacion'),
    # Crear compartimento para un área
    path('areas/<int:ubicacion_id>/compartimentos/crear/', CompartimentoCrearView.as_view(), name='ruta_crear_compartimento'),
    # Editar área
    path('areas/<int:ubicacion_id>/editar/', AreaEditarView.as_view(), name='ruta_editar_area'),

    # Lista de vehículos
    path('vehiculos/', VehiculoListaView.as_view(), name='ruta_lista_vehiculos'),
    # Editar vehículo
    path('vehiculos/<int:ubicacion_id>/editar/', AreaEditarView.as_view(), name='ruta_editar_vehiculo'),

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
    # Ver detalle proveedor
    path('proveedores/<int:pk>/', ProveedorDetalleView.as_view(), name='ruta_detalle_proveedor'),

    # Crear contacto personalizado
    path('proveedores/<int:proveedor_pk>/crear-contacto-personalizado/', ContactoPersonalizadoCrearView.as_view(), name='ruta_crear_contacto_personalizado'),
    # Editar contacto personalizado
    path('proveedores/contacto/<int:pk>/editar/', ContactoPersonalizadoEditarView.as_view(), name='ruta_editar_contacto_personalizado'),

    # Stock actual
    path('stock-actual/', StockActualListView.as_view(), name='ruta_stock_actual'),
    # Recepción de stock
    path('recepcion-stock/', RecepcionStockView.as_view(), name='ruta_recepcion_stock'),
    # Añadir Stock a Compartimento
    path('compartimentos/<int:compartimento_id>/añadir-stock/', AgregarStockACompartimentoView.as_view(), name='ruta_agregar_stock_compartimento')
]