from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image



def crear_permiso_de_acceso_al_modulo(app_config):
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




def procesar_imagen_en_memoria(
    image_field, 
    max_dimensions: tuple, 
    new_filename: str,
    crop_to_square: bool = False
):
    """
    Procesa una imagen en memoria: la recorta (opcional), la redimensiona 
    y la guarda como JPEG.
    Retorna un ContentFile listo para ser guardado.
    """
    if not image_field:
        return None
    
    with Image.open(image_field) as image:
        image = image.convert('RGB')
        
        if crop_to_square:
            width, height = image.size
            min_dim = min(width, height)
            image = image.crop((
                (width - min_dim) // 2,
                (height - min_dim) // 2,
                (width + min_dim) // 2,
                (height + min_dim) // 2
            ))
        
        # Redimensionar si supera las dimensiones máximas
        image.thumbnail(max_dimensions, Image.Resampling.LANCZOS)
        
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)
        
        # Devolver el ContentFile con el nuevo nombre de archivo basado en UUID
        return ContentFile(buffer.getvalue(), name=new_filename)




def generar_thumbnail_en_memoria(
    image_obj: Image.Image, 
    dimensions: tuple, 
    new_filename: str
):
    """
    Función genérica que genera un thumbnail en memoria. 
    Recibe un objeto Pillow Image y el nombre de archivo deseado.
    Retorna un ContentFile.
    """
    img_copy = image_obj.copy() 
    img_copy = img_copy.convert('RGB')
    img_copy.thumbnail(dimensions, Image.Resampling.LANCZOS)
    
    thumb_buffer = BytesIO()
    img_copy.save(thumb_buffer, format='JPEG', quality=90)
    thumb_buffer.seek(0)
    
    # Usamos el nombre de archivo completo que nos pasaron
    return ContentFile(thumb_buffer.getvalue(), name=new_filename)