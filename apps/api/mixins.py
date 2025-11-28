from django.contrib.auth.mixins import AccessMixin
from django.http import JsonResponse
from apps.gestion_inventario.models import Estacion

class ApiSecurityMixin(AccessMixin):
    """
    Mixin de seguridad para Vistas API (AJAX/Fetch) (Clase View).
    1. Verifica autenticación (devuelve 401 JSON).
    2. Verifica estación activa (devuelve 403 JSON).
    3. Verifica permisos específicos definidos en la vista (devuelve 403 JSON).
    """
    
    def dispatch(self, request, *args, **kwargs):
        # 1. Verificación de Login
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error', 
                'message': 'Autenticación requerida.'
            }, status=401)

        # 2. Verificación de Estación Activa
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            return JsonResponse({
                'status': 'error', 
                'message': 'No hay una estación activa en la sesión.'
            }, status=403)

        # Cargamos la estación para que esté disponible en la vista (self.estacion_activa)
        try:
            self.estacion_activa = Estacion.objects.get(id=estacion_id)
        except Estacion.DoesNotExist:
             return JsonResponse({
                'status': 'error', 
                'message': 'La estación activa no es válida.'
            }, status=403)

        # 3. Verificación de Permisos Específicos
        # Si la vista tiene 'permission_required', lo verificamos manualmente aquí
        # porque PermissionRequiredMixin de Django redirige a login, y queremos JSON.
        if hasattr(self, 'permission_required') and self.permission_required:
            # Soporta un solo permiso (string) o varios (lista/tupla)
            perms = (self.permission_required,) if isinstance(self.permission_required, str) else self.permission_required
            
            if not request.user.has_perms(perms):
                return JsonResponse({
                    'status': 'error', 
                    'message': 'No tienes permisos suficientes para realizar esta acción.'
                }, status=403)

        return super().dispatch(request, *args, **kwargs)