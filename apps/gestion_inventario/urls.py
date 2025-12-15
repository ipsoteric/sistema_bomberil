from django.urls import path
from .views import (
    InventarioInicioView, 
    AreaListaView,
    AreaCrearView,
    AreaEditarView,
    VehiculoCrearView,
    VehiculoEditarView,
    UbicacionDetalleView,
    UbicacionDeleteView,
    CompartimentoListaView,
    CompartimentoDetalleView,
    CompartimentoCrearView,
    CompartimentoEditView,
    CompartimentoDeleteView,
    CatalogoGlobalListView,
    ProductoGlobalCrearView,
    ProductoLocalListView,
    ProductoLocalEditView,
    ProductoLocalDetalleView,
    ProveedorListView,
    ProveedorCrearView,
    ProveedorDetalleView,
    ContactoPersonalizadoCrearView,
    ContactoPersonalizadoEditarView,
    StockActualListView,
    VehiculoListaView,
    RecepcionStockView,
    AgregarStockACompartimentoView,
    DetalleExistenciaView,
    AnularExistenciaView,
    AjustarStockLoteView,
    MovimientoInventarioListView,
    BajaExistenciaView,
    ExtraviadoExistenciaView,
    ConsumirStockLoteView,
    RegistrarUsoActivoView,
    TransferenciaExistenciaView,
    GenerarQRView,
    ImprimirEtiquetasView,
    CrearPrestamoView,
    HistorialPrestamosView,
    GestionarDevolucionView,
    DestinatarioListView,
    DestinatarioCreateView,
    DestinatarioEditView
    )

app_name = 'gestion_inventario'

urlpatterns = [
    # Página Inicial de la gestión de inventario
    path('', InventarioInicioView.as_view(), name="ruta_inicio"),

    # Lista de áreas
    path('areas/', AreaListaView.as_view(), name="ruta_lista_areas"),
    # Lista de compartimentos
    path('compartimentos/', CompartimentoListaView.as_view(), name='ruta_lista_compartimentos'),
    # Detalle de Compartimento
    path('compartimentos/<uuid:compartimento_id>/detalle/', CompartimentoDetalleView.as_view(), name='ruta_detalle_compartimento'),
    # Editar Compartimento
    path('compartimentos/<uuid:compartimento_id>/editar/', CompartimentoEditView.as_view(), name='ruta_editar_compartimento'),
    # Eliminar Compartimento
    path('compartimentos/<uuid:compartimento_id>/eliminar/', CompartimentoDeleteView.as_view(), name='ruta_eliminar_compartimento'),
    # Crear área
    path('areas/crear/', AreaCrearView.as_view(), name="ruta_crear_area"),
    # Gestionar detalle de una ubicación
    path('ubicaciones/<uuid:ubicacion_id>/gestionar/', UbicacionDetalleView.as_view(), name='ruta_gestionar_ubicacion'),
    # Crear compartimento para un área
    path('ubicaciones/<uuid:ubicacion_id>/compartimentos/crear/', CompartimentoCrearView.as_view(), name='ruta_crear_compartimento'),
    # Editar área
    path('areas/<uuid:ubicacion_id>/editar/', AreaEditarView.as_view(), name='ruta_editar_area'),

    # Lista de vehículos
    path('vehiculos/', VehiculoListaView.as_view(), name='ruta_lista_vehiculos'),
    # Crear vehículo
    path('vehiculos/crear/', VehiculoCrearView.as_view(), name='ruta_crear_vehiculo'),
    # Editar Vehículo
    path('vehiculos/<uuid:ubicacion_id>/editar/', VehiculoEditarView.as_view(), name='ruta_editar_vehiculo'),

    # Eliminar ubicación
    path('ubicaciones/<uuid:ubicacion_id>/eliminar/', UbicacionDeleteView.as_view(), name='ruta_eliminar_ubicacion'),

    # Catálogo global de productos
    path('catalogo-global/', CatalogoGlobalListView.as_view(), name='ruta_catalogo_global'),
    # Crear nuevo producto global
    path('catalogo-global/crear/', ProductoGlobalCrearView.as_view(), name='ruta_crear_producto_global'),
    # API para obtener detalle de producto global en apps.api (api:api_get_producto_global_sku)
    # API para agregar producto al catálogo local en apps.api (api:api_anadir_producto_local)

    # Catálogo local de productos
    path('catalogo-local/', ProductoLocalListView.as_view(), name='ruta_catalogo_local'),
    # Editar producto local
    path('catalogo-local/editar/<int:pk>/', ProductoLocalEditView.as_view(), name='ruta_editar_producto_local'),
    # Ver detalle de producto local
    path('catalogo-local/producto/<int:pk>/', ProductoLocalDetalleView.as_view(), name='ruta_detalle_producto_local'),

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
    path('compartimentos/<uuid:compartimento_id>/anadir-stock/', AgregarStockACompartimentoView.as_view(), name='ruta_agregar_stock_compartimento'),
    # Detalle 360° de la existencia (Trazabilidad completa)
    path('existencia/<str:tipo_item>/<uuid:item_id>/detalle/', DetalleExistenciaView.as_view(), name='ruta_detalle_existencia'),

    # Anular existencia
    path('existencia/<str:tipo_item>/<uuid:item_id>/anular/', AnularExistenciaView.as_view(), name='ruta_anular_existencia'),
    # Ajustar stock de existencia
    path('lotes/<uuid:lote_id>/ajustar-stock/', AjustarStockLoteView.as_view(), name='ruta_ajustar_stock_lote'),
    # Dar de baja existencia
    path('existencia/<str:tipo_item>/<uuid:item_id>/dar-de-baja/', BajaExistenciaView.as_view(), name='ruta_dar_de_baja_existencia'),
    # Reportar extravío de existencia
    path('existencia/<str:tipo_item>/<uuid:item_id>/extraviado/', ExtraviadoExistenciaView.as_view(), name='ruta_extraviado_existencia'),
    # Consumir stock (lotes de insumos)
    path('lotes/<uuid:lote_id>/consumir/', ConsumirStockLoteView.as_view(), name='ruta_consumir_stock_lote'),
    # Mover/Trasferir existencias (interno
    path('existencia/<str:tipo_item>/<uuid:item_id>/mover/', TransferenciaExistenciaView.as_view(), name='ruta_mover_existencia'),
    # Registrar horas de uso
    path('existencia/activo/<str:tipo_item>/<uuid:item_id>/registrar-uso/', RegistrarUsoActivoView.as_view(), name='ruta_registrar_uso_activo'),

    # Prestar existencias / Crear préstamo
    path('prestamos/crear/', CrearPrestamoView.as_view(), name='ruta_crear_prestamo'),
    # Endpoint para buscar existencias para préstamo en apps.api (api:api_buscar_prestables)
    path('prestamos/', HistorialPrestamosView.as_view(), name='ruta_historial_prestamos'),
    path('prestamos/<int:prestamo_id>/gestionar/', GestionarDevolucionView.as_view(), name='ruta_gestionar_devolucion'),

    # Gestión de destinatarios
    path('destinatarios/', DestinatarioListView.as_view(), name='ruta_lista_destinatarios'),
    path('destinatarios/crear/', DestinatarioCreateView.as_view(), name='ruta_crear_destinatario'),
    path('destinatarios/<int:destinatario_id>/editar/', DestinatarioEditView.as_view(), name='ruta_editar_destinatario'),

    # Historial de movimientos
    path('movimientos/', MovimientoInventarioListView.as_view(), name='ruta_historial_movimientos'),

    # Generar Código QR: Esta ruta capturará cualquier string (ej: E1-ACT-00123)
    path('generar-qr/<str:codigo>/', GenerarQRView.as_view(), name='ruta_generar_qr'),
    # Imprimir etiquetas QR
    path('imprimir-etiquetas/', ImprimirEtiquetasView.as_view(), name='ruta_imprimir_etiquetas'),
]