from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.template.loader import render_to_string
from datetime import date
import io
from xhtml2pdf import pisa

from .forms import EditarPerfilForm
from apps.common.mixins import AuditoriaMixin

# Importamos modelos necesarios
from apps.gestion_usuarios.models import Membresia
from apps.gestion_voluntarios.models import (
    Voluntario, HistorialCargo, HistorialReconocimiento, 
    HistorialSancion, HistorialCurso
)
from apps.gestion_medica.models import FichaMedica


class VerPerfilView(LoginRequiredMixin, View):
    template_name = 'perfil/pages/ver_perfil.html'

    def get(self, request, *args, **kwargs):
        es_voluntario = False
        voluntario = None
        try:
            voluntario = Voluntario.objects.get(usuario=request.user)
            es_voluntario = True
        except Voluntario.DoesNotExist:
            pass

        context = {
            'usuario': request.user,
            'es_voluntario': es_voluntario,
            'voluntario': voluntario
        }
        return render(request, self.template_name, context)


class EditarPerfilView(LoginRequiredMixin, View):
    template_name = 'perfil/pages/editar_perfil.html'
    form_class = EditarPerfilForm
    success_url = reverse_lazy('perfil:ver')

    def get(self, request, *args, **kwargs):
        form = self.form_class(instance=request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Tu perfil ha sido actualizado!')
            return redirect(self.success_url)
        messages.error(request, 'Error en el formulario.')
        return render(request, self.template_name, {'form': form})


class CambiarContrasenaView(PasswordChangeView):
    template_name = 'perfil/pages/cambiar_contrasena.html'
    success_url = reverse_lazy('perfil:ver')

    def form_valid(self, form):
        messages.success(self.request, '¡Contraseña cambiada correctamente!')
        return super().form_valid(form)


# =============================================================================
# VISTAS DE DESCARGA (CON RUTAS CORREGIDAS A 'PAGES')
# =============================================================================

class DescargarMiHojaVidaView(LoginRequiredMixin, AuditoriaMixin, View):
    def get(self, request):
        try:
            voluntario = Voluntario.objects.get(usuario=request.user)
            
            # Buscamos datos extra para el encabezado (Membresía y Cargo Actual)
            # Nota: Usamos filter().first() para evitar errores si no existen
            membresia = Membresia.objects.filter(usuario=request.user, estado='ACTIVO').first()
            cargo_actual_obj = HistorialCargo.objects.filter(voluntario=voluntario, fecha_fin__isnull=True).first()

            context = {
                'voluntario': voluntario,
                'membresia': membresia,
                'cargo_actual': cargo_actual_obj,
                'request': request, # Importante para imágenes estáticas en PDF
                # Historiales
                'cargos': HistorialCargo.objects.filter(voluntario=voluntario).order_by('-fecha_inicio'),
                'reconocimientos': HistorialReconocimiento.objects.filter(voluntario=voluntario).order_by('-fecha_evento'),
                'sanciones': HistorialSancion.objects.filter(voluntario=voluntario).order_by('-fecha_evento'),
                'cursos': HistorialCurso.objects.filter(voluntario=voluntario).order_by('-fecha_curso'),
            }

            # RUTA CORREGIDA: Apunta exactamente a donde lo tienes en gestion_voluntarios
            html_string = render_to_string("gestion_voluntarios/pages/hoja_vida_pdf.html", context)
            
            result = io.BytesIO()
            pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)

            if not pdf.err:
                response = HttpResponse(result.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="Hoja_Vida_{request.user.rut}.pdf"'

                # Auditoría (Registramos que descargó su propia ficha)
                self.auditar(
                    verbo="Descargó su hoja de vida",
                    objetivo=request.user,
                    objetivo_repr=request.user.get_full_name,
                    detalles={'accion': 'Visualización Propia Ficha'}
                )

                return response
            return HttpResponse("Error al generar PDF", status=500)

        except Voluntario.DoesNotExist:
            messages.error(request, "No tienes perfil de voluntario.")
            return redirect('perfil:ver')


class VerMiFichaMedicaView(LoginRequiredMixin, AuditoriaMixin, View):
    """
    Permite al usuario autenticado visualizar su propia ficha médica
    usando el mismo diseño de impresión que el módulo de gestión.
    """
    
    def get(self, request):
        try:
            # 1. Buscamos la ficha asociada al usuario logueado (request.user)
            # Mantenemos las optimizaciones (select_related/prefetch_related) para no golpear la BD múltiples veces
            ficha = FichaMedica.objects.select_related(
                'voluntario', 'voluntario__usuario', 'voluntario__domicilio_comuna', 
                'grupo_sanguineo', 'sistema_salud'
            ).prefetch_related(
                'alergias__alergia', 'enfermedades__enfermedad', 'medicamentos__medicamento', 
                'cirugias__cirugia', 'voluntario__contactos_emergencia'
            ).get(voluntario__usuario=request.user)
            
            # 2. Auditoría (Registramos que vio su propia ficha)
            self.auditar(
                verbo="visualizó su propia ficha clínica",
                objetivo=request.user,
                detalles={'accion': 'Visualización Propia Ficha'}
            )

            # 3. Lógica de cálculo de edad (Reutilizada)
            voluntario = ficha.voluntario
            fecha_nac = voluntario.fecha_nacimiento or voluntario.usuario.birthdate
            edad = "S/I"
            
            if fecha_nac: 
                today = date.today()
                edad = today.year - fecha_nac.year - ((today.month, today.day) < (fecha_nac.month, fecha_nac.day))

            # 4. Renderizamos la MISMA plantilla que usas para el reporte administrativo
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

        except FichaMedica.DoesNotExist:
            # Manejo de error si el usuario no tiene ficha creada
            messages.error(request, "No se encontró una ficha médica asociada a tu cuenta.")
            return redirect('perfil:ver') # O la ruta que prefieras