from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import FormView
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, views as auth_views
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .forms import FormularioLogin
from apps.gestion_usuarios.models import Membresia
from apps.gestion_inventario.models import Estacion


class LoginView(FormView):
    template_name = "acceso/pages/login.html"
    form_class = FormularioLogin
    success_url = reverse_lazy('portal:ruta_inicio')

    def dispatch(self, request, *args, **kwargs):
        # Redirección proactiva si ya está logueado
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)


    def form_valid(self, form):
        """
        Se ejecuta solo si el formulario es válido.
        Aquí realizamos la autenticación y la lógica de negocio de la sesión.
        """
        rut = form.cleaned_data.get('rut')
        password = form.cleaned_data.get('password')

        try:
            user = authenticate(self.request, rut=rut, password=password)
            if user is None:
                messages.warning(self.request, "Usuario y/o contraseña incorrectos")
                return self.form_invalid(form)

            # 1. Iniciar Sesión (Django Auth)
            login(self.request, user)

            # 2. Lógica de Membresía y Sesión
            return self._procesar_ingreso_usuario(user)
        
        except Exception as e:
            # Si falla la BD al buscar la membresía o al escribir la sesión
            messages.error(self.request, f"Error del sistema al intentar ingresar: {str(e)}")
            return self.form_invalid(form)


    def _procesar_ingreso_usuario(self, user):
        """
        Maneja la lógica específica de tu negocio: Membresías y variables de sesión.
        """
        # Buscamos membresía activa
        membresia = Membresia.objects.filter(
            usuario=user, 
            estado='ACTIVO' # Ojo: Asegúrate que tu modelo usa 'ACTIVO' o el valor correcto del choices
        ).select_related('estacion').first()

        if membresia:
            # CASO A: Usuario con estación. Configuramos sesión completa.
            self._configurar_sesion_estacion(membresia.estacion)
            messages.success(self.request, f"Bienvenido, {user.first_name.title()}!")
            return redirect('portal:ruta_inicio')

        elif user.is_superuser:
            # CASO B: Superusuario sin membresía.
            messages.info(self.request, "Bienvenido Administrador. Selecciona una estación.")
            # Asumo que esta ruta existe o existirá
            return redirect('acceso:ruta_seleccionar_estacion')

        else:
            # CASO C: Usuario sin membresía (El cambio clave).
            # NO cerramos sesión. Lo enviamos a su perfil para que pueda gestionar sus datos.
            messages.warning(self.request, "Has ingresado sin una estación asignada. Solo puedes editar tu perfil.")
            return redirect('perfil:ver') # Redirige al perfil en lugar de expulsarlo


    def _configurar_sesion_estacion(self, estacion):
        """
        Helper para inyectar variables en la sesión. Mantiene tu lógica original limpia.
        """
        self.request.session['active_estacion_id'] = estacion.id
        self.request.session['active_estacion_nombre'] = estacion.nombre

        # Lógica de Logo (Mejorada con getattr para evitar errores si faltan campos)
        logo_url = None
        if hasattr(estacion, 'logo_thumb_small') and estacion.logo_thumb_small:
            logo_url = estacion.logo_thumb_small.url
        elif estacion.logo:
            logo_url = estacion.logo.url
            
        self.request.session['active_estacion_logo'] = logo_url






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

    def form_valid(self, form):
        try:
            # Intentamos enviar el correo (super().form_valid lo hace internamente)
            response = super().form_valid(form)
            
            # Si llega aquí, el correo salió (o Django lo encoló)
            messages.success(self.request, "Se ha enviado un enlace de recuperación a tu correo.")
            return response

        except Exception as e:
            # Capturamos errores de SMTP (ConnectionRefused, AuthError, etc.)
            messages.error(self.request, f"No se pudo enviar el correo: {str(e)}. Contacta a soporte.")
            return self.form_invalid(form)




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

        try:
            estacion = get_object_or_404(Estacion, id=estacion_id)

            # No necesitamos validar membresía porque el mixin garantiza que es Superuser.
            # Inyectamos la sesión directamente.
            request.session['active_estacion_id'] = estacion.id
            request.session['active_estacion_nombre'] = estacion.nombre

            # Obtener el logo de la estación
            if estacion.logo_thumb_small:
                request.session['active_estacion_logo'] = estacion.logo_thumb_small.url
            elif estacion.logo:
                request.session['active_estacion_logo'] = estacion.logo.url
            else:
                request.session['active_estacion_logo'] = None

            messages.info(request, f"Modo Administrador: Gestionando {estacion.nombre}")
            return redirect('portal:ruta_inicio')
        
        except Exception as e:
            messages.error(request, f"Error al cambiar de estación: {str(e)}")
            return redirect('acceso:ruta_seleccionar_estacion')
    
    # Nota de Arquitectura (Para consideración futura)
    # Regla actual de negocio importante: "Un usuario normal (no superuser) nunca podrá cambiar de estación manualmente".
    # 
    # Esto funciona perfecto ahora. Pero si en el futuro hay un voluntario que trabaja en la "Segunda Compañía" y también es instructor en la "Academia de Bomberos" (otra estación en el sistema), con este código él entrará automáticamente a la primera que encuentre el sistema y no podrá cambiar a la otra.
    # 
    # Si ese escenario llega a ocurrir en el futuro, solo hay que relajar el test_func (o quitar el mixin y filtrar en el get). Pero por ahora, protegerla es la decisión segura.