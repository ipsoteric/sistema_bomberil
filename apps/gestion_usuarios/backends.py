from django.contrib.auth.backends import ModelBackend
from .models import Membresia
from apps.gestion_inventario.models import Estacion

class RolBackend(ModelBackend):
    """
    Backend de autenticación que maneja permisos a través del modelo Rol,
    considerando el contexto de la Compañía.
    """


    def _get_roles_for_user(self, user_obj, estacion=None):
        """Helper para obtener roles de un usuario en un contexto de compañía."""
        if not user_obj.is_active:
            return []
        
        query = Membresia.objects.filter(usuario=user_obj, estado='ACTIVO')
        if estacion:
            query = query.filter(estacion=estacion)
        
        # Obtenemos todas las membresías activas y sus roles
        membresias = query.select_related('estacion').prefetch_related('roles__permisos')
        return [rol for m in membresias for rol in m.roles.all()]



    def get_user_permissions(self, user_obj, obj=None):
        # Esta función no es contextual, devuelve TODOS los permisos del usuario
        # en todas las compañías donde tiene membresía activa.
        if not user_obj.is_active:
            return set()
        
        # Permisos asignados directamente al usuario
        user_perms = user_obj.user_permissions.all()
        
        # Permisos obtenidos a través de los roles en todas sus membresías activas
        roles = self._get_roles_for_user(user_obj)
        role_perms = set()
        for rol in roles:
            role_perms.update(rol.permisos.all())
            
        return set(user_perms) | role_perms



    def has_perm(self, user_obj, perm, obj=None):
        """
        Verifica si un usuario tiene un permiso específico, con posible contexto de Compañía.
        """
        if not user_obj.is_active:
            return False

        # Si el permiso está directamente en el usuario, se concede globalmente.
        if perm in self.get_user_permissions(user_obj):
             return True

        # Lógica contextual: si el objeto es una Compañía o tiene un atributo 'estacion'
        estacion_contexto = None
        if isinstance(obj, Estacion):
            estacion_contexto = obj
        elif hasattr(obj, 'estacion') and isinstance(obj.estacion, Estacion):
            estacion_contexto = obj.estacion
        
        if estacion_contexto:
            # Busca roles solo en la compañía del contexto
            roles_en_compania = self._get_roles_for_user(user_obj, estacion=estacion_contexto)
            for rol in roles_en_compania:
                if perm in {p.get_permission_string() for p in rol.permisos.all()}:
                    return True
        
        # Si no hay contexto o el permiso no se encontró en el contexto, denegar.
        return False