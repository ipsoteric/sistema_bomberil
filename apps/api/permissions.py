from rest_framework import permissions
from apps.gestion_inventario.models import Estacion
from apps.gestion_usuarios.models import Membresia


class IsEstacionActiva(permissions.BasePermission):
    """
    Verifica que el usuario tenga una estación activa.
    Estrategia Híbrida: Web (Sesión) -> Móvil (Header) -> BD (Membresía).
    Inyecta 'request.estacion_activa' para optimizar las vistas.
    """
    message = 'No se ha seleccionado una estación activa válida o no tiene acceso.'

    def has_permission(self, request, view):
        estacion_id = None

        # 1. Estrategia WEB: Buscar en la sesión (Cookie)
        if 'active_estacion_id' in request.session:
            estacion_id = request.session.get('active_estacion_id')

        # 2. Estrategia MÓVIL (API): Buscar en Headers
        # Útil si la App permite cambiar de estación y envía el ID explícitamente.
        elif 'X-Estacion-ID' in request.headers:
            estacion_id = request.headers.get('X-Estacion-ID')

        # 3. Estrategia FALLBACK (Membresía única):
        # Si no hay sesión ni header, buscamos si el usuario tiene una membresía ACTIVA.
        # Esto permite que la App funcione solo con el Token de Auth.
        else:
            try:
                #  "Un usuario solo puede tener una membresía activa a la vez"
                membresia = Membresia.objects.filter(
                    usuario=request.user, 
                    estado='ACTIVO'
                ).select_related('estacion').first()
                
                if membresia:
                    request.estacion_activa = membresia.estacion
                    return True # ¡Acceso concedido directo!
            except Exception:
                pass

        if not estacion_id:
            return False

        # 4. Validar ID y asignar objeto al request
        try:
            # Validamos que el ID exista y (opcionalmente) que el usuario tenga acceso a ella
            # Si ya validaste acceso en el login, aquí basta con obtener el objeto.
            estacion = Estacion.objects.get(id=estacion_id)
            request.estacion_activa = estacion # ¡Magia! Disponible en toda la vista
            return True
        except (Estacion.DoesNotExist, ValueError):
            return False




class IsSelfOrStationAdmin(permissions.BasePermission):
    """
    Permite acceso si es el propio usuario O si es un admin de su misma estación.
    Sólo para modificar información personal de usuarios
    """
    def has_object_permission(self, request, view, obj):
        # 1. Es el mismo usuario
        if obj == request.user:
            return True
        
        # 2. Es Admin (permiso django)
        if not request.user.has_perm('gestion_usuarios.accion_gestion_usuarios_modificar_info'):
            return False

        # 3. Verificar que ambos pertenezcan a la misma estación activa del admin
        admin_station_id = request.session.get('active_estacion_id')
        if not admin_station_id:
            return False

        return Membresia.objects.filter(
            usuario=obj,
            estacion_id=admin_station_id,
            estado__in=['ACTIVO', 'INACTIVO']
        ).exists()




# --- PERMISOS DE GESTIÓN DE USUARIOS ---
class CanCrearUsuario(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_usuarios_crear_usuario')
    



# --- PERMISOS DE GESTIÓN DE INVENTARIO ---
class CanVerCatalogos(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_ver_catalogos')

class CanCrearProductoGlobal(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_crear_producto_global')
    
class CanVerStock(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_ver_stock')
    
class CanRecepcionarStock(permissions.BasePermission):
    def has_permission(self, request, view):
        # El mismo permiso que usa tu vista web
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_recepcionar_stock')

class CanVerUbicaciones(permissions.BasePermission):
    def has_permission(self, request, view):
        # El mismo permiso que usa tu vista web
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_ver_ubicaciones')

class CanVerProveedores(permissions.BasePermission):
    def has_permission(self, request, view):
        # El mismo permiso que usa tu vista web
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_ver_proveedores')

class CanGestionarBajasStock(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_gestionar_bajas_stock')

class CanGestionarStockInterno(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_gestionar_stock_interno')
    
class CanGestionarPrestamos(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_gestionar_prestamos')

class CanVerPrestamos(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_inventario_ver_prestamos')




# --- PERMISOS DE GESTIÓN DE MANTENIMIENTO ---
class CanGestionarPlanes(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_mantenimiento_gestionar_planes')
    
class CanVerOrdenes(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_mantenimiento_ver_ordenes')

class CanGestionarOrdenes(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_mantenimiento_gestionar_ordenes')




# --- PERMISOS DE GESTIÓN USUARIOS ---
class CanVerUsuarios(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_usuarios_ver_usuarios')
    



# --- PERMISOS DE GESTIÓN DOCUMENTAL ---
class CanVerDocumentos(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_usuarios.accion_gestion_documental_ver_documentos')