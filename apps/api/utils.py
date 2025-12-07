from rest_framework import serializers
from apps.gestion_usuarios.models import Membresia


def obtener_contexto_bomberil(user):
    """
    Lógica centralizada para obtener estación y permisos.
    Retorna un diccionario con la data o lanza ValidationError.
    """
    data = {}
    
    # 1. Datos básicos
    data['usuario'] = {
        'id': user.id,
        'rut': user.rut,
        'email': user.email,
        'nombre_completo': user.get_full_name,
        'avatar': user.avatar.url if user.avatar else None,
    }

    # 2. Membresía Activa
    membresia_activa = Membresia.objects.filter(
        usuario=user, 
        estado=Membresia.Estado.ACTIVO
    ).select_related('estacion').prefetch_related('roles__permisos').first()

    if membresia_activa:
        data['estacion'] = {
            'id': membresia_activa.estacion.id,
            'nombre': membresia_activa.estacion.nombre,
        }
        
        permisos_set = set()
        for rol in membresia_activa.roles.all():
            for permiso in rol.permisos.all():
                permisos_set.add(permiso.codename)
        
        data['permisos'] = list(permisos_set)
        data['membresia_id'] = membresia_activa.id
    else:
        # AQUÍ: Si intentan refrescar y ya no tienen membresía, fallará.
        raise serializers.ValidationError(
            {"detail": "Tu estación activa ha sido revocada o finalizada."}
        )
    
    return data