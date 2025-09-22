from django.urls import path
from .views import *

app_name = "gestion_usuarios"

urlpatterns = [
    # Página Inicial de la gestión de usuarios
    path('', UsuarioInicioView.as_view(), name="ruta_inicio"),

    # Lista de usuarios
    path('usuarios/lista/', UsuarioListaView.as_view(), name="ruta_lista_usuarios"),

    # Ver detalle de usuario
    path('usuarios/<int:id>/', UsuarioObtenerView.as_view(), name="ruta_ver_usuario"),

    # Agregar usuario (enlistarlo en la compañía)
    path('usuarios/agregar/', UsuarioAgregarView.as_view(), name="ruta_agregar_usuario"),

    # Crear usuario
    path('usuarios/crear/', UsuarioCrearView.as_view(), name="ruta_crear_usuario"),

    # Modificar usuario
    path('usuarios/<int:id>/editar/', UsuarioEditarView.as_view(), name="ruta_editar_usuario"),

    # Desactivar usuario (No puede acceder al sistema)
    path('usuarios/<int:id>/desactivar/', UsuarioDesactivarView.as_view(), name="ruta_desactivar_usuario"),

    # Activar usuario (Puede acceder al sistema)
    path('usuarios/<int:id>/activar/', UsuarioActivarView.as_view(), name="ruta_activar_usuario"),

    # Asignar roles al usuario
    path('usuarios/<int:id>/asignar-roles/', UsuarioAsignarRolesView.as_view(), name='ruta_asignar_roles_usuario'),

    # Restablecer contraseña a usuario
    path('usuarios/<int:id>/restablecer-contrasena/', UsuarioRestablecerContrasena.as_view(), name='ruta_restablecer_contrasena'),

    # Ver permisos de usuario
    path('usuarios/<int:id>/permisos/', UsuarioVerPermisos.as_view(), name='ruta_ver_permisos_usuario'),



    # Lista de roles
    path('roles/', RolListaView.as_view(), name="ruta_lista_roles"),

    # Ver detalle de rol
    path('roles/<int:id>/', RolObtenerView.as_view(), name="ruta_ver_rol"),

    # Editar rol (nombre, descripción)
    path('roles/<int:id>/editar/', RolEditarView.as_view(), name="ruta_editar_rol"),

    # Crear rol
    path('roles/crear/', RolCrearView.as_view(), name="ruta_crear_rol"),

    # Asignar permisos a rol
    path('roles/<int:id>/asignar-permisos/', RolAsignarPermisosView.as_view(), name="ruta_asignar_permisos"),

    # Eliminar rol
    path('roles/<int:id>/eliminar/', RolEliminarView.as_view(), name="ruta_eliminar_rol"),
]