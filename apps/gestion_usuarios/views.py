from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseNotAllowed, HttpResponse
from django.utils import timezone
from django.db.models import Q
from collections import defaultdict

from .models import Usuario, Membresia, Rol
from .forms import FormularioCrearUsuario, FormularioEditarUsuario, FormularioRol
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




class UsuarioDesactivarView(UsuarioDeMiEstacionMixin, View):
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




class UsuarioActivarView(UsuarioDeMiEstacionMixin, View):
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

            membresia.estado = 'ACTIVO'
            membresia.save()

            # Mensaje de éxito para el usuario
            messages.success(request, f"El usuario '{membresia.usuario.get_full_name.title()}' ha sido activado correctamente.")

        except Membresia.DoesNotExist:
            messages.error(request, "El usuario no tiene acceso a esta estación.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")

        # Redirige a la lista de usuarios (asegúrate que esta URL exista)
        return redirect(reverse("gestion_usuarios:ruta_lista_usuarios"))




class RolListaView(View):
    """
    Muestra una lista de roles de la estación activa del usuario,
    separando los roles universales de los específicos.
    """

    template_name = "gestion_usuarios/pages/lista_roles.html"

    def get(self, request, *args, **kwargs):

        # 1. Obtener el ID de la estación activa
        estacion_id = request.session.get('active_estacion_id')

        # 2. Verificar que el ID exista en la sesión.
        if not estacion_id:
            messages.error(request, "No se pudo determinar la estación activa. Por favor, inicie sesión de nuevo.")
            return redirect(reverse("gestion_usuarios:ruta_lista_roles"))
    
        # 3. Obtenemos el objeto de la estación. Si no existe, devuelve un error 404.
        estacion = get_object_or_404(Estacion, id=estacion_id)

        # 4. La consulta para obtener los roles es la misma.
        query = Q(estacion__isnull=True) | Q(estacion=estacion)
        roles_queryset = Rol.objects.filter(query).prefetch_related('permisos').order_by('nombre')

        # 5. Preparar datos
        context = {
            'estacion': estacion,
            'roles': roles_queryset, # Pasamos el queryset al template con la clave 'roles'.
        }

        return render(request, self.template_name, context)




class RolObtenerView(View):
    '''Vista para obtener el detalle de un rol'''

    template_name = "gestion_usuarios/pages/ver_rol.html"
    
    def get(self, request, id):
        # Usamos get_object_or_404 para manejar automáticamente el error si el rol no existe.
        # prefetch_related('permisos__content_type') optimiza la consulta.
        rol = get_object_or_404(
            Rol.objects.prefetch_related('permisos__content_type'), 
            id=id
        )

        # Usamos defaultdict para agrupar los permisos del rol por módulo.
        permisos_por_modulo = defaultdict(list)

        # Obtenemos los permisos del rol, EXCLUYENDO los de las apps nativas de Django
        permisos_del_rol = rol.permisos.exclude(
            content_type__app_label__in=['admin', 'auth', 'contenttypes', 'sessions']
        ).select_related('content_type').exclude(
            codename__startswith='sys_'
        ).select_related('content_type')

        for permiso in permisos_del_rol:
            # Obtenemos el nombre legible del módulo (app_config.verbose_name)
            nombre_modulo = permiso.content_type.model_class()._meta.app_config.verbose_name
            permisos_por_modulo[nombre_modulo].append(permiso.name)

        context = {
            'rol': rol,
            # Pasamos el diccionario ordenado al contexto.
            'permisos_por_modulo': dict(sorted(permisos_por_modulo.items()))
        }

        return render(request, self.template_name, context)




class RolEditarView(View):
    '''Vista para editar roles. Sólo el nombre y la descripción. El usuario sólo puede editar roles asociados a su estación'''

    form_class = FormularioRol
    template_name = "gestion_usuarios/pages/editar_rol.html"
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')
    # permission_required = 'gestion_usuarios.manage_custom_roles'


    def dispatch(self, request, *args, **kwargs):
        """
        Se ejecuta antes que get() o post()
        """
        # Obtener la estación activa de la sesión.
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            # Si no hay estación, no se puede continuar.
            messages.error(request, f"No se encontró una estación asociada a tu sesión")
            return redirect(self.success_url) 

        # Obtener ID del rol de la URL.
        rol_id = kwargs.get('id')
        
        # La consulta de seguridad: Busca un Rol que tenga el 'id' de la URL Y cuyo 'estacion_id' coincida con el de la sesión. Si no lo encuentra, lanza un error 404. Esto previene editar roles universales (estacion=None) o de otras estaciones.
        self.rol = get_object_or_404(Rol, id=rol_id, estacion__id=estacion_id)
        
        return super().dispatch(request, *args, **kwargs)


    def get(self, request, *args, **kwargs):
        """
        Maneja GET. Muestra el formulario con los datos del rol.
        El rol ya fue obtenido y validado en dispatch().
        """
        formulario = self.form_class(instance=self.rol)
        context = {
            'formulario': formulario, 
            'rol': self.rol
        }
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        """
        Maneja POST. Procesa y guarda los datos del formulario.
        """
        formulario = self.form_class(request.POST, instance=self.rol)

        if formulario.is_valid():
            formulario.save()
            messages.success(request, f"Rol '{self.rol.nombre}' actualizado exitosamente.")
            return redirect(self.success_url)
        else:
            messages.error(request, "Formulario no válido. Por favor, revisa los datos.")
            context = {
                'formulario': formulario, 
                'rol': self.rol
            }
            return render(request, self.template_name, context)




class RolCrearView(View):
    '''Vista para crear roles personalizados. Los roles se asocian a la estación del usuario'''

    form_class = FormularioRol
    template_name = 'gestion_usuarios/pages/crear_rol.html'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')
    # permission_required = 'gestion_usuarios.manage_custom_roles'


    def get(self, request, *args, **kwargs):
        # 1. Obtiene la estación activa de la sesión para pasarla al contexto.
        estacion_id = request.session.get('active_estacion_id')
        estacion = get_object_or_404(Estacion, id=estacion_id)

        # 2. Pasa la estación al formulario para que la use en su lógica interna.
        form = self.form_class(estacion=estacion)
        
        # 3. Renderiza la plantilla con el formulario y la estación.
        context = {
            'formulario': form,
            'estacion': estacion
        }
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        # 1. Obtiene la estación activa de la sesión.
        estacion_id = request.session.get('active_estacion_id')
        estacion = get_object_or_404(Estacion, id=estacion_id)

        # 2. Crea una instancia del formulario con los datos de la petición (request.POST)
        #    y la estación para la lógica de guardado.
        form = self.form_class(request.POST, estacion=estacion)

        # 3. Valida el formulario.
        if form.is_valid():
            # El método .save() personalizado de nuestro form se encargará
            # de asignar la estación al nuevo rol.
            form.save()
            messages.success(request, f"Rol creado correctamente.")
            return redirect(self.success_url)
        
        # 4. Si el formulario no es válido, vuelve a mostrar la página
        #    con el formulario que incluye los errores de validación.
        context = {
            'form': form,
            'estacion': estacion
        }
        return render(request, self.template_name, context)




class RolAsignarPermisosView(View):
    template_name = 'gestion_usuarios/pages/asignar_permisos.html'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')
    # permission_required = 'gestion_usuarios.manage_custom_roles'

    def dispatch(self, request, *args, **kwargs):
        """Valida que el rol sea editable y pertenece a la estación activa."""
        estacion_id = request.session.get('active_estacion_id')
        rol_id = kwargs.get('id')
        
        # Un rol editable debe tener el 'id' correcto y pertenecer a la estación activa.
        self.rol = get_object_or_404(Rol, id=rol_id, estacion__id=estacion_id)
        
        return super().dispatch(request, *args, **kwargs)


    def get(self, request, *args, **kwargs):
        """Muestra el formulario con los permisos agrupados y los checkboxes."""
        
        # Filtra los permisos para no mostrar los de sistema (sys_) ni los de apps de Django.
        permissions = Permission.objects.exclude(
            content_type__app_label__in=['admin', 'auth', 'contenttypes', 'sessions']
        ).exclude(
            codename__startswith='sys_'
        ).select_related('content_type').order_by('name')

        # Agrupa los permisos por el nombre legible del módulo (app).
        permissions_by_module = defaultdict(list)
        for perm in permissions:
            module_name = perm.content_type.model_class()._meta.app_config.verbose_name
            permissions_by_module[module_name].append(perm)

        context = {
            'rol': self.rol,
            'permissions_by_module': dict(sorted(permissions_by_module.items())),
            'rol_permissions_ids': set(self.rol.permisos.values_list('id', flat=True))
        }
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        """Guarda los permisos seleccionados para el rol."""
        
        # Obtiene una lista con los IDs de todos los checkboxes marcados.
        selected_permissions_ids = request.POST.getlist('permisos')
        
        # El método set() es ideal: añade los nuevos, quita los desmarcados y deja los que no cambiaron.
        self.rol.permisos.set(selected_permissions_ids)
        
        messages.success(request, f"Permisos del rol '{self.rol.nombre}' actualizados correctamente.")
        return redirect(self.success_url)




class RolEliminarView(View):
    '''Vista para eliminar un rol personalizado.'''

    # --- Atributos de Configuración ---
    template_name = 'gestion_usuarios/pages/eliminar_rol.html'
    # permission_required = 'gestion_usuarios.manage_custom_roles'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')

    def dispatch(self, request, *args, **kwargs):
        """
        Valida que el rol a eliminar exista y pertenezca a la estación activa del usuario.
        Se ejecuta antes que get() o post().
        """
        estacion_id = request.session.get('active_estacion_id')
        rol_id = kwargs.get('id')

        # La consulta de seguridad: encuentra el rol solo si su ID y el ID de su estación
        # coinciden con los datos de la URL y la sesión. Si no, 404.
        self.rol = get_object_or_404(Rol, id=rol_id, estacion__id=estacion_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """Muestra la página de confirmación de eliminación."""
        # El objeto 'self.rol' ya fue obtenido y validado en dispatch().
        return render(request, self.template_name, {'rol': self.rol})

    def post(self, request, *args, **kwargs):
        """Ejecuta la eliminación del rol."""
        # El objeto 'self.rol' ya fue obtenido y validado.
        rol_nombre = self.rol.nombre
        self.rol.delete()
        
        messages.success(request, f"El rol '{rol_nombre.title()}' ha sido eliminado exitosamente.")
        return redirect(self.success_url)
