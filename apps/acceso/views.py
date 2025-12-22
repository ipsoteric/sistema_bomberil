from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import FormView
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, views as auth_views
from django.urls import reverse, reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from .forms import FormularioLogin
from apps.gestion_usuarios.models import Membresia
from apps.gestion_inventario.models import Estacion


class LoginView(FormView):
    template_name = "acceso/pages/login.html"
    form_class = FormularioLogin
    success_url = reverse_lazy('portal:ruta_inicio')

    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        """
        Evita caché en el login y redirige si ya está autenticado.
        """
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
            # 1. Autenticación pura de Django
            user = authenticate(self.request, rut=rut, password=password)
            
            if user is None:
                messages.warning(self.request, "Usuario y/o contraseña incorrectos")
                return self.form_invalid(form)

            # 2. Iniciar Sesión (Crear cookie de sesión)
            login(self.request, user)

            # 3. Delegar lógica de negocio (Estaciones y Membresías)
            return self._procesar_ingreso_usuario(user)
        
        except Exception as e:
            # Captura de errores generales para no romper la vista (Error 500)
            print(f"Error crítico en Login: {e}") # Log para consola
            messages.error(self.request, "Ocurrió un error inesperado al iniciar sesión. Intente nuevamente.")
            return self.form_invalid(form)


    def _procesar_ingreso_usuario(self, user):
        """
        Determina a dónde va el usuario y configura su entorno.
        """
        # Buscamos membresía activa.
        # Nota: Usamos filter().first() en lugar de get() para evitar errores DoesNotExist
        membresia = Membresia.objects.filter(
            usuario=user, 
            estado='ACTIVO' 
        ).select_related('estacion').first()

        if membresia:
            # CASO A: Usuario "Voluntario" con estación válida.
            if membresia.estacion:
                self._configurar_sesion_estacion(membresia.estacion)
                messages.success(self.request, f"Bienvenido, {user.first_name.title()}!")
                return redirect('portal:ruta_inicio')
            else:
                # Caso borde: Tiene membresía pero la estación es Null (Inconsistencia de datos)
                messages.error(self.request, "Tu cuenta tiene un error de configuración (Sin Estación). Contacta soporte.")
                return redirect('perfil:ver')

        elif user.is_superuser:
            # CASO B: Superusuario.
            messages.info(self.request, "Bienvenido Administrador. Selecciona una estación.")
            # Asegúrate que esta ruta exista en tus urls.py
            return redirect('acceso:ruta_seleccionar_estacion')

        else:
            # CASO C: Usuario sin membresía activa.
            messages.warning(self.request, "Has ingresado sin una estación asignada. Solo puedes editar tu perfil.")
            return redirect('perfil:ver')


    def _configurar_sesion_estacion(self, estacion):
        """
        Guarda los datos de la estación en la sesión de forma segura.
        """
        try:
            # 1. ID de Estación: Convertimos a STRING explícitamente.
            # Esto previene errores si tu PK es un UUID o BigInt que JSON no serialice bien.
            self.request.session['active_estacion_id'] = str(estacion.id)
            
            # 2. Nombre de Estación
            self.request.session['active_estacion_nombre'] = estacion.nombre

            # 3. Logo (Gestión de errores si el archivo no existe físicamente)
            logo_url = None
            try:
                if hasattr(estacion, 'logo_thumb_small') and estacion.logo_thumb_small:
                    logo_url = estacion.logo_thumb_small.url
                elif estacion.logo:
                    logo_url = estacion.logo.url
            except ValueError:
                # Si la BD dice que hay imagen pero el archivo no está en disco
                logo_url = None
            
            self.request.session['active_estacion_logo'] = logo_url

            # 4. FORZAR GUARDADO DE SESIÓN
            # Esto es vital. Le dice a Django que la sesión ha cambiado y DEBE escribirse en BD/Cookie.
            self.request.session.modified = True
            
            # Opcional: Forzar escritura inmediata (si usas DatabaseSession)
            if hasattr(self.request.session, 'save'):
                self.request.session.save()

        except Exception as e:
            # Si falla el guardado en sesión, lo logueamos pero no detenemos el login
            print(f"Error al guardar datos en sesión: {e}")
            # No lanzamos error al usuario, pero la sesión quedará 'coja' (sin ID)
            # Esto causaría el error original, pero al menos sabremos por qué gracias al print.






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




class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """
    Vista personalizada para confirmar el cambio de contraseña.
    Si el cambio es exitoso, marcamos al usuario como verificado.
    """
    template_name = "acceso/pages/password_reset_confirm.html"
    success_url = reverse_lazy('acceso:password_reset_complete')

    def form_valid(self, form):
        # 1. Llamamos al método padre. Esto guarda la nueva contraseña y retorna la redirección.
        response = super().form_valid(form)
        
        # 2. La vista PasswordResetConfirmView guarda el usuario en 'self.user' 
        #    después de validar el token en el método dispatch.
        user = self.user
        
        # 3. Verificamos y actualizamos el flag
        if not user.is_verified:
            user.is_verified = True
            # Usamos update_fields para ser más eficientes y solo tocar ese campo
            user.save(update_fields=['is_verified'])
            
        return response




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