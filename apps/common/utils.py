from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


def crear_permiso_de_acceso_al_modulo(app_config):
    # ... (imports no cambian)
    from .models import ModulePermissionAnchor

    try:
        content_type = ContentType.objects.get_for_model(ModulePermissionAnchor)
        codename = f'acceso_{app_config.label}' 
        
        Permission.objects.get_or_create(
            codename=codename,
            name=f'Acceso al módulo de {app_config.verbose_name}',
            content_type=content_type,
        )
    except Exception as e:
        print(f"Error al crear permiso para la app {app_config.name}: {e}")