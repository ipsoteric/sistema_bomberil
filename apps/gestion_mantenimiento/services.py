from django.utils import timezone
from datetime import timedelta
from apps.gestion_usuarios.models import RegistroActividad

def auditar_modificacion_incremental(request, plan, accion_detalle):
    """
    Busca un registro de actividad reciente (últimos 15 min) para este usuario y plan.
    Si existe, lo actualiza agregando el detalle. Si no, crea uno nuevo.
    
    plan: Instancia de PlanMantenimiento.
    accion_detalle: String ej: "Agregó activo Hacha-01"
    """
    estacion_id = request.session.get('active_estacion_id')
    actor = request.user if request.user.is_authenticated else None
    verbo_base = "realizó cambios en la lista de activos del plan"
    
    # Ventana de tiempo para agrupar (ej: 15 minutos)
    tiempo_limite = timezone.now() - timedelta(minutes=15)

    # 1. Buscar último log similar
    ultimo_log = RegistroActividad.objects.filter(
        actor=actor,
        estacion_id=estacion_id,
        verbo=verbo_base,
        objetivo_content_type__model='planmantenimiento', # Ajustar según tu ContentType real
        objetivo_object_id=str(plan.id), # Asumiendo que migramos a CharField
        fecha__gte=tiempo_limite
    ).first()

    if ultimo_log:
        # 2. Actualizar existente
        detalles = ultimo_log.detalles or {}
        
        # Historial de cambios interno
        historial = detalles.get('historial_cambios', [])
        historial.append(f"{timezone.now().strftime('%H:%M:%S')} - {accion_detalle}")
        
        # Contador total
        total = detalles.get('total_cambios', 0) + 1
        
        detalles['historial_cambios'] = historial[-20:] # Guardamos solo los últimos 20 para no explotar
        detalles['total_cambios'] = total
        
        ultimo_log.detalles = detalles
        ultimo_log.save(update_fields=['detalles'])
        
    else:
        # 3. Crear nuevo
        from apps.common.services import core_registrar_actividad # Importar la función base
        
        core_registrar_actividad(
            request=request,
            verbo=verbo_base,
            objetivo=plan,
            detalles={
                'total_cambios': 1,
                'historial_cambios': [f"{timezone.now().strftime('%H:%M:%S')} - {accion_detalle}"]
            }
        )