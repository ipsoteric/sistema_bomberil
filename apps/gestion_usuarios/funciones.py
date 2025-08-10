import secrets
import string
import uuid
import os
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile


def generar_contraseña_segura(longitud=12):
    """Genera una contraseña aleatoria y segura."""
    alfabeto = string.ascii_letters + string.digits + string.punctuation
    contraseña = ''.join(secrets.choice(alfabeto) for i in range(longitud))
    return contraseña



def generar_ruta_subida_avatar(instance, filename):
    '''
    Genera la ruta final. Se usa un UUID si el id no está disponible.
    '''
    if instance.id:
        return f"usuarios/avatar/user_{instance.id}/avatar.jpg"
    return f"usuarios/avatar/temp/{uuid.uuid4()}.jpg"



def generar_avatar_thumbnail(image_obj : str, dimensions : tuple, suffix : str):
    '''Función que genera thumbnail en memoria. Retorna un ContentFile'''
    image_obj = image_obj.convert('RGB')
    image_obj.thumbnail(dimensions, Image.Resampling.LANCZOS)
    thumb_buffer = BytesIO()
    image_obj.save(thumb_buffer, format='JPEG', quality=90)
    return ContentFile(thumb_buffer.getvalue(), name=f"avatar{suffix}.jpg")



def recortar_y_redimensionar_avatar(image_field):
    """
    Recorta la imagen a un cuadrado y la redimensiona a 500x500 píxeles si es necesario.
    """
    if not image_field:
        return None
    
    # Abrir el archivo directamente desde S3 (o el FileField)
    with Image.open(image_field) as image:
        image = image.convert('RGB')
        width, height = image.size
        min_dim = min(width, height)
        image = image.crop((
            (width - min_dim) // 2,
            (height - min_dim) // 2,
            (width + min_dim) // 2,
            (height + min_dim) // 2
        ))
        if image.size[0] > 500 or image.size[1] > 500:
            image.thumbnail((500, 500), Image.Resampling.LANCZOS)
        
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)
        return ContentFile(buffer.getvalue(), name=os.path.basename(image_field.name))