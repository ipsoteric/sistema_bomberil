from django.core.exceptions import PermissionDenied, ImproperlyConfigured
from django.contrib.auth.mixins import AccessMixin
from django.apps import apps
from django.shortcuts import get_object_or_404
from django.http import Http404


class ModuleAccessMixin(AccessMixin):
    """
    Verifica que el usuario tenga el permiso de acceso principal para el módulo.
    """
    def dispatch(self, request, *args, **kwargs):
        # 1. Obtenemos la ruta del módulo de la vista (ej: 'apps.gestion_usuarios.views')
        view_module_path = self.request.resolver_match.func.__module__

        # 2. Django nos dice a qué app pertenece ese módulo
        app_config = apps.get_containing_app_config(view_module_path)
        if not app_config:
            raise PermissionDenied("No se pudo determinar la aplicación para la vista.")

        # 3. Construimos el codename del permiso (ej: 'acceso_gestion_usuarios')
        codename = f'acceso_{app_config.label}'
        
        # 4. Construimos el nombre completo del permiso.
        #    Recordemos que el permiso está ANCLADO en la app 'common'.
        permission_required = f'common.{codename}'

        # 5. Verificamos si el usuario tiene el permiso
        if not request.user.has_perm(permission_required):
            raise PermissionDenied # Lanza un error 403 Prohibido

        # Si todo está en orden, la vista continúa.
        return super().dispatch(request, *args, **kwargs)




class ObjectInStationRequiredMixin(AccessMixin):
    """
    Versión mejorada que verifica si un objeto pertenece a la estación activa
    del usuario, incluso a través de relaciones anidadas (ej: 'seccion__ubicacion__estacion').
    """
    station_lookup = 'estacion' # Ruta de búsqueda al campo de la estación.

    def dispatch(self, request, *args, **kwargs):
        active_station_id = request.session.get('active_estacion_id')
        if not active_station_id:
            return self.handle_no_permission()

        pk = kwargs.get('pk') or kwargs.get('id')
        if not pk:
            return super().dispatch(request, *args, **kwargs)

        obj = get_object_or_404(self.model, pk=pk)

        try:
            # Empezamos con el objeto principal (ej: una Existencia)
            related_obj = obj
            # Dividimos la ruta (ej: 'seccion__ubicacion__estacion') en partes
            for part in self.station_lookup.split('__'):
                # Navegamos a través de cada relación (obj.seccion, luego obj.ubicacion, etc.)
                related_obj = getattr(related_obj, part)
            
            # Al final, 'related_obj' será la instancia de la Estacion
            object_station = related_obj
            
            # Comparamos si el ID de la estación del objeto es el correcto
            if object_station.id != active_station_id:
                raise Http404
                
        except AttributeError:
            raise ImproperlyConfigured(
                f"El modelo {self.model.__name__} no pudo resolver la ruta de búsqueda '{self.station_lookup}'."
            )

        return super().dispatch(request, *args, **kwargs)