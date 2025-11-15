from django.db.models.signals import post_save, post_delete
from django.db.models import Sum
from django.dispatch import receiver
from .models import Ubicacion, Compartimento, ProductoGlobal, Activo, RegistroUsoActivo


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




def recalcular_horas_totales_activo(activo_id):
    """
    Recalcula el campo 'horas_uso_totales' para un Activo específico
    sumando todos sus Registros de Uso.
    """
    try:
        # Obtenemos la instancia del activo
        activo = Activo.objects.get(id=activo_id)
        
        # Sumamos todas las 'horas_registradas' de sus registros
        # Si no hay registros, 'total' será None, por eso usamos 'or 0.00'
        total_horas = RegistroUsoActivo.objects.filter(activo=activo).aggregate(
            total=Sum('horas_registradas')
        )['total'] or 0.00
        
        # Actualizamos el campo en el modelo Activo
        # Usamos update_fields para ser eficientes y evitar otros signals
        activo.horas_uso_totales = total_horas
        activo.save(update_fields=['horas_uso_totales'])
        
    except Activo.DoesNotExist:
        # El activo no existe (quizás se está borrando), no hacemos nada.
        pass




@receiver(post_save, sender=RegistroUsoActivo)
def on_registro_uso_save(sender, instance, created, **kwargs):
    """
    Se dispara después de crear o EDITAR un RegistroUsoActivo.
    """
    # Llama a la función de recálculo
    recalcular_horas_totales_activo(instance.activo.id)




@receiver(post_delete, sender=RegistroUsoActivo)
def on_registro_uso_delete(sender, instance, **kwargs):
    """
    Se dispara después de ELIMINAR un RegistroUsoActivo.
    """
    # Llama a la función de recálculo
    recalcular_horas_totales_activo(instance.activo.id)