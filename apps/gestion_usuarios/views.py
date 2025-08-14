from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.db import IntegrityError
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseNotAllowed, HttpResponse

from .models import Usuario, Membresia
from .forms import FormularioCrearUsuario
from .funciones import generar_contraseña_segura



class UsuarioInicioView(View):
    '''Vista para la página inicial de Gestión de Usuarios'''

    def get(self, request):
        return render(request, "gestion_usuarios/pages/home.html")



class UsuarioListaView(View):
    '''Vista para listar usuarios'''
    
    def get(self, request):
        active_estacion_id = request.session.get('active_estacion_id')
        
        # Filtra el modelo Membresia, no Usuario
        membresias = Membresia.objects.filter(
            estacion_id=active_estacion_id
        ).select_related('usuario')
        
        return render(request, "gestion_usuarios/pages/lista_usuarios.html", context={'membresias': membresias})



class UsuarioObtenerView(View):
    '''Vista para obtener el detalle de un usuario'''

    def get(self, request, id):
        return HttpResponse("VER USUARIO")



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

    def get(self, request, id):
        return HttpResponse("EDITAR USUARIO")

    def post(self, request):
        pass


# ESTA FUNCIONALIDAD DEBE IMPLEMENTARSE DE OTRA FORMA
class UsuarioDesactivarView(View):
    '''Vista para desactivar usuarios'''

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def post(self, request, id, *args, **kwargs):
        active_estacion_id = request.session.get('active_estacion_id')
        if not active_estacion_id:
            messages.error(request, "No se pudo determinar la estación activa. Por favor, inicie sesión de nuevo.")
            return redirect(reverse("gestion_usuarios:ruta_lista_usuarios"))

        
        try:
            membresia = get_object_or_404(
                Membresia, 
                usuario_id=id, 
                estacion_id=active_estacion_id
            )

            membresia.estado = 'INACTIVO'
            membresia.save()

            # Mensaje de éxito para el usuario
            messages.success(request, f"El usuario '{membresia.usuario.get_full_name}' ha sido desactivado correctamente.")

        except Membresia.DoesNotExist:
            messages.error(request, "El usuario no tiene acceso a esta estación.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")

        # Redirige a la lista de usuarios (asegúrate que esta URL exista)
        return redirect(reverse("gestion_usuarios:ruta_lista_usuarios"))



def alternar_tema_oscuro(request):
    current = request.session.get('dark_mode', False)
    request.session['dark_mode'] = not current
    return redirect(request.META.get('HTTP_REFERER', '/'))