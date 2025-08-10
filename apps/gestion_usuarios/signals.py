from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from django.core.files.base import ContentFile
from PIL import Image

from .models import Usuario
from .funciones import recortar_y_redimensionar_avatar, generar_avatar_thumbnail



@receiver(pre_delete, sender=Usuario)
def eliminar_archivos_de_avatar(sender, instance, **kwargs):
    """
    Elimina todos los archivos del avatar al borrar el usuario.
    """
    if instance.avatar:
        instance.avatar.delete(save=False)

    if instance.avatar_thumb_small:
        instance.avatar_thumb_small.delete(save=False)
    if instance.avatar_thumb_medium:
        instance.avatar_thumb_medium.delete(save=False)