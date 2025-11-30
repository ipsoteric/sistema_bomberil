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
    MantenimientoBuscarActivoParaPlanAPIView,
    MantenimientoAnadirActivoEnPlanAPIView,
    MantenimientoQuitarActivoDePlanAPIView,
    MantenimientoTogglePlanActivoAPIView,
    MantenimientoRegistrarTareaAPIView,
    MantenimientoCambiarEstadoOrdenAPIView,
    MantenimientoBuscarActivoParaOrdenAPIView,
    MantenimientoAnadirActivoOrdenAPIView,
    MantenimientoQuitarActivoOrdenAPIView,
)

app_name = "api"

urlpatterns = [
    # Alternar tema oscuro
    path('alternar-tema-oscuro/', AlternarTemaOscuroAPIView.as_view(), name='api_alternar_tema'),


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
    # Buscar existencias disponibles para préstamo
    path('gestion_inventario/prestamo/buscar-prestables/', InventarioBuscarExistenciasPrestablesAPI.as_view(), name='api_buscar_prestables'),


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
]