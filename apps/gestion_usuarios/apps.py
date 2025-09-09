from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.gestion_usuarios'

    verbose_name = "Gestión de Usuarios y Permisos"

    def ready(self):
        import apps.gestion_usuarios.signals