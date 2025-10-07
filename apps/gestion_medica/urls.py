from django.urls import path
from .views import *

'''
FUNCIONALIDADES A DESARROLLAR EN EL MÓDULO "GESTIÓN MÉDICA"

_ Medicamentos (secundario): Listar, agregar, modificar y eliminar
_ Enfermedades (secundario): Listar, agregar, modificar y eliminar

_ Pacientes (primario):
    Lista
        campos por ver
    
    Ver paciente:
        información personal específica, imagen, teléfono primario, enfermedades, medicamentos y operaciones

    "Agregar paciente" no aplica aquí. Los voluntarios son ingresados en otro módulo
    
    Modificar paciente:
        - modificar información médica (grupo sang, presión art, altura, peso, etc.)
        - asignar enfermedades padecidas (varios)
        - asignar medicamentos (varios)
        - asignar operaciones quirúrgicas
    
_ Generar ficha médica en formato PDF
_ Exportar listado de pacientes (excel, .csv, etc.)
'''

app_name = "gestion_medica"

urlpatterns = [
    # Página Inicial de la gestión médica
    path('', MedicoInicioView.as_view(), name="ruta_inicio"),

    # Lista de pacientes (información médica resumida de los voluntarios)
    path('lista/', MedicoListaView.as_view(), name="ruta_lista_paciente"),

    # Datos de pacientes (información médica de los voluntarios)
    path('paciente/datos/', MedicoDatosView.as_view(), name="ruta_datos_paciente"),

    # Ver información médica de un voluntario
    path('paciente/contacto', MedicoNumEmergView.as_view(), name="ruta_contacto_emergencia"),

    # Ver información médica de un voluntario
    path('paciente/enfermedad', MedicoEnfermedadView.as_view(), name="ruta_enfermedad_paciente"),

    # Ver información médica de un voluntario
    path('paciente/alergias', MedicoAlergiasView.as_view(), name="ruta_alergias_paciente"),

    # Ver información médica de un voluntario
    path('paciente/informacion', MedicoInfoView.as_view(), name="ruta_informacion_paciente"),

    # Modificar información médica de un voluntario
    path('editar', MedicoModificarView.as_view(), name="ruta_modificar_paciente"),

    # Crear información médica de un voluntario
    path('pacientes/crear/', MedicoCrearView.as_view(), name="ruta_crear_paciente"),

    # Adicion de medicamentos
    path('medicamentos/crear/', MedicamentoCrearView.as_view(), name="ruta_crear_medicamento"),

    # Lista de medicamentos
    path('medicamentos/', MedicamentoListView.as_view(), name="ruta_lista_medicamentos"),
]