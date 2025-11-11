from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.gestion_usuarios'
    verbose_name = "Gestión de Usuarios y Permisos"

    #def ready(self):
    #    import apps.gestion_usuarios.signals
    #    from django.db.models.signals import post_migrate
    #    from apps.common.utils import crear_permiso_de_acceso_al_modulo
    #
    #    # 2. Conecta la señal a esa función, pasándole la configuración
    #    #    de esta app específica (self).
    #    post_migrate.connect(
    #        lambda sender, **kwargs: crear_permiso_de_acceso_al_modulo(self),
    #        sender=self
    #    )