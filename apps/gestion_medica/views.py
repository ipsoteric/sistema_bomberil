from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages # Opcional, para mensajes bonitos
from .models import Medicamento, FichaMedica, FichaMedicaMedicamento,FichaMedicaAlergia, FichaMedicaEnfermedad, FichaMedicaCirugia, ContactoEmergencia, Alergia,  Enfermedad, Cirugia
from .forms import MedicamentoForm, FichaMedicaForm, FichaMedicaMedicamentoForm, FichaMedicaAlergiaForm, FichaMedicaEnfermedadForm, ContactoEmergenciaForm, FichaMedicaCirugiaForm, AlergiaForm, EnfermedadForm, CirugiaForm    
from datetime import date  
from django.db import IntegrityError  # <--- IMPORTANTE

class MedicoInicioView(View):
    '''Vista para ver la página principal del módulo'''
    def get(self, request):
        return render(request, "gestion_medica/pages/home.html")
    


class MedicoCrearView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/crear_voluntario.html")



class MedicoListaView(View):
    def get(self, request):
        # 1. Buscamos todas las fichas médicas en la base de datos
        # Usamos 'select_related' para traer los datos del voluntario y usuario de una vez (optimización)
        pacientes = FichaMedica.objects.select_related('voluntario__usuario').all()
        return render(request, "gestion_medica/pages/lista_voluntarios.html", {'pacientes': pacientes})
    
class MedicoDatosView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/datos_paciente.html")
    #def get(self, request, id):
        #return HttpResponse("mostrar datos")

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

# En apps/gestion_medica/views.py

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
        return redirect('gestion_medica:ruta_contacto_emergencia', pk=pk)#def get(self, request, id):
        #return HttpResponse("mostrar datos")

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

class MedicoInfoView(View):
    def get(self, request, pk):
        # Buscamos la ficha por el ID (pk). Si no existe, da error 404.
        ficha = get_object_or_404(FichaMedica, pk=pk)
        # 2. Buscamos al voluntario
        voluntario = ficha.voluntario

        # --- CORRECCIÓN AQUÍ: Usamos voluntario.usuario ---
        usuario = voluntario.usuario  # Accedemos a la cuenta de usuario real
        
        edad = "S/I"
        if usuario.birthdate: # <--- Aquí estaba el error, se llama birthdate
            today = date.today()
            nac = usuario.birthdate
            # Calculamos la edad exacta
            edad = today.year - nac.year - ((today.month, today.day) < (nac.month, nac.day))

        qr_url = request.build_absolute_uri()

        return render(request, "gestion_medica/pages/informacion_paciente.html", {
            'ficha': ficha,
            'voluntario': voluntario,
            'edad': edad, # Enviamos la edad calculada
            'qr_url': qr_url,  # Enviamos la URL para el QR
            # Relaciones directas desde la ficha (usando related_name del models.py)
            'alergias': ficha.alergias.all(),
            'enfermedades': ficha.enfermedades.all(),
            'medicamentos': ficha.medicamentos.all(),
            'cirugias': ficha.cirugias.all(),
            # Relación desde el voluntario
            'contactos': voluntario.contactos_emergencia.all()
        })
    
    #def get(self, request, id):
        #return HttpResponse("mostrar datos")

class MedicoVerView(View):
    def get(self, request):
        return render(request, "gestion_medica/pages/ver_voluntario.html")



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
    
class MedicoImprimirView(View):
    def get(self, request, pk):
        ficha = get_object_or_404(FichaMedica, pk=pk)
        voluntario = ficha.voluntario
        # --- CORRECCIÓN AQUÍ: Usamos voluntario.usuario ---
        usuario = voluntario.usuario  # Accedemos a la cuenta de usuario real
        
        edad = "S/I"
        # Verificamos si el USUARIO tiene la fecha, no el voluntario
        if hasattr(usuario, 'fecha_nacimiento') and usuario.fecha_nacimiento:
            today = date.today()
            edad = today.year - usuario.fecha_nacimiento.year - ((today.month, today.day) < (usuario.fecha_nacimiento.month, usuario.fecha_nacimiento.day))

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
    
# --- GESTIÓN CATÁLOGO ALERGIAS ---

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
            # Opcional: Mensaje de éxito si usas 'messages'
            return redirect('gestion_medica:ruta_lista_alergias')
        
        # Si no es válido (ej: ya existe), volvemos al HTML con el formulario y sus errores
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
    
# Asegúrate de que en tus imports al principio tengas:
# from .forms import ..., CirugiaForm

# --- GESTIÓN CATÁLOGO CIRUGÍAS ---

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

class EnfermedadDeleteView(View):
    def post(self, request, pk):
        item = get_object_or_404(Enfermedad, pk=pk)
        item.delete()
        return redirect('gestion_medica:ruta_lista_enfermedades')
 
