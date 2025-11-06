from django.urls import path
from .views import *

'''
FUNCIONALIDADES A DESARROLLAR EN EL MÓDULO "GESTION DE VOLUNTARIOS"

_ Profesiones (secundario): Listar, agregar, modificar y eliminar
_ Rangos bomberiles (secundario): Lista, agregar, modificar y eliminar
_ Voluntarios (primario): 
    Lista (filtro sólo estación, global, reciente)
        campos por ver

    Ver voluntario
        información personal, imagen, teléfonos, estación actual, experiencia bomberil, actividades, reconocimientos, sanciones, logros generales y especiales

    Agregar nuevo voluntario
        campos: pendiente

    Modificar voluntario
        _ modificar información personal
        _ asignar experiencia bomberil
        _ asignar reconocimientos
        _ asignar actividades
        _ asignar logros generales
        _ asignar logros especiales
        _ asignar sanciones
        _ asignar expulsiones
    
    Eliminar voluntario
        _ Requiere una confirmación adicional tipo AWS y permisos especiales

_ Generar Hoja de vida en formato PDF (Aún no sé si hacerlo en formato word o con una plantilla HTML convertida a PDF. De momento prefiero HTML.)
_ Trasladar voluntario a otra compañía para ceder su gestión
_ Exportar listado de voluntarios (excel, .csv, etc.)
'''

app_name = "gestion_voluntarios"

urlpatterns = [
    # Página Inicial de la gestión de inventario
    path('', VoluntariosInicioView.as_view(), name="ruta_inicio"),

    # Lista de voluntarios de la compañía
    path('lista/', VoluntariosListaView.as_view(), name="ruta_lista_voluntarios"),

    # Ingresar voluntario al sistema
    path('crear/', VoluntariosCrearView.as_view(), name="ruta_crear_voluntario"),

    # Ver información de un voluntario
    path('voluntario/<int:id>/', VoluntariosVerView.as_view(), name="ruta_ver"),

    # Modificar información de un voluntario
    path('voluntario/<int:id>/editar', VoluntariosModificarView.as_view(), name="ruta_modificar"),

    # Eliminar voluntario del sistema (A EVALUAR. PROBABLEMENTE TERMINE QUITANDO ESTE ENDPOINT)
    path('voluntario/<int:id>/editar', VoluntariosEliminarView.as_view(), name="ruta_eliminar"),



    # Lista de cargos/rangos bomberiles
    path('lista/', CargosListaView.as_view(), name="ruta_cargos_lista"),

    # Ingresar cargo al sistema
    path('crear/', CargosCrearView.as_view(), name="ruta_cargos_crear"),

    # Modificar cargo
    path('voluntario/<int:id>/editar', CargosModificarView.as_view(), name="ruta_cargos_modificar"),

    # Eliminar cargo (PROTEGIDO)
    path('voluntario/<int:id>/eliminar', CargosEliminarView.as_view(), name="ruta_cargos_eliminar"),
]