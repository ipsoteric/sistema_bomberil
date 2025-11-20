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
    # Ver Ficha (Antes era fijo, ahora recibe ID)
    path('paciente/informacion/<int:pk>/', MedicoInfoView.as_view(), name="ruta_informacion_paciente"),
    
    # Editar Ficha
    path('paciente/editar/<int:pk>/', MedicoModificarView.as_view(), name="ruta_modificar_paciente"),

    # Ver información médica de un voluntario
    path('paciente/contacto/<int:pk>/', MedicoNumEmergView.as_view(), name="ruta_contacto_emergencia"),

    # Ver información médica de un voluntario
    path('paciente/enfermedad/<int:pk>/', MedicoEnfermedadView.as_view(), name="ruta_enfermedad_paciente"),

    path('paciente/enfermedad/editar/<int:pk>/<int:enfermedad_id>/', EditarEnfermedadPacienteView.as_view(), name="ruta_editar_enfermedad_paciente"),

    path('paciente/enfermedad/eliminar/<int:pk>/<int:enfermedad_id>/', EliminarEnfermedadPacienteView.as_view(), name="ruta_eliminar_enfermedad_paciente"),

    # Ver información médica de un voluntario
    path('paciente/alergias/<int:pk>/', MedicoAlergiasView.as_view(), name="ruta_alergias_paciente"),

    path('paciente/alergias/eliminar/<int:pk>/<int:alergia_id>/', EliminarAlergiaPacienteView.as_view(), name="ruta_eliminar_alergia_paciente"),

    # Ver información médica de un voluntario
    path('paciente/informacion/<int:pk>/', MedicoInfoView.as_view(), name="ruta_informacion_paciente"),

    # Modificar información médica de un voluntario
    path('editar', MedicoModificarView.as_view(), name="ruta_modificar_paciente"),

    # Crear información médica de un voluntario
    path('pacientes/crear/', MedicoCrearView.as_view(), name="ruta_crear_paciente"),

    # NUEVA: Vista de Impresión
    path('paciente/imprimir/<int:pk>/', MedicoImprimirView.as_view(), name="ruta_imprimir_ficha"),
    
    # Rutas para Medicamentos DEL PACIENTE (No el catálogo global)
    path('paciente/medicamentos/<int:pk>/', MedicoMedicamentosView.as_view(), name="ruta_medicamentos_paciente"),
    
    path('paciente/medicamentos/editar/<int:pk>/<int:medicamento_id>/', EditarMedicamentoPacienteView.as_view(),  name="ruta_editar_medicamento_paciente"),

    path('paciente/medicamentos/eliminar/<int:pk>/<int:medicamento_id>/', EliminarMedicamentoPacienteView.as_view(), name="ruta_eliminar_medicamento_paciente"),

    path('paciente/contacto/editar/<int:pk>/<int:contacto_id>/', EditarContactoView.as_view(), name="ruta_editar_contacto"),

    #Ruta Contacto (Eliminar faltaba)
    path('paciente/contacto/eliminar/<int:pk>/<int:contacto_id>/', EliminarContactoView.as_view(), name="ruta_eliminar_contacto"),

    # Rutas de Cirugías (Paciente)
    path('paciente/cirugias/<int:pk>/', MedicoCirugiasView.as_view(), name="ruta_cirugias_paciente"),

    path('paciente/cirugias/editar/<int:pk>/<int:cirugia_id>/', 
         EditarCirugiaPacienteView.as_view(), 
         name="ruta_editar_cirugia_paciente"),
    
    path('paciente/cirugias/eliminar/<int:pk>/<int:item_id>/', EliminarCirugiaPacienteView.as_view(), name="ruta_eliminar_cirugia_paciente"),

    # --- CATÁLOGO DE ALERGIAS ---
    path('alergias/', AlergiaListView.as_view(), name="ruta_lista_alergias"),
    
    path('alergias/crear/', AlergiaCrearView.as_view(), name="ruta_crear_alergia"),

    # --- CATÁLOGO DE ENFERMEDADES ---
    path('enfermedades/', EnfermedadListView.as_view(), name="ruta_lista_enfermedades"),
    
    path('enfermedades/crear/', EnfermedadCrearView.as_view(), name="ruta_crear_enfermedad"),

    # Adicion de medicamentos
    path('medicamentos/crear/', MedicamentoCrearView.as_view(), name="ruta_crear_medicamento"),

    # Lista de medicamentos
    path('medicamentos/', MedicamentoListView.as_view(), name="ruta_lista_medicamentos"),

    # --- CATÁLOGO DE CIRUGÍAS ---
    path('cirugias/', CirugiaListView.as_view(), name="ruta_lista_cirugias"),
    
    path('cirugias/crear/', CirugiaCrearView.as_view(), name="ruta_crear_cirugia"),
        
    ]   