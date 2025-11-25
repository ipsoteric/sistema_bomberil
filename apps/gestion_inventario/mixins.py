from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from core.settings import (
    INVENTARIO_UBICACION_ADMIN_NOMBRE as AREA_ADMINISTRATIVA)
from .models import Activo, LoteInsumo


class UbicacionMixin:
    """
    Este Mixin comprueba si la Ubicacion obtenida por la vista
    es de tipo 'ADMINISTRATIVA'. Si lo es, redirige con un
    mensaje de error.
    
    Requiere que la vista que lo usa defina un método get_object().
    """
    
    # URL a la que redirigir si la validación falla
    # Puedes sobreescribir esto en tus vistas si es necesario
    admin_redirect_url = reverse_lazy('gestion_inventario:ruta_inicio')

    def dispatch(self, request, *args, **kwargs):
        # 1. Obtenemos el objeto (la vista debe definir get_object)
        # Usamos self.object para que esté disponible en el resto de la vista
        try:
            self.object = self.get_object()
        except Exception as e:
            # Si get_object() lanza un error (ej. 404),
            # simplemente dejamos que el dispatch normal lo maneje.
            return super().dispatch(request, *args, **kwargs)

        # 2. ¡Aquí está tu lógica centralizada!
        if self.object.tipo_ubicacion.nombre == AREA_ADMINISTRATIVA:
            messages.error(request, "Esta ubicación es interna del sistema y no se puede gestionar.")
            return redirect(self.admin_redirect_url)

        # 3. Si la validación pasa, continuamos con la vista normal
        return super().dispatch(request, *args, **kwargs)




class InventoryStateValidatorMixin:
    """
    Mixin para validar reglas de negocio basadas en el estado del ítem.
    Genera mensajes amigables para el usuario final.
    """
    
    def validate_state(self, item, allowed_states):
        if isinstance(allowed_states, str):
            allowed_states = [allowed_states]
            
        current_state = item.estado.nombre
        
        if current_state not in allowed_states:
            # Diccionario de mensajes amigables según el estado actual (el obstáculo)
            errores_amigables = {
                'ANULADO POR ERROR': "Este registro está anulado y no admite modificaciones.",
                'DE BAJA': "Este ítem ya fue dado de baja del inventario permanentemente.",
                'EXTRAVIADO': "No se puede operar sobre un ítem reportado como extraviado.",
                'EN PRÉSTAMO EXTERNO': "Esta acción no se puede realizar porque el ítem está prestado.",
                'EN REPARACIÓN': "El ítem se encuentra en mantenimiento/reparación.",
                'PENDIENTE REVISIÓN': "El ítem debe ser revisado antes de realizar esta acción.",
                'EN TRÁNSITO': "El ítem está siendo trasladado y no está disponible."
            }
            
            # Mensaje por defecto si el estado no está en la lista
            msg = errores_amigables.get(
                current_state, 
                "El ítem no está disponible para realizar esta operación en este momento."
            )
            
            messages.warning(self.request, msg)
            return False
            
        return True




class StationInventoryObjectMixin:
    """
    Mixin para vistas que operan sobre un ítem de inventario (Activo o Lote).
    Responsabilidades:
    1. Leer 'tipo_item' y 'item_id' de la URL.
    2. Recuperar el objeto asegurando estrictamente la pertenencia a la estación activa.
    3. Exponer el objeto en self.item y self.tipo_item para la vista.
    """
    item = None
    tipo_item = None

    def dispatch(self, request, *args, **kwargs):
        # Recuperación robusta del ID de estación 
        # (Leemos directo de sesión para evitar problemas de orden MRO)
        estacion_id = request.session.get('active_estacion_id')
        
        if not estacion_id:
            # Si no hay estación, dejamos pasar (BaseEstacionMixin se encargará de redirigir)
            return super().dispatch(request, *args, **kwargs)

        self.tipo_item = kwargs.get('tipo_item')
        item_id = kwargs.get('item_id')

        # Lógica Polimórfica Centralizada
        if self.tipo_item == 'activo':
            self.item = get_object_or_404(
                Activo.objects.select_related('producto__producto_global', 'estado', 'compartimento'),
                id=item_id,
                estacion_id=estacion_id
            )
        elif self.tipo_item == 'lote':
            self.item = get_object_or_404(
                LoteInsumo.objects.select_related('producto__producto_global', 'estado', 'compartimento'),
                id=item_id,
                compartimento__ubicacion__estacion_id=estacion_id
            )
        else:
            # Si la URL está mal construida o el tipo no existe
            raise Http404("Tipo de ítem de inventario desconocido.")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Inyecta automáticamente el ítem en el contexto del template."""
        context = super().get_context_data(**kwargs)
        context['item'] = self.item
        context['tipo_item'] = self.tipo_item
        context['es_lote'] = (self.tipo_item == 'lote')
        return context