from itertools import cycle
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image


def _preparar_imagen_para_jpeg(image):
    """
    Helper interno: Convierte cualquier imagen a RGB.
    Si tiene transparencia (RGBA/LA), le pone un fondo blanco.
    """
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        # Convertir a RGBA para asegurar que tenemos canal alfa
        image = image.convert('RGBA')
        # Crear un lienzo blanco del mismo tamaño
        background = Image.new('RGB', image.size, (255, 255, 255))
        # Pegar la imagen original sobre el blanco usando el canal alfa como máscara
        background.paste(image, mask=image.split()[3]) # 3 es el canal Alpha
        return background
    else:
        return image.convert('RGB')




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
        # 1. GESTIÓN DE TRANSPARENCIA Y MODO
        image = _preparar_imagen_para_jpeg(image)
        
        # 2. RECORTAR (CROP) 1:1
        if crop_to_square:
            width, height = image.size
            min_dim = min(width, height)
            image = image.crop((
                (width - min_dim) // 2,
                (height - min_dim) // 2,
                (width + min_dim) // 2,
                (height + min_dim) // 2
            ))
        
        # 3. REDIMENSIONAR (RESIZE)
        # Solo redimensiona si la imagen es más grande que el objetivo
        if image.width > max_dimensions[0] or image.height > max_dimensions[1]:
            image.thumbnail(max_dimensions, Image.Resampling.LANCZOS)
        
        # 4. GUARDAR EN BUFFER
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=90, optimize=True)
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
    # Usa una copia para no afectar el objeto original que podría seguir usándose
    img_copy = image_obj.copy() 
    
    # 1. GESTIÓN DE TRANSPARENCIA (Usamos el mismo helper)
    img_copy = _preparar_imagen_para_jpeg(img_copy)
    
    # 2. RESIZE
    img_copy.thumbnail(dimensions, Image.Resampling.LANCZOS)
    
    thumb_buffer = BytesIO()
    img_copy.save(thumb_buffer, format='JPEG', quality=90)
    thumb_buffer.seek(0)
    
    # Usamos el nombre de archivo completo que nos pasaron
    return ContentFile(thumb_buffer.getvalue(), name=new_filename)




def calcular_dv(cuerpo_rut):
    """
    Recibe un número (entero o string) y retorna el DV calculado (string).
    Ej: calcular_dv(12345678) -> '5'
    """
    try:
        cuerpo = str(cuerpo_rut)
        # Invertimos el número para multiplicar por la serie 2,3,4,5,6,7
        reversed_digits = map(int, reversed(cuerpo))
        factors = cycle(range(2, 8))
        
        s = sum(d * f for d, f in zip(reversed_digits, factors))
        mod = (-s) % 11
        
        if mod == 10:
            return 'K'
        if mod == 11:
            return '0'
        return str(mod)
    except ValueError:
        return None # O manejar error según necesidad