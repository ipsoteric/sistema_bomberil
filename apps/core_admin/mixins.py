from django.contrib.auth.mixins import AccessMixin
from django.http import Http404

class SuperuserRequiredMixin(AccessMixin):
    """
    Mixin estricto para 'core_admin'.
    1. Verifica autenticación.
    2. Verifica flag is_superuser.
    3. Si falla, lanza 404 (Not Found) para ocultar la URL.
    """
    
    def dispatch(self, request, *args, **kwargs):
        # 1. Si no está logueado, redirige al login (comportamiento estándar)
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # 2. Si está logueado pero NO es superusuario, fingimos que la página no existe
        if not request.user.is_superuser:
            raise Http404
            
        # 3. Si pasa, continúa a la vista
        return super().dispatch(request, *args, **kwargs)