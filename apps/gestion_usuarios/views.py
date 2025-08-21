from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseNotAllowed, HttpResponse
from django.utils import timezone

from .models import Usuario, Membresia
from .forms import FormularioCrearUsuario, FormularioEditarUsuario
from .mixins import UsuarioDeMiEstacionMixin
from .funciones import generar_contraseña_segura
from apps.gestion_inventario.models import Estacion



class UsuarioInicioView(View):
    '''Vista para la página inicial de Gestión de Usuarios'''

    def get(self, request):
        return render(request, "gestion_usuarios/pages/home.html")



class UsuarioListaView(View):
    '''Vista para listar usuarios'''

    template_name = "gestion_usuarios/pages/lista_usuarios.html"
    
    def get(self, request):
        active_estacion_id = request.session.get('active_estacion_id')
        
        # Filtra el modelo Membresia, no Usuario
        membresias = Membresia.objects.filter(
            estacion_id=active_estacion_id
        ).select_related('usuario')
        
        return render(request, self.template_name, context={'membresias': membresias})



class UsuarioObtenerView(UsuarioDeMiEstacionMixin, View):
    '''Vista para obtener el detalle de un usuario'''

    template_name = "gestion_usuarios/pages/ver_usuario.html"

    def get(self, request, id):
        membresia = Membresia.objects.filter(
            usuario_id=id,
            estacion_id=request.session.get('active_estacion_id'),
            estado__in=['ACTIVO', 'INACTIVO']
        ).select_related('usuario', 'estacion').prefetch_related('roles').latest('fecha_inicio')

        # Pasamos la membresía encontrada al contexto.
        context = {'membresia': membresia}
        
        return render(request, self.template_name, context)




class UsuarioAgregarView(View):
    '''Vista para agregar usuario y que pueda acceder a la información de la compañía'''

    template_name = "gestion_usuarios/pages/agregar_usuario.html"

    def get(self, request):
        return render(request, self.template_name)
    

    def post(self, request, *args, **kwargs):
        # 1. OBTENER DATOS de la petición y la sesión
        usuario_id = request.POST.get('usuario_id')
        estacion_id = request.session.get('active_estacion_id') # Cambia 'estacion_id_actual' por el nombre de tu variable de sesión

        # 2. VALIDAR DATOS DE ENTRADA
        if not usuario_id or not estacion_id:
            messages.error(request, 'Hubo un error en la solicitud. Faltan datos necesarios.')
            return redirect('gestion_usuarios:ruta_agregar_usuario') # Redirige a la misma página

        try:
            # 3. OBTENER OBJETOS de la base de datos
            usuario = Usuario.objects.get(id=usuario_id)
            estacion = Estacion.objects.get(id=estacion_id)

            # 4. REGLA DE NEGOCIO: Re-verificar que el usuario esté realmente disponible
            if Membresia.objects.filter(usuario=usuario, estado__in=['ACTIVO', 'INACTIVO']).exists():
                messages.warning(request, f'El usuario {usuario.get_full_name.title()} ya se encuentra activo o inactivo en otra estación.')
                return redirect('gestion_usuarios:ruta_agregar_usuario')

            # 5. CREAR LA MEMBRESÍA
            Membresia.objects.create(
                usuario=usuario,
                estacion=estacion,
                estado='ACTIVO',
                fecha_inicio=timezone.now().date() # Asigna la fecha actual como inicio
            )

            messages.success(request, f'¡{usuario.get_full_name.title()} ha sido agregado a la estación exitosamente!')
            # Redirige a una página de éxito, como la lista de usuarios.
            return redirect('gestion_usuarios:ruta_lista_usuarios')

        except Usuario.DoesNotExist:
            messages.error(request, 'El usuario que intentas agregar no existe.')
        except Estacion.DoesNotExist:
            messages.error(request, 'La estación seleccionada no es válida. Revisa tu sesión.')
        
        return redirect('gestion_usuarios:ruta_agregar_usuario')
    




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
        
        # Obtenemos la estación de la sesión
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Tu sesión ha expirado o no tienes una estación asignada. No se puede crear el usuario.")
            return render(request, self.template_name, {'formulario': formulario})
        
        
        try:
            with transaction.atomic():

                # 1. Obtener el objeto Estacion
                estacion_actual = Estacion.objects.get(id=estacion_id)

                # 2. Crear el usuario
                datos_limpios = formulario.cleaned_data
                contrasena_plana = generar_contraseña_segura()

                # create_user para hashear la contraseña correctamente
                nuevo_usuario = Usuario.objects.create_user(
                    password=contrasena_plana,
                    email=datos_limpios.get('correo'),
                    first_name=datos_limpios.get('nombre'),
                    last_name=datos_limpios.get('apellido'),
                    rut=datos_limpios.get('rut'),
                    birthdate=datos_limpios.get('fecha_nacimiento'),
                    phone=datos_limpios.get('telefono'),
                    avatar=datos_limpios.get('avatar'),
                )

                # 3. Crear membresía inicial para el nuevo usuario
                Membresia.objects.create(
                    usuario=nuevo_usuario,
                    estacion=estacion_actual,
                    estado='ACTIVO',
                    fecha_inicio=timezone.now().date()
                )

                print(f"Contraseña para {nuevo_usuario.email}: {contrasena_plana}")

                messages.success(request, f"Usuario {nuevo_usuario.get_full_name.title()} creado y asignado a la estación exitosamente.")
                return redirect(reverse('gestion_usuarios:ruta_lista_usuarios'))

        except Estacion.DoesNotExist:
            messages.error(request, "La estación guardada en tu sesión no es válida.")
        except IntegrityError:
            messages.error(request, "Ya existe un usuario con el mismo RUT o correo electrónico.")
        except Exception as e:
            print(f"Ocurrió un error inesperado: {e}")
            messages.error(request, "Ocurrió un error inesperado. Intenta nuevamente más tarde.")
        
        return render(request, self.template_name, {'formulario': formulario})




class UsuarioEditarView(UsuarioDeMiEstacionMixin, View):
    '''Vista para editar usuarios'''

    template_name = "gestion_usuarios/pages/editar_usuario.html"


    def get(self, request, id):
        # Obtiene el usuario o retorna un 404 si no existe
        usuario = get_object_or_404(Usuario, id=id)
        
        # Instancia el formulario con los datos del usuario
        formulario = FormularioEditarUsuario(instance=usuario)
        
        return render(request, self.template_name, {'formulario': formulario, 'usuario': usuario})


    def post(self, request, id):
        usuario = get_object_or_404(Usuario, id=id)
        
        # Instancia el formulario con los datos de la petición y los datos del usuario
        formulario = FormularioEditarUsuario(request.POST, request.FILES, instance=usuario)

        if formulario.is_valid():
            # El formulario se encarga de guardar los cambios en el objeto 'usuario'
            formulario.save()
            messages.success(request, f"Usuario {usuario.get_full_name.title()} actualizado exitosamente.")
            return redirect(reverse('gestion_usuarios:ruta_lista_usuarios'))
        else:
            print("FORMULARIO NO VALIDO")
            messages.error(request, "Formulario no válido. Por favor, revisa los datos.")
            return render(request, self.template_name, {'formulario': formulario, 'usuario': usuario})




#class UsuarioEditarAvatarView(View):
#    '''Vista para modificar el avatar de un usuario'''
#
#    def get(self, request):
#        return HttpResponseNotAllowed(['POST'])
#
#    def post(self, request, id):
#        pass




class UsuarioDesactivarView(View):
    '''Vista para desactivar usuarios. Desactivar un usuario consiste en no permitirle iniciar sesión en la compañía.'''

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
            messages.success(request, f"El usuario '{membresia.usuario.get_full_name.title()}' ha sido desactivado correctamente.")

        except Membresia.DoesNotExist:
            messages.error(request, "El usuario no tiene acceso a esta estación.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")

        # Redirige a la lista de usuarios (asegúrate que esta URL exista)
        return redirect(reverse("gestion_usuarios:ruta_lista_usuarios"))