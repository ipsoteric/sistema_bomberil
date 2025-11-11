from django.apps import AppConfig


class GestionInventarioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.gestion_inventario'
    verbose_name = "Gestión de Inventario"

    #def ready(self):
    #    from django.db.models.signals import post_migrate
    #    from apps.common.utils import crear_permiso_de_acceso_al_modulo
    #    import apps.gestion_inventario.signals
    #
    #    # 2. Conecta la señal a esa función, pasándole la configuración
    #    #    de esta app específica (self).
    #    post_migrate.connect(
    #        lambda sender, **kwargs: crear_permiso_de_acceso_al_modulo(self),
    #        sender=self
    #    )