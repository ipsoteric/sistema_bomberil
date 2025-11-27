from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages # Opcional, para mensajes bonitos
from .models import Medicamento, FichaMedica, FichaMedicaMedicamento,FichaMedicaAlergia, FichaMedicaEnfermedad, FichaMedicaCirugia, ContactoEmergencia, Alergia,  Enfermedad, Cirugia
from .forms import MedicamentoForm, FichaMedicaForm, FichaMedicaMedicamentoForm, FichaMedicaAlergiaForm, FichaMedicaEnfermedadForm, ContactoEmergenciaForm, FichaMedicaCirugiaForm, AlergiaForm, EnfermedadForm, CirugiaForm    
from datetime import date  
from django.urls import reverse  
from django.db import IntegrityError
from django.db.models import Count
from apps.gestion_usuarios.models import Membresia
import qrcode
from io import BytesIO
import base64

# ==============================================================================
# LÓGICA DE COMPATIBILIDAD SANGUÍNEA (Donante -> Receptor)
# Esta es la base para determinar quién puede donar a quién.
# Se define como: {'TIPO_DONANTE': ['TIPO_RECEPTOR_1', 'TIPO_RECEPTOR_2', ...]}
# ==============================================================================
BLOOD_COMPATIBILITY = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'], # Donante Universal
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+'], # Receptor Universal (solo puede donar a su mismo tipo)
}

# ==============================================================================
# 1. VISTAS GENERALES Y DE PACIENTES (FICHA MÉDICA)
# ==============================================================================

# sistema_bomberil/apps/gestion_medica/views.py

class MedicoInicioView(View):
    '''Vista para ver la página principal del módulo con resumen médico'''
    def get(self, request):
        # 1. Recuperamos la estación actual de la sesión
        estacion_id = request.session.get('active_estacion_id')
        # Calcular la distribución de tipos de sangre
        # 2. Filtramos SOLO las fichas de usuarios activos en esta estación
        distribucion_qs = FichaMedica.objects.filter(
            grupo_sanguineo__isnull=False,
            # --- FILTRO MÁGICO ---
            voluntario__usuario__membresias__estacion_id=estacion_id,
            voluntario__usuario__membresias__estado='ACTIVO'
        ).values('grupo_sanguineo__nombre').annotate(
            count=Count('pk') # Contamos por ID para ser más precisos
        ).order_by('-count')

        # Calculamos el total sumando los conteos
        total_fichas_con_grupo = sum(item['count'] for item in distribucion_qs)
        # --- LÓGICA DE CÁLCULO DE PORCENTAJE (FINAL) ---
        distribucion_final = []
        # Inicializamos contadores para las tarjetas de resumen
        donor_universal_count = 0
        receptor_universal_count = 0

        if total_fichas_con_grupo > 0:
            for item in distribucion_qs:
                percentage = round((item['count'] / total_fichas_con_grupo) * 100)
                nombre_grupo = item['grupo_sanguineo__nombre']
                item['grupo_sanguineo'] = nombre_grupo 
                item['percentage'] = percentage 
                distribucion_final.append(item)

                blood_type = str(nombre_grupo).upper().strip()
                if blood_type == 'O-':
                    donor_universal_count = item['count']
                if blood_type == 'AB+':
                    receptor_universal_count = item['count']
        
        context = {
            'total_fichas_con_grupo': total_fichas_con_grupo,
            'distribucion_sumario': distribucion_final,
            'donor_universal_count': donor_universal_count,
            'receptor_universal_count': receptor_universal_count
        }
        return render(request, "gestion_medica/pages/home.html", context)
    
class MedicoListaView(View):
    def get(self, request):
        # Importación local para evitar conflictos
        from apps.gestion_usuarios.models import Membresia
        estacion_id = request.session.get('active_estacion_id')
        # 1. Obtener IDs de los voluntarios ACTIVOS en esta estación
        ids_usuarios_activos = Membresia.objects.filter(
            estacion_id=estacion_id,
            estado='ACTIVO'
        ).values_list('usuario_id', flat=True)

        # 2. Buscar las fichas usando esos IDs
        pacientes = FichaMedica.objects.filter(
            voluntario_id__in=ids_usuarios_activos
        ).select_related(
            'voluntario', 
            'voluntario__usuario'
        # --- SOLUCIÓN DEL ERROR ---
        # Le decimos explícitamente a Django que NO intente leer 'telefono'
        # de la tabla voluntario, evitando el error de columna inexistente.
        ).defer('voluntario__telefono') 
        
        return render(request, "gestion_medica/pages/lista_voluntarios.html", {'pacientes': pacientes})

class MedicoCrearView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/crear_voluntario.html")

class MedicoDatosView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/datos_paciente.html")

class MedicoVerView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/ver_voluntario.html")

class MedicoInfoView(View):
    def get(self, request, pk):
        # 1. Buscamos la ficha y optimizamos consultas
        ficha = get_object_or_404(
            FichaMedica.objects.select_related(
                'voluntario', 
                'voluntario__usuario', 
                'grupo_sanguineo', 
                'sistema_salud'
            ), pk=pk
        )
        voluntario = ficha.voluntario
        
        # 2. CÁLCULO DE EDAD MEJORADO (Igual que en imprimir)
        # Prioriza la fecha del voluntario, si no, usa la del usuario
        fecha_nac = voluntario.fecha_nacimiento or voluntario.usuario.birthdate
        
        edad = "S/I"
        if fecha_nac: 
            today = date.today()
            edad = today.year - fecha_nac.year - ((today.month, today.day) < (fecha_nac.month, fecha_nac.day))

        qr_url = request.build_absolute_uri()

        return render(request, "gestion_medica/pages/informacion_paciente.html", {
            'ficha': ficha,
            'voluntario': voluntario,
            'edad': edad, # Ahora sí lleva el cálculo correcto
            'qr_url': qr_url,
            # Usamos select_related para optimizar las relaciones
            'alergias': ficha.alergias.all().select_related('alergia'),
            'enfermedades': ficha.enfermedades.all().select_related('enfermedad'),
            'medicamentos': ficha.medicamentos.all().select_related('medicamento'),
            'cirugias': ficha.cirugias.all().select_related('cirugia'),
            'contactos': voluntario.contactos_emergencia.all()
        })

class MedicoModificarView(View):
    def get(self, request, pk):
        # 1. Buscar la ficha médica por su ID (pk)
        ficha = get_object_or_404(FichaMedica, pk=pk)
        # 2. Llenar el formulario con los datos existentes
        form = FichaMedicaForm(instance=ficha)
        return render(request, "gestion_medica/pages/modificar_voluntario.html", {
            'form': form,
            'ficha': ficha  # Para mostrar el nombre del paciente si quieres
        })
    
    def post(self, request, pk):
        # 1. Recuperar la ficha
        ficha = get_object_or_404(FichaMedica, pk=pk)

        # 2. Cargar el formulario con los datos nuevos que envió el usuario
        form = FichaMedicaForm(request.POST, instance=ficha)

        if form.is_valid():
            form.save() # ¡Guardar cambios!
            # Redirigir a la lista o al detalle (ajusta la ruta según prefieras)
            return redirect('gestion_medica:ruta_lista_paciente')

        # Si hay error, volver a mostrar el formulario con errores
        return render(request, "gestion_medica/pages/modificar_voluntario.html", {'form': form, 'ficha': ficha})

class MedicoImprimirView(View):
    def get(self, request, pk):
        # 1. Traemos la ficha con todos los datos necesarios
        ficha = get_object_or_404(
            FichaMedica.objects.select_related(
                'voluntario', 
                'voluntario__usuario',
                'voluntario__domicilio_comuna', # <--- IMPORTANTE: Esto faltaba para la comuna
                'grupo_sanguineo', 
                'sistema_salud'
            ), pk=pk
        )
        voluntario = ficha.voluntario
        
        # 2. CÁLCULO INTELIGENTE DE EDAD
        # Si no hay fecha en Voluntario, intenta buscar en Usuario
        fecha_nac = voluntario.fecha_nacimiento or voluntario.usuario.birthdate
        
        edad = "S/I" # Sin Información por defecto
        if fecha_nac: 
            today = date.today()
            # Algoritmo preciso de edad
            edad = today.year - fecha_nac.year - ((today.month, today.day) < (fecha_nac.month, fecha_nac.day))

        # 3. Enviamos todo al HTML
        return render(request, "gestion_medica/pages/imprimir_ficha.html", {
            'ficha': ficha,
            'voluntario': voluntario,
            'edad': edad, # Aquí va la edad calculada
            'alergias': ficha.alergias.all().select_related('alergia'),
            'enfermedades': ficha.enfermedades.all().select_related('enfermedad'),
            'medicamentos': ficha.medicamentos.all().select_related('medicamento'),
            'cirugias': ficha.cirugias.all().select_related('cirugia'),
            'contactos': voluntario.contactos_emergencia.all(),
            'fecha_reporte': date.today()
        })
    
class MedicoImprimirQRView(View):
    '''Genera una vista imprimible con el QR del paciente'''
    def get(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        voluntario = ficha.voluntario
        
        # 1. Datos a codificar en el QR
        # Puede ser la URL de la ficha o un JSON con datos vitales
        # Para este caso, usaremos la URL absoluta de la ficha médica
        data_qr = request.build_absolute_uri(reverse('gestion_medica:ruta_informacion_paciente', args=[pk]))
        
        # 2. Generar QR en memoria
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data_qr)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 3. Convertir imagen a Base64 para incrustar en HTML
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        # 4. Renderizar plantilla de impresión
        return render(request, "gestion_medica/pages/imprimir_qr.html", {
            'voluntario': voluntario,
            'ficha': ficha,
            'qr_image': img_str,
            'fecha_impresion': date.today()
        })

# En sistema_bomberil/apps/gestion_medica/views.py

# ... (El diccionario BLOOD_COMPATIBILITY se mantiene igual)

class MedicoCompatibilidadView(View):
    def get(self, request):
        from apps.gestion_usuarios.models import Membresia
        estacion_id = request.session.get('active_estacion_id')
        
        # 1. Obtener fichas con tipo de sangre definido (Soluciona el ValueError)
        ids_usuarios_activos = Membresia.objects.filter(
            estacion_id=estacion_id,
            estado='ACTIVO'
        ).values_list('usuario_id', flat=True)
        # PASO 2: Filtrar las fichas médicas usando esos IDs
        # Usamos 'voluntario_id__in' que es más directo y menos propenso a errores de JOIN
        fichas = FichaMedica.objects.filter(
            grupo_sanguineo__isnull=False,
            voluntario_id__in=ids_usuarios_activos  # <--- CAMBIO CLAVE
        ).select_related(
            'voluntario', 
            'voluntario__usuario'
        ).defer('voluntario__telefono').all()

        distribucion_qs = FichaMedica.objects.filter(
            grupo_sanguineo__isnull=False,
            voluntario_id__in=ids_usuarios_activos # <--- CAMBIO CLAVE TAMBIÉN AQUÍ
        ).values('grupo_sanguineo').annotate(
            count=Count('grupo_sanguineo')
        ).order_by('-count')

        distribucion = list(distribucion_qs)

        # 3. Preparar datos de receptores y Donantes (CORRECCIÓN DE 'str' object is not callable)
        recipients_by_type = {}
        for ficha in fichas:
            blood_type = str(ficha.grupo_sanguineo).upper().strip() 
            
            if blood_type not in recipients_by_type:
                recipients_by_type[blood_type] = []
            
            recipients_by_type[blood_type].append({
                'id': ficha.pk, # <--- IMPORTANTE: Usar .pk
                'nombre': ficha.voluntario.usuario.get_full_name,
                'rut': ficha.voluntario.usuario.rut,
                'avatar_url': ficha.voluntario.usuario.avatar.url if ficha.voluntario.usuario.avatar else None,
            })
        
        # 4. Generar la lista final de compatibilidad
        compatibilidad_list = []
        for ficha in fichas:
            donor_type = str(ficha.grupo_sanguineo).upper().strip()
            recipients_types = BLOOD_COMPATIBILITY.get(donor_type, [])
            
            possible_recipients = []
            for recipient_type in recipients_types:
                if recipient_type in recipients_by_type:
                    possible_recipients.extend(recipients_by_type[recipient_type])
            
            final_recipients = []
            seen_ids = set()
            for r in possible_recipients:
                if r['id'] != ficha.pk and r['id'] not in seen_ids: # <--- IMPORTANTE: Usar .pk
                    final_recipients.append(r)
                    seen_ids.add(r['id'])
            
            compatibilidad_list.append({
                'voluntario_id': ficha.pk, # <--- IMPORTANTE: Usar .pk
                'nombre_donante': ficha.voluntario.usuario.get_full_name,
                'tipo_sangre': donor_type,
                'puede_donar_a_tipos': recipients_types,
                'lista_compatibles': final_recipients,
            })
            
        return render(request, "gestion_medica/pages/compatibilidad_sanguinea.html", {
            'compatibilidad_list': compatibilidad_list,
            'distribucion': distribucion,
            'compatibilidad_map': BLOOD_COMPATIBILITY
        })
    
# Nota: La definición de la lógica de compatibilidad (BLOOD_COMPATIBILITY) 
# se debe mantener al inicio del archivo o en una ubicación accesible dentro de views.py.

# ==============================================================================
# 2. GESTIÓN DE CONTACTOS DE EMERGENCIA
# ==============================================================================

class MedicoNumEmergView(View):
    def get(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        
        # OJO: Los contactos están en el voluntario, no en la ficha médica directa
        contactos = ficha.voluntario.contactos_emergencia.all()
        form = ContactoEmergenciaForm(usuario_dueno=ficha.voluntario.usuario)
        return render(request, "gestion_medica/pages/contacto_emergencia.html", {
            'ficha': ficha,
            'contactos': contactos,
            'form': form
        })
    
    def post(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        form = ContactoEmergenciaForm(request.POST, usuario_dueno=ficha.voluntario.usuario)
        if form.is_valid():
            contacto = form.save(commit=False)
            contacto.voluntario = ficha.voluntario # Asignamos al voluntario
            contacto.save()
            return redirect('gestion_medica:ruta_contacto_emergencia', pk=pk)

        contactos = ficha.voluntario.contactos_emergencia.all()
        return render(request, "gestion_medica/pages/contacto_emergencia.html", {
            'ficha': ficha, 'contactos': contactos, 'form': form
        })

class EditarContactoView(View):
    def get(self, request, pk, contacto_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        contacto = get_object_or_404(ContactoEmergencia, id=contacto_id, voluntario=ficha.voluntario)
        
        # Pasamos usuario_dueno para que la validación del teléfono funcione igual
        form = ContactoEmergenciaForm(instance=contacto, usuario_dueno=ficha.voluntario.usuario)
        
        return render(request, "gestion_medica/pages/editar_contacto.html", {
            'ficha': ficha,
            'form': form,
            'contacto': contacto
        })

    def post(self, request, pk, contacto_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        contacto = get_object_or_404(ContactoEmergencia, id=contacto_id, voluntario=ficha.voluntario)
        
        form = ContactoEmergenciaForm(request.POST, instance=contacto, usuario_dueno=ficha.voluntario.usuario)
        
        if form.is_valid():
            form.save()
            # Al guardar, volvemos a la lista de contactos
            return redirect('gestion_medica:ruta_contacto_emergencia', pk=pk)
            
        return render(request, "gestion_medica/pages/editar_contacto.html", {
            'ficha': ficha,
            'form': form,
            'contacto': contacto
        })
    
class EliminarContactoView(View):
    def post(self, request, pk, contacto_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        contacto = get_object_or_404(ContactoEmergencia, id=contacto_id, voluntario=ficha.voluntario)
        contacto.delete()
        return redirect('gestion_medica:ruta_contacto_emergencia', pk=pk)


# ==============================================================================
# 3. GESTIÓN DE ENFERMEDADES (DEL PACIENTE)
# ==============================================================================

class MedicoEnfermedadView(View):
    def get(self, request,pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        # Buscamos las enfermedades de ESTA ficha
        enfermedad = ficha.enfermedades.all()
        form = FichaMedicaEnfermedadForm() # Formulario vacío
        return render(request, "gestion_medica/pages/enfermedad_paciente.html", {
            'ficha': ficha,  # Enviamos la ficha para poder volver
            'enfermedades': enfermedad,
            'form': form # Si quieres mostrar el formulario también
        })
    
    def post(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        form = FichaMedicaEnfermedadForm(request.POST)
        
        if form.is_valid():
            nueva_enfermedad = form.save(commit=False)
            nueva_enfermedad.ficha_medica = ficha
            
            try:
                nueva_enfermedad.save()
                return redirect('gestion_medica:ruta_enfermedad_paciente', pk=pk)
            except IntegrityError:
                form.add_error('enfermedad', 'Esta enfermedad ya está registrada.')
        
        # Si falla, recargar con errores
        enfermedades = ficha.enfermedades.all()
        return render(request, "gestion_medica/pages/enfermedad_paciente.html", {
            'ficha': ficha,
            'enfermedades': enfermedades,
            'form': form
        })

class EditarEnfermedadPacienteView(View):
    def get(self, request, pk, enfermedad_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        # Buscamos la relación específica (la enfermedad asignada)
        item = get_object_or_404(FichaMedicaEnfermedad, id=enfermedad_id, ficha_medica=ficha)
        
        form = FichaMedicaEnfermedadForm(instance=item)
        
        return render(request, "gestion_medica/pages/editar_enfermedad_paciente.html", {
            'ficha': ficha,
            'form': form,
            'item': item
        })

    def post(self, request, pk, enfermedad_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        item = get_object_or_404(FichaMedicaEnfermedad, id=enfermedad_id, ficha_medica=ficha)
        
        form = FichaMedicaEnfermedadForm(request.POST, instance=item)
        
        if form.is_valid():
            form.save()
            # Al guardar, volvemos a la lista de enfermedades
            return redirect('gestion_medica:ruta_enfermedad_paciente', pk=pk)
            
        return render(request, "gestion_medica/pages/editar_enfermedad_paciente.html", {
            'ficha': ficha,
            'form': form,
            'item': item
        })

class EliminarEnfermedadPacienteView(View):
    def post(self, request, pk, enfermedad_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        item = get_object_or_404(FichaMedicaEnfermedad, id=enfermedad_id, ficha_medica=ficha)
        item.delete()
        return redirect('gestion_medica:ruta_enfermedad_paciente', pk=pk)


# ==============================================================================
# 4. GESTIÓN DE ALERGIAS (DEL PACIENTE)
# ==============================================================================

class MedicoAlergiasView(View):
    def get(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        
        # Buscamos las alergias de ESTA ficha
        alergias = ficha.alergias.all()
        form = FichaMedicaAlergiaForm()
        return render(request, "gestion_medica/pages/alergias_paciente.html", {
            'ficha': ficha,  # Enviamos la ficha para poder volver
            'alergias': alergias,
            'form': form # Si quieres mostrar el formulario también
        })
    def post(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        form = FichaMedicaAlergiaForm(request.POST)
        
        if form.is_valid():
            nueva_alergia = form.save(commit=False)
            nueva_alergia.ficha_medica = ficha
            
            try:
                nueva_alergia.save()
                return redirect('gestion_medica:ruta_alergias_paciente', pk=pk)
            except IntegrityError:
                # Error amigable si ya existe la alergia
                form.add_error('alergia', 'El paciente ya tiene registrada esta alergia.')
        
        # Si hay error, recargamos la página con el formulario lleno
        alergias_paciente = ficha.alergias.all()
        return render(request, "gestion_medica/pages/alergias_paciente.html", {
            'ficha': ficha,
            'alergias': alergias_paciente,
            'form': form
        })
    
class EliminarAlergiaPacienteView(View):
    def post(self, request, pk, alergia_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        # Buscamos la relación específica para borrarla
        item = get_object_or_404(FichaMedicaAlergia, id=alergia_id, ficha_medica=ficha)
        item.delete()
        return redirect('gestion_medica:ruta_alergias_paciente', pk=pk)


# ==============================================================================
# 5. GESTIÓN DE MEDICAMENTOS (DEL PACIENTE)
# ==============================================================================

class MedicoMedicamentosView(View):
    def get(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        # Listamos los medicamentos que YA toma el paciente
        medicamentos_paciente = ficha.medicamentos.all()
        form = FichaMedicaMedicamentoForm()
        
        return render(request, "gestion_medica/pages/medicamentos_paciente.html", {
            'ficha': ficha,
            'medicamentos_paciente': medicamentos_paciente,
            'form': form
        })

    def post(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        form = FichaMedicaMedicamentoForm(request.POST)

        if form.is_valid():
            nuevo_medicamento = form.save(commit=False)
            nuevo_medicamento.ficha_medica = ficha

            try:
                nuevo_medicamento.save() # Intentamos guardar
                return redirect('gestion_medica:ruta_medicamentos_paciente', pk=pk)
            except IntegrityError:
                # Si ya existe, agregamos un error al formulario en lugar de romper la página
                form.add_error('medicamento', 'Este medicamento ya está asignado a este paciente.')

        # Si falló (por duplicado o datos inválidos), volvemos a mostrar la página con el error
        medicamentos_paciente = ficha.medicamentos.all()
        return render(request, "gestion_medica/pages/medicamentos_paciente.html", {
            'ficha': ficha,
            'medicamentos_paciente': medicamentos_paciente,
            'form': form
        })

class EditarMedicamentoPacienteView(View):
    def get(self, request, pk, medicamento_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        item = get_object_or_404(FichaMedicaMedicamento, id=medicamento_id, ficha_medica=ficha)
        
        form = FichaMedicaMedicamentoForm(instance=item)
        
        return render(request, "gestion_medica/pages/editar_medicamento_paciente.html", {
            'ficha': ficha,
            'form': form,
            'item': item
        })

    def post(self, request, pk, medicamento_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        item = get_object_or_404(FichaMedicaMedicamento, id=medicamento_id, ficha_medica=ficha)
        
        form = FichaMedicaMedicamentoForm(request.POST, instance=item)
        
        if form.is_valid():
            form.save()
            return redirect('gestion_medica:ruta_medicamentos_paciente', pk=pk)
            
        return render(request, "gestion_medica/pages/editar_medicamento_paciente.html", {
            'ficha': ficha,
            'form': form,
            'item': item
        })

class EliminarMedicamentoPacienteView(View):
    def post(self, request, pk, medicamento_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        item = get_object_or_404(FichaMedicaMedicamento, id=medicamento_id, ficha_medica=ficha)
        item.delete()
        return redirect('gestion_medica:ruta_medicamentos_paciente', pk=pk)


# ==============================================================================
# 6. GESTIÓN DE CIRUGÍAS (DEL PACIENTE)
# ==============================================================================

class MedicoCirugiasView(View):
    def get(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        cirugias = ficha.cirugias.all()
        form = FichaMedicaCirugiaForm()
        return render(request, "gestion_medica/pages/gestionar_cirugias.html", {
            'ficha': ficha, 'cirugias': cirugias, 'form': form
        })

    def post(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        form = FichaMedicaCirugiaForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.ficha_medica = ficha
            item.save()
            return redirect('gestion_medica:ruta_cirugias_paciente', pk=pk)

        cirugias = ficha.cirugias.all()
        return render(request, "gestion_medica/pages/gestionar_cirugias.html", {
            'ficha': ficha, 'cirugias': cirugias, 'form': form
        })
    
class EditarCirugiaPacienteView(View):
    def get(self, request, pk, cirugia_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        item = get_object_or_404(FichaMedicaCirugia, id=cirugia_id, ficha_medica=ficha)
        form = FichaMedicaCirugiaForm(instance=item)
        return render(request, "gestion_medica/pages/editar_cirugia_paciente.html", {
            'ficha': ficha,
            'form': form,
            'item': item
        })

    def post(self, request, pk, cirugia_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        item = get_object_or_404(FichaMedicaCirugia, id=cirugia_id, ficha_medica=ficha)
        form = FichaMedicaCirugiaForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect('gestion_medica:ruta_cirugias_paciente', pk=pk)
        return render(request, "gestion_medica/pages/editar_cirugia_paciente.html", {
            'ficha': ficha,
            'form': form,
            'item': item
        })

class EliminarCirugiaPacienteView(View):
    def post(self, request, pk, item_id):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        item = get_object_or_404(FichaMedicaCirugia, id=item_id, ficha_medica=ficha)
        item.delete()
        return redirect('gestion_medica:ruta_cirugias_paciente', pk=pk)


# ==============================================================================
# 7. GESTIÓN DE CATÁLOGOS (GLOBALES)
# ==============================================================================

# --- MEDICAMENTOS ---
class MedicamentoCrearView(View):
    def get(self, request):
        form = MedicamentoForm()
        return render(request, "gestion_medica/pages/crear_medicamento.html", {'form': form})
    def post(self, request):
        form = MedicamentoForm(request.POST)
        if form.is_valid():
            form.save() # ¡Guarda en la BD!
            return redirect('gestion_medica:ruta_lista_medicamentos')
        return render(request, "gestion_medica/pages/crear_medicamento.html", {'form': form})
    
class MedicamentoListView(View):
    def get(self, request):
        # Recupera los datos REALES de la base de datos
        medicamentos = Medicamento.objects.all().order_by('nombre')
        return render(request, "gestion_medica/pages/lista_medicamentos.html", {'object_list': medicamentos})
    
class MedicamentoUpdateView(View):
    def get(self, request, pk):
        medicamento = get_object_or_404(Medicamento, pk=pk)
        form = MedicamentoForm(instance=medicamento)
        return render(request, "gestion_medica/pages/crear_medicamento.html", {'form': form})

    def post(self, request, pk):
        medicamento = get_object_or_404(Medicamento, pk=pk)
        form = MedicamentoForm(request.POST, instance=medicamento)
        if form.is_valid():
            form.save() # ¡Actualiza en la BD!
            return redirect('gestion_medica:ruta_lista_medicamentos')
        return render(request, "gestion_medica/pages/crear_medicamento.html", {'form': form})

class MedicamentoDeleteView(View):
    def post(self, request, pk):
        medicamento = get_object_or_404(Medicamento, pk=pk)
        medicamento.delete() # ¡Borra de la BD!
        return redirect('gestion_medica:ruta_lista_medicamentos')

# --- ALERGIAS ---
class AlergiaListView(View):
    def get(self, request):
        alergias = Alergia.objects.all().order_by('nombre')
        return render(request, "gestion_medica/pages/lista_alergias.html", {'object_list': alergias})

class AlergiaCrearView(View):
    def get(self, request):
        form = AlergiaForm()
        return render(request, "gestion_medica/pages/crear_alergia.html", {'form': form})

    def post(self, request):
        form = AlergiaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('gestion_medica:ruta_lista_alergias')
        return render(request, "gestion_medica/pages/crear_alergia.html", {'form': form})

class AlergiaUpdateView(View):
    def get(self, request, pk):
        alergia = get_object_or_404(Alergia, pk=pk)
        form = AlergiaForm(instance=alergia)
        return render(request, "gestion_medica/pages/crear_alergia.html", {'form': form})

    def post(self, request, pk):
        alergia = get_object_or_404(Alergia, pk=pk)
        form = AlergiaForm(request.POST, instance=alergia)
        if form.is_valid():
            form.save()
            return redirect('gestion_medica:ruta_lista_alergias')
        return render(request, "gestion_medica/pages/crear_alergia.html", {'form': form})

class AlergiaDeleteView(View):
    def post(self, request, pk):
        alergia = get_object_or_404(Alergia, pk=pk)
        alergia.delete()
        return redirect('gestion_medica:ruta_lista_alergias')

# --- CIRUGÍAS ---
class CirugiaListView(View):
    def get(self, request):
        cirugias = Cirugia.objects.all().order_by('nombre')
        return render(request, "gestion_medica/pages/lista_cirugias.html", {'object_list': cirugias})

class CirugiaCrearView(View):
    def get(self, request):
        form = CirugiaForm()
        return render(request, "gestion_medica/pages/crear_cirugia.html", {'form': form})

    def post(self, request):
        form = CirugiaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('gestion_medica:ruta_lista_cirugias')
        return render(request, "gestion_medica/pages/crear_cirugia.html", {'form': form})

class CirugiaUpdateView(View):
    def get(self, request, pk):
        item = get_object_or_404(Cirugia, pk=pk)
        form = CirugiaForm(instance=item)
        return render(request, "gestion_medica/pages/crear_cirugia.html", {'form': form})

    def post(self, request, pk):
        item = get_object_or_404(Cirugia, pk=pk)
        form = CirugiaForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect('gestion_medica:ruta_lista_cirugias')
        return render(request, "gestion_medica/pages/crear_cirugia.html", {'form': form})

class CirugiaDeleteView(View):
    def post(self, request, pk):
        item = get_object_or_404(Cirugia, pk=pk)
        item.delete()
        return redirect('gestion_medica:ruta_lista_cirugias')

# --- ENFERMEDADES ---
class EnfermedadListView(View):
    def get(self, request):
        enfermedades = Enfermedad.objects.all().order_by('nombre')
        return render(request, "gestion_medica/pages/lista_enfermedades.html", {'object_list': enfermedades})

class EnfermedadCrearView(View):
    def get(self, request):
        form = EnfermedadForm()
        return render(request, "gestion_medica/pages/crear_enfermedad.html", {'form': form})
    def post(self, request):
        form = EnfermedadForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('gestion_medica:ruta_lista_enfermedades')
        return render(request, "gestion_medica/pages/crear_enfermedad.html", {'form': form})
    
class EnfermedadUpdateView(View):
    def get(self, request, pk):
        item = get_object_or_404(Enfermedad, pk=pk)
        form = EnfermedadForm(instance=item)
        return render(request, "gestion_medica/pages/crear_enfermedad.html", {'form': form})
    def post(self, request, pk):
        item = get_object_or_404(Enfermedad, pk=pk)
        form = EnfermedadForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect('gestion_medica:ruta_lista_enfermedades')
        return render(request, "gestion_medica/pages/crear_enfermedad.html", {'form': form})

class EnfermedadDeleteView(View):
    def post(self, request, pk):
        item = get_object_or_404(Enfermedad, pk=pk)
        item.delete()
        return redirect('gestion_medica:ruta_lista_enfermedades')

