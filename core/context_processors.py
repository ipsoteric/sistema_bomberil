from .settings import MODULOS

def modulo_actual(request):
    # Obtiene el nombre de la app desde la URL resuelta
    app_name = getattr(request.resolver_match, 'app_name', None)
    
    # Asigna el nombre legible o un valor por defecto
    nombre_modulo = MODULOS.get(app_name, 'Bomberil')
    
    return {'nombre_modulo': nombre_modulo}