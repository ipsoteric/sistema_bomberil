from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.db import IntegrityError
from django.urls import reverse

from .models import Usuario
from .forms import FormularioCrearUsuario
from .funciones import generar_contraseña_segura



class UsuarioInicioView(View):
    '''Vista para la página inicial de Gestión de Usuarios'''

    def get(self, request):
        return render(request, "gestion_usuarios/pages/home.html")



class UsuarioListaView(View):
    '''Vista para listar usuarios'''
    
    def get(self, request):
        usuarios = Usuario.objects.filter(estacion=request.user.estacion)
        return render(request, "gestion_usuarios/pages/lista_usuarios.html", context={'usuarios':usuarios})



class UsuarioObtenerView(View):
    '''Vista para obtener el detalle de un usuario'''

    def get(self, request):
        pass



class UsuarioCrearView(View):
    '''Vista para crear usuarios'''

    template_name = "gestion_usuarios/pages/crear_usuario.html"

    def get(self, request):
        formulario = FormularioCrearUsuario()
        return render(request, self.template_name, context={'formulario':formulario})


    def post(self, request):
        formulario = FormularioCrearUsuario(request.POST, request.FILES)

        if not formulario.is_valid():
            messages.add_message(request, messages.ERROR, "Formulario no válido")
            return render(request, self.template_name, {'formulario': formulario})
        
        # Obtener datos limpios
        datos_limpios = formulario.cleaned_data
        # Generar contraseña temporal de 12 caracteres
        contrasena_plana = generar_contraseña_segura()
        
        try:
            Usuario.objects.create(
                email = datos_limpios.get('correo'),
                first_name = datos_limpios.get('nombre'),
                last_name = datos_limpios.get('apellido'),
                rut = datos_limpios.get('rut'),
                birthdate = datos_limpios.get('fecha_nacimiento'),
                phone = datos_limpios.get('telefono'),
                avatar = datos_limpios.get('avatar'),
                estacion = request.user.estacion
            )
            messages.add_message(request, messages.SUCCESS, "Usuario creado con éxito")
            return redirect(reverse('gestion_usuarios:ruta_lista_usuarios'))
        except IntegrityError as e:
            print(f"Error al crear el usuario. Detalle: {e}")
            messages.add_message(request, messages.ERROR, "No es posible realizar la operación")
        except Exception as e:
            print(f"Ocurrió un error inesperado. Detalle: {e}")
            messages.add_message(request, messages.ERROR, "Ocurrió un error inesperado. Intente nuevamente más tarde")
        
        return render(request, self.template_name, {'formulario': formulario})




class UsuarioEditarView(View):
    '''Vista para editar usuarios'''

    def get(self, request):
        pass

    def post(self, request):
        pass



class UsuarioDesactivarView(View):
    '''Vista para desactivar usuarios'''

    def get(self, request):
        pass

    def post(self, request):
        pass



def alternar_tema_oscuro(request):
    current = request.session.get('dark_mode', False)
    request.session['dark_mode'] = not current
    return redirect(request.META.get('HTTP_REFERER', '/'))