from django.urls import path
from .views import (
    AlternarTemaOscuroAPIView,
    BuscarUsuarioAPIView, 
    ActualizarAvatarUsuarioAPIView, 
    ComunasPorRegionAPIView, 
    InventarioGraficoEstadosAPIView, 
    InventarioGraficoExistenciasCategoriaAPIView,
    InventarioProductoGlobalSKUAPIView,
    InventarioAnadirProductoLocalAPIView,
    InventarioBuscarExistenciasPrestablesAPI,
    InventarioCrearPrestamoAPIView,
    InventarioDestinatarioListAPIView,
    InventarioDetalleExistenciaAPIView,
    InventarioCatalogoStockAPIView,
    InventarioExistenciasPorProductoAPIView,
    InventarioRecepcionStockAPIView,
    InventarioUbicacionListAPIView,
    InventarioCompartimentoListAPIView,
    InventarioProveedorListAPIView,
    InventarioAnularExistenciaAPIView,
    InventarioAjustarStockAPIView,
    InventarioConsumirStockAPIView,
    InventarioBajaExistenciaAPIView,
    InventarioExtraviarActivoAPIView,
    InventarioHistorialPrestamosAPIView,
    InventarioGestionarDevolucionAPIView,
    MantenimientoBuscarActivoParaPlanAPIView,
    MantenimientoAnadirActivoEnPlanAPIView,
    MantenimientoQuitarActivoDePlanAPIView,
    MantenimientoTogglePlanActivoAPIView,
    MantenimientoRegistrarTareaAPIView,
    MantenimientoCambiarEstadoOrdenAPIView,
    MantenimientoBuscarActivoParaOrdenAPIView,
    MantenimientoAnadirActivoOrdenAPIView,
    MantenimientoQuitarActivoOrdenAPIView,
    MantenimientoOrdenListAPIView,
    MantenimientoOrdenCorrectivaCreateAPIView,
    BomberilLoginView,
    BomberilRefreshView,
    BomberilLogoutView,
    MeView,
    PasswordResetRequestView,
    TestConnectionView
)

app_name = "api"

urlpatterns = [
    # Alternar tema oscuro
    path('alternar-tema-oscuro/', AlternarTemaOscuroAPIView.as_view(), name='api_alternar_tema'),
    path('test-connection/', TestConnectionView.as_view(), name='test_connection'),


    # --- AUTENTICACIÓN ---
    # Login: Entrega Access Token, Refresh Token y Datos de Usuario/Estaciones
    path('auth/login/', BomberilLoginView.as_view(), name='token_obtain_pair'),
    # Refresh: Permite obtener un nuevo Access Token cuando el anterior expira
    path('auth/refresh/', BomberilRefreshView.as_view(), name='token_refresh'),
    # Cerrar sesión
    path('auth/logout/', BomberilLogoutView.as_view(), name='token_blacklist'),
    # Obtener información del usuario
    path('auth/me/', MeView.as_view(), name='users_me'),
    # Recuperar contraseña
    path('auth/password_reset/', PasswordResetRequestView.as_view(), name='password_reset_request'),


    # --- USUARIOS ---
    # Buscar usuario para agregarlo a la estación
    path('gestion_usuarios/buscar-usuario-para-agregar', BuscarUsuarioAPIView.as_view(), name='api_buscar_usuario'),
    # Modificar avatar
    path('gestion_usuarios/usuarios/<uuid:id>/editar-avatar/', ActualizarAvatarUsuarioAPIView.as_view(), name="api_editar_avatar_usuario"),


    # --- INVENTARIO ---
    # Obtener comunas por región
    path('gestion_inventario/comunas-por-region/<int:region_id>/', ComunasPorRegionAPIView.as_view(), name='api_comunas_por_region'),
    # Obtener gráfico de existencias por categoría
    path('gestion_inventario/existencias-por-categoria/', InventarioGraficoExistenciasCategoriaAPIView.as_view(), name="api_obtener_grafico_categoria"),
    # Obtener gráfico existencias por estado
    path('gestion_inventario/existencias-por-estado/', InventarioGraficoEstadosAPIView.as_view(), name="api_grafico_estado"),
    # Obtener detalle de producto global y SKU sugerido
    path('gestion_inventario/detalle-existencia/<int:pk>/', InventarioProductoGlobalSKUAPIView.as_view(), name="api_get_producto_global_sku"),
    # Agregar producto al catálogo local
    path('gestion_inventario/anadir-producto-local/', InventarioAnadirProductoLocalAPIView.as_view(), name="api_anadir_producto_local"),

    # --- INVENTARIO: PRÉSTAMOS ---
    # Buscar existencias disponibles para préstamo
    path('gestion_inventario/prestamo/buscar-prestables/', InventarioBuscarExistenciasPrestablesAPI.as_view(), name='api_buscar_prestables'),
    # Crear préstamo
    path('gestion_inventario/prestamos/crear/', InventarioCrearPrestamoAPIView.as_view(), name='api_crear_prestamo'),
    # Obtener destinatarios
    path('gestion_inventario/destinatarios/', InventarioDestinatarioListAPIView.as_view(), name='api_destinatarios_list'),
    # Lista de préstamos
    path('gestion_inventario/prestamos/', InventarioHistorialPrestamosAPIView.as_view(), name='api_historial_prestamos'),
    # Gestionar préstamo
    path('gestion_inventario/prestamos/<int:prestamo_id>/devolucion/', InventarioGestionarDevolucionAPIView.as_view(), name='api_gestionar_devolucion'),

    # Obtener detalle de una existencia
    path('gestion_inventario/existencias/buscar/', InventarioDetalleExistenciaAPIView.as_view(), name='api_existencia_detalle'),
    # Obtener catálogo local de productos (con existencias)
    path('gestion_inventario/catalogo/stock/', InventarioCatalogoStockAPIView.as_view(), name='api_catalogo_stock'),
    # Lista de Existencias por Producto
    path('gestion_inventario/existencias/', InventarioExistenciasPorProductoAPIView.as_view(), name='api_existencias_por_producto'),
    # Recepcionar stock
    path('gestion_inventario/movimientos/recepcion/', InventarioRecepcionStockAPIView.as_view(), name='api_recepcion_stock'),
    # Rutas Core / Auxiliares (Selectores)
    path('gestion_inventario/core/ubicaciones/', InventarioUbicacionListAPIView.as_view(), name='api_ubicaciones_list'),
    path('gestion_inventario/core/compartimentos/', InventarioCompartimentoListAPIView.as_view(), name='api_compartimentos_list'),
    path('gestion_inventario/core/proveedores/', InventarioProveedorListAPIView.as_view(), name='api_proveedores_list'),
    # Ruta para ajuste cíclico (conteo manual)
    path('gestion_inventario/movimientos/ajustar/', InventarioAjustarStockAPIView.as_view(), name='api_ajustar_stock'),
    # Ruta para consumo de stock (salida interna)
    path('gestion_inventario/movimientos/consumir/', InventarioConsumirStockAPIView.as_view(), name='api_consumir_stock'),
    # Mover/Trasferir existencias (interno) (PENDIENTE)
    # Ruta para anular (dar de baja lógica por error)
    path('gestion_inventario/movimientos/anular/', InventarioAnularExistenciaAPIView.as_view(), name='api_anular_existencia'),
    # Ruta para dar de baja (fin de vida útil / daño)
    path('gestion_inventario/movimientos/baja/', InventarioBajaExistenciaAPIView.as_view(), name='api_baja_existencia'),
    # Ruta para reportar extravío (pérdida accidental)
    path('gestion_inventario/movimientos/extravio/', InventarioExtraviarActivoAPIView.as_view(), name='api_extravio_activo'),




    # --- MANTENIMIENTO ---
    # API para buscar activos (ej. por SKU o nombre) para añadirlos al plan. Se usaría en la vista 'ruta_gestionar_plan'
    path('gestion_mantenimiento/planes/buscar-activo/', MantenimientoBuscarActivoParaPlanAPIView.as_view(), name='api_buscar_activo_para_plan'),
    # API para añadir un activo (POST) a un plan específico
    path('gestion_mantenimiento/planes/<int:plan_pk>/anadir-activo,/', MantenimientoAnadirActivoEnPlanAPIView.as_view(), name="api_anadir_activo_plan"),
    # API para quitar un activo de un plan (DELETE)
    path('gestion_mantenimiento/planes/<int:pk>/quitar-activo/', MantenimientoQuitarActivoDePlanAPIView.as_view(), name='api_quitar_activo_plan'),
    # API para activar/desactivar el plan (cambia 'activo_en_sistema')
    path('gestion_mantenimiento/planes/<int:pk>/toggle-activo/', MantenimientoTogglePlanActivoAPIView.as_view(), name='api_toggle_plan_activo'),

    # Registrar tarea/mantenimiento de un activo específico
    # Se llama cuando el usuario hace click en "Listo" o "Registrar" sobre un activo en la lista
    path('gestion_mantenimiento/ordenes/<int:pk>/registrar-tarea/', MantenimientoRegistrarTareaAPIView.as_view(), name='api_registrar_tarea_orden'),

    # --- Gestión de Activos en Orden de mantenimiento ---
    # Cambiar estado global (Ej: Iniciar trabajo, Finalizar orden)
    path('gestion_mantenimiento/ordenes/<int:pk>/cambiar-estado/', MantenimientoCambiarEstadoOrdenAPIView.as_view(), name='api_cambiar_estado_orden'),
    path('gestion_mantenimiento/ordenes/buscar-activo/', MantenimientoBuscarActivoParaOrdenAPIView.as_view(), name='api_buscar_activo_para_orden'),
    path('gestion_mantenimiento/ordenes/<int:pk>/anadir-activo/', MantenimientoAnadirActivoOrdenAPIView.as_view(), name='api_anadir_activo_orden'),
    path('gestion_mantenimiento/ordenes/<int:pk>/quitar-activo/', MantenimientoQuitarActivoOrdenAPIView.as_view(), name='api_quitar_activo_orden'),
    # Lista de órdenes
    path('gestion_mantenimiento/ordenes/', MantenimientoOrdenListAPIView.as_view(), name='api_ordenes_list'),
    # Crear orden
    path('gestion_mantenimiento/ordenes/crear/', MantenimientoOrdenCorrectivaCreateAPIView.as_view(), name='api_crear_orden_correctiva'),
]