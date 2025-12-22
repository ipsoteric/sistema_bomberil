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
            try:
                form.save()
                messages.success(request, '¡Tu perfil ha sido actualizado!')
                return redirect(self.success_url)
            except Exception as e:
                messages.error(request, f"Error crítico al actualizar perfil: {str(e)}")

        messages.error(request, 'Error en el formulario.')
        return render(request, self.template_name, {'form': form})


class CambiarContrasenaView(PasswordChangeView):
    template_name = 'perfil/pages/cambiar_contrasena.html'
    success_url = reverse_lazy('perfil:ver')

    def form_valid(self, form):
        try:
            messages.success(self.request, '¡Contraseña cambiada correctamente!')
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Error al cambiar la contraseña: {e}")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "No se pudo cambiar la contraseña. Verifica que la contraseña actual sea correcta y que las nuevas coincidan.")
        return super().form_invalid(form)

# =============================================================================
# VISTAS DE DESCARGA (CON RUTAS CORREGIDAS A 'PAGES')
# =============================================================================

class DescargarMiHojaVidaView(LoginRequiredMixin, AuditoriaMixin, View):
    """
    Controlador encargado de la generación y descarga del reporte PDF "Hoja de Vida"
    para el usuario actualmente autenticado.
    
    Funcionalidad Técnica:
    - Recuperación de perfil de Voluntario asociado a la sesión.
    - Agregación de datos históricos (Cargos, Sanciones, Cursos) y estado actual.
    - Renderizado de plantilla HTML y conversión a binario PDF utilizando xhtml2pdf (Pisa).
    - Registro de auditoría de auto-consulta.
    """

    def get(self, request):
        try:
            # 1. Recuperación de Entidad Principal
            # Obtener el perfil de voluntario vinculado al usuario de la sesión.
            voluntario = Voluntario.objects.get(usuario=request.user)
            
            # 2. Recuperación de Datos Complementarios (Safe Retrieval)
            # Utilizar .first() para obtener relaciones 1:N que actúan como 1:1 en el contexto actual (Estado actual).
            # Esto previene excepciones DoesNotExist si la data no está íntegra.
            membresia = Membresia.objects.filter(usuario=request.user, estado='ACTIVO').first()
            cargo_actual_obj = HistorialCargo.objects.filter(voluntario=voluntario, fecha_fin__isnull=True).first()

            # 3. Construcción del Contexto de Reporte
            context = {
                'voluntario': voluntario,
                'membresia': membresia,
                'cargo_actual': cargo_actual_obj,
                'request': request, # Inyectar request para resolución de rutas absolutas de imágenes en PDF (static)
                
                # Colecciones Históricas (Ordenamiento Cronológico Inverso)
                'cargos': HistorialCargo.objects.filter(voluntario=voluntario).order_by('-fecha_inicio'),
                'reconocimientos': HistorialReconocimiento.objects.filter(voluntario=voluntario).order_by('-fecha_evento'),
                'sanciones': HistorialSancion.objects.filter(voluntario=voluntario).order_by('-fecha_evento'),
                'cursos': HistorialCurso.objects.filter(voluntario=voluntario).order_by('-fecha_curso'),
            }

            # 4. Generación de PDF en Memoria
            # Renderizar plantilla HTML a string.
            html_string = render_to_string("gestion_voluntarios/pages/hoja_vida_pdf.html", context)
            
            # Crear buffer de bytes para el flujo de salida.
            result = io.BytesIO()
            # Convertir HTML a PDF.
            pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)

            # 5. Entrega de Respuesta
            if not pdf.err:
                response = HttpResponse(result.getvalue(), content_type='application/pdf')
                # Configurar header para descarga de archivo adjunto con nombre dinámico.
                response['Content-Disposition'] = f'attachment; filename="Hoja_Vida_{request.user.rut}.pdf"'

                # --- Auditoría ---
                self.auditar(
                    verbo="Descargó su hoja de vida",
                    objetivo=request.user,
                    objetivo_repr=request.user.get_full_name,
                    detalles={'accion': 'Visualización Propia Ficha'}
                )

                return response
            
            # Manejo de error en generación de PDF
            messages.error(request, "Error interno al generar el PDF. Contacte a soporte.")
            return redirect('perfil:ver')

        except Voluntario.DoesNotExist:
            # Manejo de consistencia: Usuario sin perfil de voluntario asignado.
            messages.error(request, "No tienes perfil de voluntario asociado.")
            return redirect('perfil:ver')
        
        except Exception as e:
            # Captura de errores no controlados
            messages.error(request, f"Ocurrió un error inesperado: {str(e)}")
            return redirect('perfil:ver')




class VerMiFichaMedicaView(LoginRequiredMixin, AuditoriaMixin, View):
    """
    Controlador para la visualización de la Ficha Clínica Personal.
    
    Permite al usuario autenticado acceder a sus antecedentes médicos en modo solo lectura,
    reutilizando la plantilla de impresión del módulo de gestión médica para garantizar
    consistencia visual en los reportes.
    """
    
    def get(self, request):
        try:
            # 1. Recuperación Optimizada de Datos (Eager Loading)
            # Utilizar select_related para relaciones ForeignKey directas y prefetch_related
            # para relaciones ManyToMany o inversas, minimizando consultas a la base de datos (N+1 Problem).
            ficha = FichaMedica.objects.select_related(
                'voluntario', 'voluntario__usuario', 'voluntario__domicilio_comuna', 
                'grupo_sanguineo', 'sistema_salud'
            ).prefetch_related(
                'alergias__alergia', 'enfermedades__enfermedad', 'medicamentos__medicamento', 
                'cirugias__cirugia', 'voluntario__contactos_emergencia'
            ).get(voluntario__usuario=request.user)
            
            # 2. Registro de Auditoría
            # Documentar el acceso a información sensible (PHI).
            self.auditar(
                verbo="visualizó su propia ficha clínica",
                objetivo=request.user,
                detalles={'accion': 'Visualización Propia Ficha'}
            )

            # 3. Lógica de Presentación (Cálculo de Edad)
            # Determinar edad exacta basada en fecha de nacimiento del voluntario o del usuario base.
            voluntario = ficha.voluntario
            fecha_nac = voluntario.fecha_nacimiento or voluntario.usuario.birthdate
            edad = "S/I"
            
            if fecha_nac: 
                today = date.today()
                # Ajuste booleano para restar un año si aún no cumple en el año actual.
                edad = today.year - fecha_nac.year - ((today.month, today.day) < (fecha_nac.month, fecha_nac.day))

            # 4. Renderizado de Vista
            # Inyección de dependencias para la plantilla de impresión.
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
            # Manejo de caso donde el usuario no tiene ficha creada.
            messages.error(request, "No se encontró una ficha médica asociada a tu cuenta.")
            return redirect('perfil:ver')
        
        except Exception as e:
            # Captura de errores generales.
            messages.error(request, f"Error al cargar la ficha médica: {str(e)}")
            return redirect('perfil:ver')