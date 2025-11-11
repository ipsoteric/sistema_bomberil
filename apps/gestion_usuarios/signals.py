from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from django.core.files.base import ContentFile
from PIL import Image

from .models import Usuario
from apps.gestion_voluntarios.models import Voluntario
from apps.gestion_medica.models import FichaMedica



@receiver(post_delete, sender=Usuario)
def eliminar_avatar_usuario(sender, instance, **kwargs):
    """
    Elimina los archivos de avatar del almacenamiento
    cuando el Usuario es eliminado.
    """
    if instance.avatar:
        instance.avatar.delete(save=False)
        
    if instance.avatar_thumb_medium:
        instance.avatar_thumb_medium.delete(save=False)
        
    if instance.avatar_thumb_small:
        instance.avatar_thumb_small.delete(save=False)




@receiver(post_save, sender=Usuario)
def crear_perfiles_automaticamente(sender, instance, created, **kwargs):
    """
    Crea Voluntario (HojaDeVida) y FichaMedica vacías automáticamente 
    cuando un nuevo Usuario es creado.
    """
    if created:
        # 1. Creamos el Perfil de Voluntario
        voluntario_perfil = Voluntario.objects.create(usuario=instance)
        # 2. Creamos la Ficha Médica vacía, vinculada al Voluntario
        FichaMedica.objects.create(voluntario=voluntario_perfil)