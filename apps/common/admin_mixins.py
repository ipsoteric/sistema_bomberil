from django.utils.html import format_html

class SysPermissionMixin:
    """
    Mixin para forzar al Admin de Django a usar los permisos personalizados 'sys_'
    definidos en los modelos, en lugar de los permisos estándar (add, change, delete, view).
    """
    def has_view_permission(self, request, obj=None):
        opts = self.opts
        codename = f'{opts.app_label}.sys_view_{opts.model_name}'
        return request.user.has_perm(codename)

    def has_add_permission(self, request, obj=None):
        opts = self.opts
        codename = f'{opts.app_label}.sys_add_{opts.model_name}'
        return request.user.has_perm(codename)

    def has_change_permission(self, request, obj=None):
        opts = self.opts
        codename = f'{opts.app_label}.sys_change_{opts.model_name}'
        return request.user.has_perm(codename)

    def has_delete_permission(self, request, obj=None):
        opts = self.opts
        codename = f'{opts.app_label}.sys_delete_{opts.model_name}'
        return request.user.has_perm(codename)
    
    # Opcional: Para asegurar que el modelo aparezca en el índice de la app
    def has_module_permission(self, request):
        # Verifica si el usuario tiene al menos permiso de ver para mostrar el módulo
        opts = self.opts
        return request.user.has_perm(f'{opts.app_label}.sys_view_{opts.model_name}')




class ImagenPreviewMixin:
    """
    Mixin para mostrar miniaturas de imágenes en el listado del admin.
    Busca campos comunes de imagen o thumbnails.
    """
    def mostrar_preview(self, obj):
        # Intenta mostrar la preview generada por el sistema
        if hasattr(obj, 'preview_imagen') and obj.preview_imagen:
            return format_html('<img src="{}" width="50" height="70" style="object-fit:cover; border:1px solid #ccc;" />', obj.preview_imagen.url)
        # Intenta mostrar un campo 'imagen' genérico
        elif hasattr(obj, 'imagen') and obj.imagen:
            return format_html('<img src="{}" width="50" height="50" style="object-fit:cover; border-radius:4px;" />', obj.imagen.url)
        return "-"
    mostrar_preview.short_description = "Vista Previa"