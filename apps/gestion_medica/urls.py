from django.urls import path
from .views import *

app_name = "gestion_medica"

urlpatterns = [
    # ==========================================================================
    # 1. VISTAS PRINCIPALES / DASHBOARD
    # ==========================================================================
    path('', MedicoInicioView.as_view(), name="ruta_inicio"),
    path('lista/', MedicoListaView.as_view(), name="ruta_lista_paciente"),
    path('pacientes/crear/', MedicoCrearView.as_view(), name="ruta_crear_paciente"), # Vista de creación (placeholder)

    # ==========================================================================
    # 2. FICHA MÉDICA PRINCIPAL (INFORMACIÓN, EDICIÓN, IMPRESIÓN, Compatibilidad)
    # ==========================================================================
    # Ver Ficha (Información Detallada - Recibe ID)
    path('paciente/informacion/<int:pk>/', MedicoInfoView.as_view(), name="ruta_informacion_paciente"),
    # Editar Ficha (Datos Fisiológicos, Grupos)
    path('paciente/editar/<int:pk>/', MedicoModificarView.as_view(), name="ruta_modificar_paciente"),
    # Generar Documento de Impresión
    path('paciente/imprimir/<int:pk>/', MedicoImprimirView.as_view(), name="ruta_imprimir_ficha"),

    path('paciente/qr/<int:pk>/', MedicoImprimirQRView.as_view(), name="ruta_imprimir_qr"),

    path('compatibilidad_sanguinea/', MedicoCompatibilidadView.as_view(), name="ruta_compatibilidad_sanguinea"),


    # ==========================================================================
    # 3. CONTACTOS DE EMERGENCIA (CRUD)
    # ==========================================================================
    # Listar y Crear Contacto
    path('paciente/contacto/<int:pk>/', MedicoNumEmergView.as_view(), name="ruta_contacto_emergencia"),
    # Editar Contacto
    path('paciente/contacto/editar/<int:pk>/<int:contacto_id>/', EditarContactoView.as_view(), name="ruta_editar_contacto"),
    # Eliminar Contacto
    path('paciente/contacto/eliminar/<int:pk>/<int:contacto_id>/', EliminarContactoView.as_view(), name="ruta_eliminar_contacto"),


    # ==========================================================================
    # 4. ANTECEDENTES DEL PACIENTE (ALERGIAS, ENFERMEDADES, MEDICAMENTOS, CIRUGÍAS)
    # ==========================================================================

    # --- ENFERMEDADES (Asignación) ---
    path('paciente/enfermedad/<int:pk>/', MedicoEnfermedadView.as_view(), name="ruta_enfermedad_paciente"),
    path('paciente/enfermedad/editar/<int:pk>/<int:enfermedad_id>/', EditarEnfermedadPacienteView.as_view(), name="ruta_editar_enfermedad_paciente"),
    path('paciente/enfermedad/eliminar/<int:pk>/<int:enfermedad_id>/', EliminarEnfermedadPacienteView.as_view(), name="ruta_eliminar_enfermedad_paciente"),

    # --- ALERGIAS (Asignación) ---
    path('paciente/alergias/<int:pk>/', MedicoAlergiasView.as_view(), name="ruta_alergias_paciente"),
    path('paciente/alergias/eliminar/<int:pk>/<int:alergia_id>/', EliminarAlergiaPacienteView.as_view(), name="ruta_eliminar_alergia_paciente"),
    
    # --- MEDICAMENTOS (Asignación) ---
    path('paciente/medicamentos/<int:pk>/', MedicoMedicamentosView.as_view(), name="ruta_medicamentos_paciente"),
    path('paciente/medicamentos/editar/<int:pk>/<int:medicamento_id>/', EditarMedicamentoPacienteView.as_view(),  name="ruta_editar_medicamento_paciente"),
    path('paciente/medicamentos/eliminar/<int:pk>/<int:medicamento_id>/', EliminarMedicamentoPacienteView.as_view(), name="ruta_eliminar_medicamento_paciente"),

    # --- CIRUGÍAS (Asignación) ---
    path('paciente/cirugias/<int:pk>/', MedicoCirugiasView.as_view(), name="ruta_cirugias_paciente"),
    path('paciente/cirugias/editar/<int:pk>/<int:cirugia_id>/', EditarCirugiaPacienteView.as_view(),  name="ruta_editar_cirugia_paciente"),
    path('paciente/cirugias/eliminar/<int:pk>/<int:item_id>/', EliminarCirugiaPacienteView.as_view(), name="ruta_eliminar_cirugia_paciente"),


    # ==========================================================================
    # 5. CATÁLOGOS GLOBALES (CRUD de Mantenedores)
    # ==========================================================================
    
    # --- CATÁLOGO MEDICAMENTOS ---
    path('medicamentos/', MedicamentoListView.as_view(), name="ruta_lista_medicamentos"),
    path('medicamentos/crear/', MedicamentoCrearView.as_view(), name="ruta_crear_medicamento"),

    # --- CATÁLOGO ENFERMEDADES ---
    path('enfermedades/', EnfermedadListView.as_view(), name="ruta_lista_enfermedades"),
    path('enfermedades/crear/', EnfermedadCrearView.as_view(), name="ruta_crear_enfermedad"),

    # --- CATÁLOGO ALERGIAS ---
    path('alergias/', AlergiaListView.as_view(), name="ruta_lista_alergias"),
    path('alergias/crear/', AlergiaCrearView.as_view(), name="ruta_crear_alergia"),
    
    # --- CATÁLOGO CIRUGÍAS ---
    path('cirugias/', CirugiaListView.as_view(), name="ruta_lista_cirugias"),
    path('cirugias/crear/', CirugiaCrearView.as_view(), name="ruta_crear_cirugia"),
]