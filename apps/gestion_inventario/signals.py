from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Ubicacion, Compartimento, ProductoGlobal


@receiver(post_save, sender=Ubicacion)
def crear_compartimento_general(sender, instance, created, **kwargs):
    """
    Signal que se activa después de guardar una Ubicacion.
    
    Si la Ubicacion es nueva (created=True), crea automáticamente
    un compartimento hijo llamado "General".
    """
    if created:
        Compartimento.objects.create(
            nombre="General",
            descripcion="Compartimento principal o área general de esta ubicación. Usar para ítems que no están en una gaveta o estante específico.",
            ubicacion=instance
        )




@receiver(post_delete, sender=ProductoGlobal)
def eliminar_imagenes_producto_global(sender, instance, **kwargs):
    """
    Elimina los archivos de imagen de ProductoGlobal del almacenamiento
    cuando el objeto es eliminado.
    """
    # 'instance' es el objeto ProductoGlobal que acaba de ser eliminado
    
    # Usamos .delete(save=False) en cada campo de imagen
    if instance.imagen:
        instance.imagen.delete(save=False)
        
    if instance.imagen_thumb_medium:
        instance.imagen_thumb_medium.delete(save=False)
        
    if instance.imagen_thumb_small:
        instance.imagen_thumb_small.delete(save=False)