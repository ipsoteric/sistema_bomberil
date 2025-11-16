from django.urls import path
from .views import (
    MantenimientoInicioView,
    PlanMantenimientoListView,
    PlanMantenimientoCrearView,
    PlanMantenimientoGestionarView,
    PlanMantenimientoEditarView,
    PlanMantenimientoEliminarView,
    ApiTogglePlanActivoView,
    ApiBuscarActivoParaPlanView,
    ApiAnadirActivoEnPlanView,
    ApiQuitarActivoDePlanView,
)

app_name = 'gestion_mantenimiento'

urlpatterns = [
    # Página Inicial de la gestión de inventario
    path('', MantenimientoInicioView.as_view(), name="ruta_inicio"),


    # --- Gestión de Planes (Punto 1) ---
    
    # 1. Lista de todos los planes de mantenimiento
    path('planes/', PlanMantenimientoListView.as_view(), name='ruta_lista_planes'),
    
    # 2. Formulario para crear un nuevo plan
    path('planes/crear/', PlanMantenimientoCrearView.as_view(), name='ruta_crear_plan'),
    
    # 3. Vista de "Gestionar" (Detalle) de un plan. 
    #    Aquí es donde se verán los activos asignados y se podrán añadir/quitar.
    path('planes/<int:pk>/gestionar/', PlanMantenimientoGestionarView.as_view(), name='ruta_gestionar_plan'),
    
    # 4. Formulario para editar los datos de un plan (nombre, trigger, frecuencia)
    path('planes/<int:pk>/editar/', PlanMantenimientoEditarView.as_view(), name='ruta_editar_plan'),
    
    # 5. Vista de confirmación para eliminar un plan
    path('planes/<int:pk>/eliminar/', PlanMantenimientoEliminarView.as_view(), name='ruta_eliminar_plan'),

    # --- API (Endpoints para gestionar planes de forma interactiva) ---
    
    # API para activar/desactivar el plan (cambia 'activo_en_sistema')
    path('api/planes/<int:pk>/toggle-activo/', ApiTogglePlanActivoView.as_view(), name='api_toggle_plan_activo'),
    
    # API para buscar activos (ej. por SKU o nombre) para añadirlos al plan
    # Se usaría en la vista 'ruta_gestionar_plan'
    path('api/planes/buscar-activo/', ApiBuscarActivoParaPlanView.as_view(), name='api_buscar_activo_para_plan'),

    # API para añadir un activo (POST) a un plan específico
    path('api/planes/<int:plan_pk>/anadir-activo/', ApiAnadirActivoEnPlanView.as_view(), name='api_anadir_activo_plan'),

    # API para quitar un activo de un plan (DELETE)
    # El 'pk' aquí es el ID del registro 'PlanActivoConfig'
    path('api/planes/configuracion/<int:pk>/quitar/', ApiQuitarActivoDePlanView.as_view(), name='api_quitar_activo_plan'),
]