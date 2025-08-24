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

    # Lista de roles
    path('roles/', RolListaView.as_view(), name="ruta_lista_roles"),
]