from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, views as auth_views
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import FormularioLogin
from apps.gestion_usuarios.models import Membresia


class LoginView(View):

    template_name = "acceso/pages/login.html"

    def get(self, request):
        # Si el usuario ya está autenticado, redirige al inicio
        if request.user.is_authenticated:
            return redirect(reverse('portal:ruta_inicio'))
        
        formulario = FormularioLogin()
        return render(request, self.template_name, {'formulario': formulario})
    

    def post(self, request):
        formulario = FormularioLogin(request.POST)

        if not formulario.is_valid():
            return render(request, self.template_name, {'formulario': formulario})

        datos_limpios = formulario.cleaned_data
        user = authenticate(
            request, 
            rut=datos_limpios.get('rut'), 
            password=datos_limpios.get('password')
        )

        if user is None:
            messages.add_message(request, messages.WARNING, "Usuario y/o contraseña incorrectos")
            return redirect(reverse('acceso:ruta_login'))
            

        # Iniciar sesión
        login(request, user)

        # Obtener membresía activa (acceso)
        membresia_activa = Membresia.objects.filter(usuario=user, estado='ACTIVO').select_related('estacion').first()

        # Verificar membresía
        if membresia_activa:
            # ÉXITO: Guarda los datos de la estación en la sesión.
            request.session['active_estacion_id'] = membresia_activa.estacion.id
            request.session['active_estacion_nombre'] = membresia_activa.estacion.nombre
            messages.success(request, f"Bienvenido, {user.first_name.title()}!")
            return redirect(reverse('portal:ruta_inicio'))
        
        else:
            # FALLO: El usuario es válido, pero no tiene acceso activo.
            # Se cierra su sesión y se le notifica.
            logout(request)
            messages.error(request, "No tienes una membresía activa en ninguna estación. Contacta a un administrador.")
            return redirect(reverse('acceso:ruta_login'))






class LogoutView(LoginRequiredMixin, View):
    def get(self, request):
        logout(request)
        messages.add_message(request, messages.SUCCESS, "Se cerró la sesión correctamente")
        return redirect(reverse('acceso:ruta_login'))






class CustomPasswordResetView(auth_views.PasswordResetView):
    """
    Vista personalizada para sobreescribir las plantillas y URLs
    del flujo de restablecimiento de contraseña.
    """
    # Plantilla del formulario donde se ingresa el email
    template_name = 'acceso/pages/password_reset_form.html'
    
    # Plantilla del asunto del correo
    subject_template_name = 'acceso/emails/password_reset_subject.txt'
    
    # Plantilla del cuerpo del correo en TEXTO PLANO (el fallback)
    email_template_name = 'acceso/emails/password_reset_email.txt'
    
    # Plantilla del cuerpo del correo en HTML (el diseño principal)
    html_email_template_name = 'acceso/emails/password_reset_email.html'
    
    # URL a la que se redirige tras enviar el correo
    success_url = reverse_lazy('acceso:password_reset_done')