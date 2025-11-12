from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from core.settings import (
    INVENTARIO_UBICACION_ADMIN_NOMBRE as AREA_ADMINISTRATIVA)


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