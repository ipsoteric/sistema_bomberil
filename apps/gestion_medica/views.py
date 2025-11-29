import base64
import qrcode
from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse  
from django.db import IntegrityError
from django.db.models import Count, ProtectedError
from datetime import date

# --- Imports del Proyecto ---
from .models import (
    Medicamento, FichaMedica, FichaMedicaMedicamento, FichaMedicaAlergia, 
    FichaMedicaEnfermedad, FichaMedicaCirugia, ContactoEmergencia, 
    Alergia, Enfermedad, Cirugia
)
from .forms import (
    MedicamentoForm, FichaMedicaForm, FichaMedicaMedicamentoForm, 
    FichaMedicaAlergiaForm, FichaMedicaEnfermedadForm, ContactoEmergenciaForm, 
    FichaMedicaCirugiaForm, AlergiaForm, EnfermedadForm, CirugiaForm
)  
from .utils import BLOOD_COMPATIBILITY
from apps.common.mixins import BaseEstacionMixin, AuditoriaMixin
from apps.gestion_usuarios.models import Membresia
from apps.gestion_voluntarios.models import Voluntario


# ==============================================================================
# 1. VISTAS GENERALES Y DE PACIENTES (FICHA MÉDICA)
# ==============================================================================
class MedicoInicioView(BaseEstacionMixin, View):
    """
    Dashboard principal del módulo médico.
    """
    def get(self, request):
        estacion = self.estacion_activa

        # Distribución de grupos sanguíneos en la estación
        distribucion_qs = FichaMedica.objects.filter(
            grupo_sanguineo__isnull=False,
            voluntario__usuario__membresias__estacion=estacion,
            voluntario__usuario__membresias__estado='ACTIVO'
        ).values('grupo_sanguineo__nombre').annotate(
            count=Count('pk')
        ).order_by('-count')

        total_fichas = sum(item['count'] for item in distribucion_qs)
        distribucion_final = []
        donor_universal_count = 0
        receptor_universal_count = 0

        if total_fichas > 0:
            for item in distribucion_qs:
                percentage = round((item['count'] / total_fichas) * 100)
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
            'total_fichas_con_grupo': total_fichas,
            'distribucion_sumario': distribucion_final,
            'donor_universal_count': donor_universal_count,
            'receptor_universal_count': receptor_universal_count
        }
        return render(request, "gestion_medica/pages/home.html", context)




class MedicoListaView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Listado de personal con ficha médica disponible.
    """
    permission_required = 'gestion_medica.accion_gestion_medica_ver_fichas_medicas'

    def get(self, request):
        # 1. Filtramos usuarios activos de la estación
        # Optimizamos la consulta para traer datos del voluntario y usuario de una vez
        pacientes = FichaMedica.objects.select_related(
            'voluntario', 
            'voluntario__usuario'
        ).filter(
            voluntario__usuario__membresias__estacion=self.estacion_activa,
            voluntario__usuario__membresias__estado='ACTIVO'
        ).defer('voluntario__telefono') # Evitamos cargar campos pesados si no se usan
        
        return render(request, "gestion_medica/pages/lista_voluntarios.html", {'pacientes': pacientes})




class MedicoInfoView(BaseEstacionMixin, PermissionRequiredMixin, AuditoriaMixin, View):
    """
    Ficha clínica detallada (Solo Lectura).
    """
    permission_required = 'gestion_medica.accion_gestion_medica_ver_fichas_medicas'

    def get(self, request, pk):
        # 1. Recuperación segura (pertenece a la estación)
        ficha = get_object_or_404(
            FichaMedica.objects.select_related(
                'voluntario', 
                'voluntario__usuario', 
                'grupo_sanguineo', 
                'sistema_salud'
            ).prefetch_related(
                'alergias__alergia',
                'enfermedades__enfermedad',
                'medicamentos__medicamento',
                'cirugias__cirugia',
                'voluntario__contactos_emergencia' # Relación inversa desde Voluntario
            ), 
            pk=pk,
            voluntario__usuario__membresias__estacion=self.estacion_activa
        )
        voluntario = ficha.voluntario
        
        # 2. Cálculo de Edad
        fecha_nac = voluntario.fecha_nacimiento or voluntario.usuario.birthdate
        edad = "S/I"
        if fecha_nac: 
            today = date.today()
            edad = today.year - fecha_nac.year - ((today.month, today.day) < (fecha_nac.month, fecha_nac.day))

        qr_url = request.build_absolute_uri()
        
        # Auditoría de acceso (opcional, si es muy sensible)
        # self.auditar('Consultar', voluntario.usuario, 'Visualización de ficha médica detallada', voluntario.usuario.get_full_name)

        return render(request, "gestion_medica/pages/informacion_paciente.html", {
            'ficha': ficha,
            'voluntario': voluntario,
            'edad': edad,
            'qr_url': qr_url,
            'alergias': ficha.alergias.all(),
            'enfermedades': ficha.enfermedades.all(),
            'medicamentos': ficha.medicamentos.all(),
            'cirugias': ficha.cirugias.all(),
            'contactos': voluntario.contactos_emergencia.all()
        })




class MedicoModificarView(BaseEstacionMixin, AuditoriaMixin, PermissionRequiredMixin, View):
    """
    Edición de datos fisiológicos básicos (Peso, Altura, Grupo, etc.)
    """
    permission_required = 'gestion_medica.accion_gestion_medica_gestionar_fichas_medicas'

    def get_ficha(self, pk):
        return get_object_or_404(
            FichaMedica, 
            pk=pk, 
            voluntario__usuario__membresias__estacion=self.estacion_activa
        )

    def get(self, request, pk):
        ficha = self.get_ficha(pk)
        form = FichaMedicaForm(instance=ficha)
        return render(request, "gestion_medica/pages/modificar_voluntario.html", {
            'form': form,
            'ficha': ficha 
        })
    
    def post(self, request, pk):
        ficha = self.get_ficha(pk)
        form = FichaMedicaForm(request.POST, instance=ficha)

        if form.is_valid():
            try:
                form.save()
                self.auditar(
                    verbo="actualizó los datos médicos de",
                    objetivo=ficha.voluntario.usuario,
                    objetivo_repr=ficha.voluntario.usuario.get_full_name,
                    detalles={'cambios': 'Actualización de signos vitales/grupo sanguíneo'}
                )
                messages.success(request, f"Datos médicos de {ficha.voluntario.usuario.get_full_name} actualizados.")
                return redirect('gestion_medica:ruta_informacion_paciente', pk=pk)
            except Exception as e:
                messages.error(request, f"Error crítico al actualizar la ficha: {str(e)}")

        messages.error(request, "Error al actualizar la ficha. Verifique los datos.")
        return render(request, "gestion_medica/pages/modificar_voluntario.html", {'form': form, 'ficha': ficha})




# ==============================================================================
# 2. REPORTES E IMPRESIÓN
# ==============================================================================
class MedicoImprimirView(BaseEstacionMixin, PermissionRequiredMixin, AuditoriaMixin, View):
    permission_required = 'gestion_medica.accion_gestion_medica_generar_reportes'

    def get(self, request, pk):
        ficha = get_object_or_404(
            FichaMedica.objects.select_related(
                'voluntario', 'voluntario__usuario', 'voluntario__domicilio_comuna', 
                'grupo_sanguineo', 'sistema_salud'
            ).prefetch_related(
                'alergias__alergia', 'enfermedades__enfermedad', 'medicamentos__medicamento', 
                'cirugias__cirugia', 'voluntario__contactos_emergencia'
            ), 
            pk=pk,
            voluntario__usuario__membresias__estacion=self.estacion_activa
        )
        
        # Auditoría de descarga
        self.auditar(
            verbo="generó reporte clínico impreso de",
            objetivo=ficha.voluntario.usuario,
            objetivo_repr=ficha.voluntario.usuario.get_full_name,
            detalles={'accion': 'Impresión Ficha Clínica'}
        )

        voluntario = ficha.voluntario
        fecha_nac = voluntario.fecha_nacimiento or voluntario.usuario.birthdate
        edad = "S/I"
        if fecha_nac: 
            today = date.today()
            edad = today.year - fecha_nac.year - ((today.month, today.day) < (fecha_nac.month, fecha_nac.day))

        return render(request, "gestion_medica/pages/imprimir_ficha.html", {
            'ficha': ficha,
            'voluntario': voluntario,
            'edad': edad,
            'alergias': ficha.alergias.all(),
            'enfermedades': ficha.enfermedades.all(),
            'medicamentos': ficha.medicamentos.all(),
            'cirugias': ficha.cirugias.all(),
            'contactos': voluntario.contactos_emergencia.all(),
            'fecha_reporte': date.today()
        })




class MedicoImprimirQRView(BaseEstacionMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_medica.accion_gestion_medica_generar_reportes'

    def get(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk, voluntario__usuario__membresias__estacion=self.estacion_activa)
        
        data_qr = request.build_absolute_uri(reverse('gestion_medica:ruta_informacion_paciente', args=[pk]))
        
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(data_qr)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return render(request, "gestion_medica/pages/imprimir_qr.html", {
            'voluntario': ficha.voluntario,
            'ficha': ficha,
            'qr_image': img_str,
            'fecha_impresion': date.today()
        })




class MedicoCompatibilidadView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Matriz de compatibilidad sanguínea local.
    """
    permission_required = 'gestion_medica.accion_gestion_medica_ver_fichas_medicas'

    def get(self, request):
        estacion = self.estacion_activa
        
        # 1. Obtenemos solo fichas con grupo sanguíneo y de la estación activa
        fichas = FichaMedica.objects.filter(
            grupo_sanguineo__isnull=False,
            voluntario__usuario__membresias__estacion=estacion,
            voluntario__usuario__membresias__estado='ACTIVO'
        ).select_related('voluntario', 'voluntario__usuario', 'grupo_sanguineo').defer('voluntario__telefono')

        # 2. Distribución para gráfico/resumen
        distribucion = fichas.values('grupo_sanguineo__nombre').annotate(count=Count('grupo_sanguineo')).order_by('-count')

        # 3. Mapeo de receptores en memoria
        recipients_by_type = {}
        for ficha in fichas:
            blood_type = str(ficha.grupo_sanguineo.nombre).upper().strip()
            
            if blood_type not in recipients_by_type:
                recipients_by_type[blood_type] = []
            
            recipients_by_type[blood_type].append({
                'id': ficha.pk,
                'nombre': ficha.voluntario.usuario.get_full_name,
                'rut': ficha.voluntario.usuario.rut,
                'avatar_url': ficha.voluntario.usuario.avatar.url if ficha.voluntario.usuario.avatar else None,
            })
        
        # 4. Generar lista de match
        compatibilidad_list = []
        for ficha in fichas:
            donor_type = str(ficha.grupo_sanguineo.nombre).upper().strip()
            # Obtenemos a quiénes puede donar este usuario
            recipients_types = BLOOD_COMPATIBILITY.get(donor_type, [])
            
            possible_recipients = []
            for recipient_type in recipients_types:
                if recipient_type in recipients_by_type:
                    possible_recipients.extend(recipients_by_type[recipient_type])
            
            # Filtramos para no donarse a sí mismo
            final_recipients = [r for r in possible_recipients if r['id'] != ficha.pk]
            
            compatibilidad_list.append({
                'voluntario_id': ficha.pk,
                'nombre_donante': ficha.voluntario.usuario.get_full_name,
                'tipo_sangre': donor_type,
                'puede_donar_a_tipos': recipients_types,
                'lista_compatibles': final_recipients,
            })
            
        return render(request, "gestion_medica/pages/compatibilidad_sanguinea.html", {
            'compatibilidad_list': compatibilidad_list,
            'distribucion': list(distribucion),
            'compatibilidad_map': BLOOD_COMPATIBILITY
        })




# ==============================================================================
# 3. GESTIÓN DE SUB-ELEMENTOS (CRUDs ESPECÍFICOS)
# ==============================================================================

# --- HELPERS PARA MIXINS Y REPETICIÓN ---
class SubElementoMedicoBaseView(BaseEstacionMixin, AuditoriaMixin, PermissionRequiredMixin, View):
    """Clase base para Contactos, Alergias, Enfermedades, etc."""
    permission_required = 'gestion_medica.accion_gestion_medica_gestionar_fichas_medicas'

    def get_ficha(self, pk):
        return get_object_or_404(
            FichaMedica, 
            pk=pk, 
            voluntario__usuario__membresias__estacion=self.estacion_activa
        )
   



# --- CONTACTOS DE EMERGENCIA ---
class MedicoNumEmergView(SubElementoMedicoBaseView):
    def get(self, request, pk):
        ficha = self.get_ficha(pk)
        contactos = ficha.voluntario.contactos_emergencia.all()
        form = ContactoEmergenciaForm(usuario_dueno=ficha.voluntario.usuario)
        return render(request, "gestion_medica/pages/contacto_emergencia.html", {
            'ficha': ficha, 'contactos': contactos, 'form': form
        })
    
    def post(self, request, pk):
        ficha = self.get_ficha(pk)
        form = ContactoEmergenciaForm(request.POST, usuario_dueno=ficha.voluntario.usuario)
        if form.is_valid():
            try:
                contacto = form.save(commit=False)
                contacto.voluntario = ficha.voluntario
                contacto.save()

                self.auditar("agregó un contacto de emergencia a", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'contacto': contacto.nombre_completo})
                messages.success(request, "Contacto de emergencia agregado.")
                return redirect('gestion_medica:ruta_contacto_emergencia', pk=pk)
            except Exception as e:
                messages.error(request, f"Error al guardar el contacto: {str(e)}")

        messages.error(request, "Error al guardar el contacto.")
        return render(request, "gestion_medica/pages/contacto_emergencia.html", {
            'ficha': ficha, 'contactos': ficha.voluntario.contactos_emergencia.all(), 'form': form
        })




class EditarContactoView(SubElementoMedicoBaseView):
    def get(self, request, pk, contacto_id):
        ficha = self.get_ficha(pk)
        contacto = get_object_or_404(ContactoEmergencia, id=contacto_id, voluntario=ficha.voluntario)
        form = ContactoEmergenciaForm(instance=contacto, usuario_dueno=ficha.voluntario.usuario)
        return render(request, "gestion_medica/pages/editar_contacto.html", {'ficha': ficha, 'form': form, 'contacto': contacto})

    def post(self, request, pk, contacto_id):
        ficha = self.get_ficha(pk)
        contacto = get_object_or_404(ContactoEmergencia, id=contacto_id, voluntario=ficha.voluntario)
        form = ContactoEmergenciaForm(request.POST, instance=contacto, usuario_dueno=ficha.voluntario.usuario)
        
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Contacto actualizado.")
                return redirect('gestion_medica:ruta_contacto_emergencia', pk=pk)
            except Exception as e:
                messages.error(request, f"Error al guardar los cambios: {e}")
        
        messages.error(request, "Error al actualizar el contacto. Revisa los datos.")
        return render(request, "gestion_medica/pages/editar_contacto.html", {'ficha': ficha, 'form': form, 'contacto': contacto})




class EliminarContactoView(SubElementoMedicoBaseView):
    def post(self, request, pk, contacto_id):
        ficha = self.get_ficha(pk)
        contacto = get_object_or_404(ContactoEmergencia, id=contacto_id, voluntario=ficha.voluntario)
        nombre = contacto.nombre_completo

        try:
            contacto.delete()
            self.auditar("eliminó un contacto de emergencia de", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'contacto_eliminado': nombre})
            messages.success(request, "Contacto eliminado correctamente.")
        except Exception as e:
            messages.error(request, f"Error al eliminar el contacto: {str(e)}")
        return redirect('gestion_medica:ruta_contacto_emergencia', pk=pk)




# --- ENFERMEDADES ---
class MedicoEnfermedadView(SubElementoMedicoBaseView):
    def get(self, request, pk):
        ficha = self.get_ficha(pk)
        return render(request, "gestion_medica/pages/enfermedad_paciente.html", {
            'ficha': ficha, 'enfermedades': ficha.enfermedades.select_related('enfermedad'), 'form': FichaMedicaEnfermedadForm()
        })
    
    def post(self, request, pk):
        ficha = self.get_ficha(pk)
        form = FichaMedicaEnfermedadForm(request.POST)
        
        if form.is_valid():
            item = form.save(commit=False)
            item.ficha_medica = ficha
            try:
                item.save()
                self.auditar("registró una enfermedad/condición a", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'enfermedad': item.enfermedad.nombre})
                messages.success(request, "Enfermedad registrada en la ficha.")
                return redirect('gestion_medica:ruta_enfermedad_paciente', pk=pk)
            except IntegrityError:
                form.add_error('enfermedad', 'Esta enfermedad ya está registrada.')
            except Exception as e:
                messages.error(request, f"Error al guardar los cambios: {e}")
        
        messages.error(request, "Error al registrar enfermedad.")
        return render(request, "gestion_medica/pages/enfermedad_paciente.html", {
            'ficha': ficha, 'enfermedades': ficha.enfermedades.all(), 'form': form
        })




class EditarEnfermedadPacienteView(View): # NO SE USA. PENDIENTE DE ELIMINAR
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
            messages.success(request, "Condición actualizada correctamente.")
            # Al guardar, volvemos a la lista de enfermedades
            return redirect('gestion_medica:ruta_enfermedad_paciente', pk=pk)
        
        messages.error(request, "Error al actualizar la condición.")
        return render(request, "gestion_medica/pages/editar_enfermedad_paciente.html", {
            'ficha': ficha,
            'form': form,
            'item': item
        })




class EliminarEnfermedadPacienteView(SubElementoMedicoBaseView):
    def post(self, request, pk, enfermedad_id):
        ficha = self.get_ficha(pk)
        item = get_object_or_404(FichaMedicaEnfermedad, id=enfermedad_id, ficha_medica=ficha)
        nombre = item.enfermedad.nombre
        
        try:
            item.delete()        
            self.auditar("eliminó un registro de enfermedad de", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'enfermedad': nombre})
            messages.warning(request, "Enfermedad eliminada de la ficha.")
        except Exception as e:
            messages.error(request, f"Error al eliminar registro: {str(e)}")

        return redirect('gestion_medica:ruta_enfermedad_paciente', pk=pk)




# --- ALERGIAS ---
class MedicoAlergiasView(SubElementoMedicoBaseView):
    def get(self, request, pk):
        ficha = self.get_ficha(pk)
        return render(request, "gestion_medica/pages/alergias_paciente.html", {
            'ficha': ficha, 'alergias': ficha.alergias.select_related('alergia'), 'form': FichaMedicaAlergiaForm()
        })
    
    def post(self, request, pk):
        ficha = self.get_ficha(pk)
        form = FichaMedicaAlergiaForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.ficha_medica = ficha
            try:
                item.save()
                self.auditar("registró una alergia a", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'alergia': item.alergia.nombre})
                messages.success(request, "Alergia registrada.")
                return redirect('gestion_medica:ruta_alergias_paciente', pk=pk)
            except IntegrityError:
                form.add_error('alergia', 'El paciente ya tiene registrada esta alergia.')
            except Exception as e:
                messages.error(request, f"Error al guardar los cambios: {e}")
        
        messages.error(request, "Error al registrar alergia.")
        return render(request, "gestion_medica/pages/alergias_paciente.html", {'ficha': ficha, 'alergias': ficha.alergias.all(), 'form': form})




class EliminarAlergiaPacienteView(SubElementoMedicoBaseView):
    def post(self, request, pk, alergia_id):
        ficha = self.get_ficha(pk)
        item = get_object_or_404(FichaMedicaAlergia, id=alergia_id, ficha_medica=ficha)
        nombre = item.alergia.nombre

        try:
            item.delete()
            self.auditar("eliminó un registro de alergia de", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'alergia': nombre})
            messages.warning(request, "Alergia eliminada.")
        except Exception as e:
            messages.error(request, f"Error al eliminar alergia: {str(e)}")
        return redirect('gestion_medica:ruta_alergias_paciente', pk=pk)




# --- MEDICAMENTOS ---
class MedicoMedicamentosView(SubElementoMedicoBaseView):
    def get(self, request, pk):
        ficha = self.get_ficha(pk)
        return render(request, "gestion_medica/pages/medicamentos_paciente.html", {
            'ficha': ficha, 'medicamentos_paciente': ficha.medicamentos.select_related('medicamento'), 'form': FichaMedicaMedicamentoForm()
        })

    def post(self, request, pk):
        ficha = self.get_ficha(pk)
        form = FichaMedicaMedicamentoForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.ficha_medica = ficha
            try:
                item.save()
                self.auditar("asignó un medicamento permanente a", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'medicamento': item.medicamento.nombre, 'dosis': item.dosis_frecuencia})
                messages.success(request, "Medicamento asignado.")
                return redirect('gestion_medica:ruta_medicamentos_paciente', pk=pk)
            except IntegrityError:
                form.add_error('medicamento', 'Este medicamento ya está asignado.')
            except Exception as e:
                messages.error(request, f"Error al asignar medicamento: {str(e)}")

        messages.error(request, "Error al asignar medicamento. Revisa los datos.")
        return render(request, "gestion_medica/pages/medicamentos_paciente.html", {'ficha': ficha, 'medicamentos_paciente': ficha.medicamentos.all(), 'form': form})



class EditarMedicamentoPacienteView(View): # NO SE USA. PENDIENTE DE ELIMINAR
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




class EliminarMedicamentoPacienteView(SubElementoMedicoBaseView):
    def post(self, request, pk, medicamento_id):
        ficha = self.get_ficha(pk)
        item = get_object_or_404(FichaMedicaMedicamento, id=medicamento_id, ficha_medica=ficha)
        nombre = item.medicamento.nombre

        try:
            item.delete()
            self.auditar("retiró un medicamento de la ficha de", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'medicamento': nombre})
            messages.warning(request, "Medicamento eliminado.")
        except Exception as e:
            messages.error(request, f"Error al eliminar medicamento: {str(e)}")

        return redirect('gestion_medica:ruta_medicamentos_paciente', pk=pk)




# --- CIRUGÍAS ---
class MedicoCirugiasView(SubElementoMedicoBaseView):
    def get(self, request, pk):
        ficha = self.get_ficha(pk)
        return render(request, "gestion_medica/pages/gestionar_cirugias.html", {
            'ficha': ficha, 'cirugias': ficha.cirugias.select_related('cirugia'), 'form': FichaMedicaCirugiaForm()
        })

    def post(self, request, pk):
        ficha = self.get_ficha(pk)
        form = FichaMedicaCirugiaForm(request.POST)
        if form.is_valid():
            try:
                item = form.save(commit=False)
                item.ficha_medica = ficha
                item.save()
                self.auditar("registró antecedentes de cirugía a", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'cirugia': item.cirugia.nombre, 'fecha': str(item.fecha_cirugia)})
                messages.success(request, "Cirugía registrada.")
                return redirect('gestion_medica:ruta_cirugias_paciente', pk=pk)
            
            except Exception as e:
                messages.error(request, f"Error al registrar cirugía: {e}")

        messages.error(request, "Error al registrar cirugía.")
        return render(request, "gestion_medica/pages/gestionar_cirugias.html", {'ficha': ficha, 'cirugias': ficha.cirugias.all(), 'form': form})




class EditarCirugiaPacienteView(View): # NO SE USA. PENDIENTE DE ELIMINAR
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




class EliminarCirugiaPacienteView(SubElementoMedicoBaseView):
    def post(self, request, pk, item_id):
        ficha = self.get_ficha(pk)
        item = get_object_or_404(FichaMedicaCirugia, id=item_id, ficha_medica=ficha)
        nombre = item.cirugia.nombre

        try:
            item.delete()
            self.auditar("eliminó un registro de cirugía de", ficha.voluntario.usuario, ficha.voluntario.usuario.get_full_name, {'cirugia': nombre})
            messages.warning(request, "Registro de cirugía eliminado.")
        except Exception as e:
            messages.error(request, f"Error al eliminar registro: {str(e)}")

        return redirect('gestion_medica:ruta_cirugias_paciente', pk=pk)




# ==============================================================================
# 4. GESTIÓN DE CATÁLOGOS GLOBALES (NORMALIZACIÓN)
# ==============================================================================
class CatalogoMedicoBaseView(BaseEstacionMixin, AuditoriaMixin, PermissionRequiredMixin, View):
    """Base para CRUDs de catálogos globales (Medicamentos, Enfermedades, etc.)"""
    permission_required = 'gestion_medica.accion_gestion_medica_gestionar_datos_normalizacion'

    def get_context_data(self, **kwargs):
        # Hook para personalizar contexto en hijos si fuera necesario
        return kwargs




# --- MEDICAMENTOS (CATÁLOGO) ---
class MedicamentoListView(CatalogoMedicoBaseView):
    def get(self, request):
        return render(request, "gestion_medica/pages/lista_medicamentos.html", {'object_list': Medicamento.objects.all().order_by('nombre')})


class MedicamentoCrearView(CatalogoMedicoBaseView):
    def get(self, request):
        return render(request, "gestion_medica/pages/crear_medicamento.html", {'form': MedicamentoForm()})
    
    def post(self, request):
        form = MedicamentoForm(request.POST)
        if form.is_valid():
            try:
                obj = form.save()
                messages.success(request, f"Medicamento '{obj.nombre}' creado correctamente.")
                return redirect('gestion_medica:ruta_lista_medicamentos')
            except Exception as e:
                messages.error(request, f"Error al crear medicamento: {e}")

        messages.error(request, "Error en el formulario de medicamentos. Revise los datos.")
        return render(request, "gestion_medica/pages/crear_medicamento.html", {'form': form})


class MedicamentoUpdateView(CatalogoMedicoBaseView):
    def get(self, request, pk):
        obj = get_object_or_404(Medicamento, pk=pk)
        return render(request, "gestion_medica/pages/crear_medicamento.html", {'form': MedicamentoForm(instance=obj)})
    
    def post(self, request, pk):
        obj = get_object_or_404(Medicamento, pk=pk)
        form = MedicamentoForm(request.POST, instance=obj)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Medicamento actualizado.")
                return redirect('gestion_medica:ruta_lista_medicamentos')
            except Exception as e:
                messages.error(request, f"Error al guardar los cambios: {e}")

        messages.error(request, "Error en el formulario de medicamentos. Revise los datos.")
        return render(request, "gestion_medica/pages/crear_medicamento.html", {'form': form})


class MedicamentoDeleteView(CatalogoMedicoBaseView):
    def post(self, request, pk):
        obj = get_object_or_404(Medicamento, pk=pk)
        try:
            obj.delete()
            messages.success(request, "Medicamento eliminado del catálogo.")
        except ProtectedError:
            messages.error(request, "No se puede eliminar: Hay pacientes usando este medicamento.")
        except Exception as e:
            messages.error(request, f"Error inesperado al eliminar: {str(e)}")
        return redirect('gestion_medica:ruta_lista_medicamentos')




# --- ALERGIAS (CATÁLOGO) ---
class AlergiaListView(CatalogoMedicoBaseView):
    def get(self, request):
        return render(request, "gestion_medica/pages/lista_alergias.html", {'object_list': Alergia.objects.all().order_by('nombre')})


class AlergiaCrearView(CatalogoMedicoBaseView):
    def get(self, request):
        return render(request, "gestion_medica/pages/crear_alergia.html", {'form': AlergiaForm()})
    
    def post(self, request):
        form = AlergiaForm(request.POST)
        if form.is_valid():
            try:
                obj = form.save()
                messages.success(request, "Alergia creada.")
                return redirect('gestion_medica:ruta_lista_alergias')
            except Exception as e:
                messages.error(request, f"Error al registrar alergia: {e}")
        messages.error(request, "Error al crear la alergia. Verifique que no exista.")
        return render(request, "gestion_medica/pages/crear_alergia.html", {'form': form})


class AlergiaDeleteView(CatalogoMedicoBaseView):
    def post(self, request, pk):
        obj = get_object_or_404(Alergia, pk=pk)
        try:
            obj.delete()
            messages.success(request, "Alergia eliminada.")
        except ProtectedError:
            messages.error(request, "No se puede eliminar: Hay pacientes usando este medicamento.")
        except Exception as e:
            messages.error(request, f"Error inesperado al eliminar: {str(e)}")
        return redirect('gestion_medica:ruta_lista_alergias')




# --- ENFERMEDADES (CATÁLOGO) ---
class EnfermedadListView(CatalogoMedicoBaseView):
    def get(self, request):
        return render(request, "gestion_medica/pages/lista_enfermedades.html", {'object_list': Enfermedad.objects.all().order_by('nombre')})


class EnfermedadCrearView(CatalogoMedicoBaseView):
    def get(self, request):
        return render(request, "gestion_medica/pages/crear_enfermedad.html", {'form': EnfermedadForm()})
    
    def post(self, request):
        form = EnfermedadForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Enfermedad creada.")
                return redirect('gestion_medica:ruta_lista_enfermedades')
            except Exception as e:
                messages.error(request, f"Error al registrar enfermedad: {e}")
        messages.error(request, "Error al registrar la enfermedad en el catálogo.")
        return render(request, "gestion_medica/pages/crear_enfermedad.html", {'form': form})


class EnfermedadDeleteView(CatalogoMedicoBaseView):
    def post(self, request, pk):
        obj = get_object_or_404(Enfermedad, pk=pk)
        try:
            obj.delete()
            messages.success(request, "Enfermedad eliminada.")
        except ProtectedError:
            messages.error(request, "No se puede eliminar: Hay pacientes usando este medicamento.")
        except Exception as e:
            messages.error(request, f"Error inesperado al eliminar: {str(e)}")
        return redirect('gestion_medica:ruta_lista_enfermedades')




# --- CIRUGÍAS (CATÁLOGO) ---
class CirugiaListView(CatalogoMedicoBaseView):
    def get(self, request):
        return render(request, "gestion_medica/pages/lista_cirugias.html", {'object_list': Cirugia.objects.all().order_by('nombre')})


class CirugiaCrearView(CatalogoMedicoBaseView):
    def get(self, request):
        return render(request, "gestion_medica/pages/crear_cirugia.html", {'form': CirugiaForm()})
    
    def post(self, request):
        form = CirugiaForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Cirugía creada.")
                return redirect('gestion_medica:ruta_lista_cirugias')
            except Exception as e:
                messages.error(request, f"Error al registrar cirugía: {e}")
        messages.error(request, "Error al crear la cirugía en el catálogo.")
        return render(request, "gestion_medica/pages/crear_cirugia.html", {'form': form})


class CirugiaDeleteView(CatalogoMedicoBaseView):
    def post(self, request, pk):
        obj = get_object_or_404(Cirugia, pk=pk)
        try:
            obj.delete()
            messages.success(request, "Cirugía eliminada.")
        except ProtectedError:
            messages.error(request, "No se puede eliminar: Hay pacientes usando este medicamento.")
        except Exception as e:
            messages.error(request, f"Error inesperado al eliminar: {str(e)}")
        return redirect('gestion_medica:ruta_lista_cirugias')