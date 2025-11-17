from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, views as auth_views
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .forms import FormularioLogin
from apps.gestion_usuarios.models import Membresia
from apps.gestion_inventario.models import Estacion


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
            # Caso A: Usuario normal (o superuser con membresía). Flujo estándar.
            request.session['active_estacion_id'] = membresia_activa.estacion.id
            request.session['active_estacion_nombre'] = membresia_activa.estacion.nombre
            messages.success(request, f"Bienvenido, {user.first_name.title()}!")
            return redirect(reverse('portal:ruta_inicio'))
        
        elif user.is_superuser:
            # Caso B: Superusuario SIN membresía activa.
            # No lo expulsamos. Lo enviamos a seleccionar estación.
            messages.info(request, f"Bienvenido Administrador. Por favor selecciona una estación para gestionar.")
            # Asegúrate de crear esta ruta y vista (la que hablamos antes)
            return redirect('acceso:ruta_seleccionar_estacion')
        
        else:
            # Caso C: Usuario normal sin membresía. Expulsado.
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




class SeleccionarEstacionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Permite al usuario seleccionar con qué estación desea trabajar ("Modo Dios").
    - RESTRINGIDO: Solo accesible para superusuarios.
    - Superusuarios: Ven TODAS las estaciones.
    - Usuarios normales: Ven solo las estaciones donde tienen membresía ACTIVA.
    """
    template_name = "acceso/pages/seleccionar_estacion.html"


    # 2. Definimos la prueba de seguridad
    def test_func(self):
        # Solo pasa si es superusuario.
        # Si retorna False, Django lanza un error 403 (Prohibido).
        return self.request.user.is_superuser
    

    def get(self, request):
        # Como ya filtramos con el mixin, aquí asumimos que es Superuser.
        # Mostramos TODAS las estaciones.
        estaciones = Estacion.objects.all().order_by('nombre')
        return render(request, self.template_name, {'estaciones': estaciones})


    def post(self, request):
        estacion_id = request.POST.get('estacion_id')
        
        if not estacion_id:
            messages.error(request, "Debes seleccionar una estación.")
            return redirect('acceso:ruta_seleccionar_estacion')

        estacion = get_object_or_404(Estacion, id=estacion_id)

        # No necesitamos validar membresía porque el mixin garantiza que es Superuser.
        # Inyectamos la sesión directamente.
        request.session['active_estacion_id'] = estacion.id
        request.session['active_estacion_nombre'] = estacion.nombre
        
        messages.info(request, f"Modo Administrador: Gestionando {estacion.nombre}")
        return redirect('portal:ruta_inicio')
    
    # Nota de Arquitectura (Para consideración futura)
    # Regla actual de negocio importante: "Un usuario normal (no superuser) nunca podrá cambiar de estación manualmente".
    # 
    # Esto funciona perfecto ahora. Pero si en el futuro hay un voluntario que trabaja en la "Segunda Compañía" y también es instructor en la "Academia de Bomberos" (otra estación en el sistema), con este código él entrará automáticamente a la primera que encuentre el sistema y no podrá cambiar a la otra.
    # 
    # Si ese escenario llega a ocurrir en el futuro, solo hay que relajar el test_func (o quitar el mixin y filtrar en el get). Pero por ahora, protegerla es la decisión segura.