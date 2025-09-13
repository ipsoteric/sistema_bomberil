from django.db import models

class ModulePermissionAnchor(models.Model):
    """
    Este modelo no crea una tabla para usarla, sino que actúa como un
    punto de anclaje centralizado para permisos personalizados a nivel de
    módulo o aplicación.
    """
    class Meta:
        verbose_name = "Ancla de Permiso de Módulo"
        verbose_name_plural = "Anclas de Permisos de Módulo"
        
        # Con esto evitamos que Django cree permisos inútiles de 
        # "add", "change", "delete", "view" para este modelo ancla.
        default_permissions = []