import pprint
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.models import Permission
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.forms import PasswordResetForm
from django.db import IntegrityError, transaction
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseNotAllowed
from django.utils import timezone
from django.db.models import Q
from collections import defaultdict
from django.apps import apps

from .models import Usuario, Membresia, Rol
from .forms import FormularioCrearUsuario, FormularioEditarUsuario, FormularioRol
from .mixins import UsuarioDeMiEstacionMixin, RolValidoParaEstacionMixin
from apps.common.mixins import ModuleAccessMixin, ObjectInStationRequiredMixin
from .utils import generar_contraseña_segura
from apps.gestion_inventario.models import Estacion



class UsuarioInicioView(LoginRequiredMixin, ModuleAccessMixin, View):
    '''Vista para la página inicial de Gestión de Usuarios'''

    def get(self, request):
        return render(request, "gestion_usuarios/pages/home.html")



class UsuarioListaView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    '''Vista para listar usuarios'''

    template_name = "gestion_usuarios/pages/lista_usuarios.html"
    model = Membresia
    permission_required = 'gestion_usuarios.accion_usuarios_ver_usuarios_compania'
    
    def get(self, request):
        active_estacion_id = request.session.get('active_estacion_id')
        
        # Filtra el modelo Membresia, no Usuario
        membresias = self.model.objects.filter(
            estacion_id=active_estacion_id
        ).select_related('usuario')
        
        return render(request, self.template_name, context={'membresias': membresias})



class UsuarioObtenerView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, ObjectInStationRequiredMixin, View):
    '''Vista para obtener el detalle de un usuario'''

    template_name = "gestion_usuarios/pages/ver_usuario.html"
    model = Membresia
    permission_required = 'gestion_usuarios.accion_usuarios_ver_usuarios_compania'

    def get(self, request, id):
        membresia = self.model.objects.filter(
            usuario_id=id,
            estacion_id=request.session.get('active_estacion_id'),
            estado__in=['ACTIVO', 'INACTIVO']
        ).select_related('usuario', 'estacion').prefetch_related('roles').latest('fecha_inicio')

        # Pasamos la membresía encontrada al contexto.
        context = {'membresia': membresia}
        
        return render(request, self.template_name, context)




class UsuarioAgregarView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    '''Vista para agregar usuario y que pueda acceder a la información de la compañía'''

    template_name = "gestion_usuarios/pages/agregar_usuario.html"
    permission_required = 'gestion_usuarios.accion_usuarios_crear_usuario'

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
    




class UsuarioCrearView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    '''Vista para crear usuarios'''

    template_name = "gestion_usuarios/pages/crear_usuario.html"
    permission_required = 'gestion_usuarios.accion_usuarios_crear_usuario'

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
                    rut=datos_limpios.get('rut'),
                    email=datos_limpios.get('correo'),
                    first_name=datos_limpios.get('nombre'),
                    last_name=datos_limpios.get('apellido'),
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




class UsuarioEditarView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, UsuarioDeMiEstacionMixin, View):
    '''Vista para editar usuarios'''

    template_name = "gestion_usuarios/pages/editar_usuario.html"
    permission_required = 'gestion_usuarios.accion_usuarios_modificar_info_personal'


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




class UsuarioDesactivarView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, UsuarioDeMiEstacionMixin, View):
    '''Vista para desactivar usuarios. Desactivar un usuario consiste en no permitirle iniciar sesión en la compañía.'''

    permission_required = 'gestion_usuarios.accion_usuarios_desactivar_usuario'


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




class UsuarioActivarView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, UsuarioDeMiEstacionMixin, View):
    '''Vista para activar usuarios. Activar un usuario le permitirle iniciar sesión en la compañía.'''

    permission_required = 'gestion_usuarios.accion_usuarios_desactivar_usuario'

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




class RolListaView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Muestra una lista de roles de la estación activa del usuario,
    separando los roles universales de los específicos.
    """

    template_name = "gestion_usuarios/pages/lista_roles.html"
    permission_required = 'gestion_usuarios.accion_usuarios_ver_roles'

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




class RolObtenerView(LoginRequiredMixin, ModuleAccessMixin, RolValidoParaEstacionMixin, PermissionRequiredMixin, View):
    '''Vista para obtener el detalle de un rol'''

    template_name = "gestion_usuarios/pages/ver_rol.html"
    permission_required = 'gestion_usuarios.accion_usuarios_ver_roles'
    
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




class RolEditarView(LoginRequiredMixin, ModuleAccessMixin, RolValidoParaEstacionMixin, PermissionRequiredMixin, View):
    '''Vista para editar roles. Sólo el nombre y la descripción. El usuario sólo puede editar roles asociados a su estación'''

    form_class = FormularioRol
    template_name = "gestion_usuarios/pages/editar_rol.html"
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')
    permission_required = 'gestion_usuarios.accion_usuarios_gestionar_roles'


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




class RolCrearView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    '''Vista para crear roles personalizados. Los roles se asocian a la estación del usuario'''

    form_class = FormularioRol
    template_name = 'gestion_usuarios/pages/crear_rol.html'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')
    permission_required = 'gestion_usuarios.accion_usuarios_gestionar_roles'


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




class RolAsignarPermisosView(LoginRequiredMixin, ModuleAccessMixin, RolValidoParaEstacionMixin, PermissionRequiredMixin, View):

    template_name = 'gestion_usuarios/pages/asignar_permisos.html'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')
    permission_required = 'gestion_usuarios.accion_usuarios_gestionar_roles'

    def dispatch(self, request, *args, **kwargs):
        """Valida que el rol sea editable y pertenece a la estación activa."""
        estacion_id = request.session.get('active_estacion_id')
        rol_id = kwargs.get('id')
        
        # Un rol editable debe tener el 'id' correcto y pertenecer a la estación activa.
        self.rol = get_object_or_404(Rol, id=rol_id, estacion__id=estacion_id)
        
        return super().dispatch(request, *args, **kwargs)


    def get(self, request, *args, **kwargs):
        """Muestra el formulario con los permisos agrupados y los checkboxes."""

        # 1. Obtener todos los permisos de negocio
        permissions = Permission.objects.filter(
            Q(codename__startswith='acceso_') | Q(codename__startswith='accion_')
        )

        # 2. Diccionario final
        grouped_perms = {} 

        # 3. PRIMERA PASADA: PADRES (acceso_)
        parent_perms = permissions.filter(codename__startswith='acceso_')
        
        for perm in parent_perms:
            app_label = None
            try:
                # 'acceso_gestion_inventario' -> app_label = 'gestion_inventario'
                app_label = perm.codename.split('_', 1)[1]
                config = apps.get_app_config(app_label)
                
                grouped_perms[app_label] = {
                    'verbose_name': config.verbose_name,
                    'main_perm': perm,
                    'children': []
                }
            except (LookupError, IndexError):
                continue 

        # 4. SEGUNDA PASADA: HIJOS (accion_)
        child_perms = permissions.filter(codename__startswith='accion_')
        # Obtenemos los app_labels que SÍ existen (ej: 'gestion_inventario', 'gestion_usuarios')
        app_labels_from_parents = grouped_perms.keys() 

        for perm in child_perms:
            found_parent = False
            try:
                # Iterar sobre los app_labels que SÍ encontramos en la PASADA 1
                for app_label in app_labels_from_parents:
                    
                    # Construir el prefijo que este permiso 'hijo' debería tener
                    # ej. "accion_gestion_inventario_"
                    expected_prefix = f"accion_{app_label}_"
                    
                    if perm.codename.startswith(expected_prefix):
                        grouped_perms[app_label]['children'].append(perm)
                        found_parent = True
                        break # Encontró su padre, pasar al siguiente permiso
                
                if not found_parent:
                    print(f"[DEBUG] -> ADVERTENCIA: No coincide con ningún prefijo de app_label conocido. Omitiendo.")
            
            except Exception as e:
                print(f"[DEBUG] -> ERROR Inesperado procesando '{perm.codename}': {e}. Omitiendo.")
                continue 

        # 5. Ordenar los permisos hijos alfabéticamente
        for app_label in grouped_perms:
            grouped_perms[app_label]['children'].sort(key=lambda x: x.name)
    
        context = {
            'rol': self.rol,
            'permissions_by_app': dict(sorted(grouped_perms.items(), key=lambda item: item[1]['verbose_name'])),
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




class RolEliminarView(LoginRequiredMixin, ModuleAccessMixin, RolValidoParaEstacionMixin, PermissionRequiredMixin, View):
    '''Vista para eliminar un rol personalizado.'''

    # --- Atributos de Configuración ---
    template_name = 'gestion_usuarios/pages/eliminar_rol.html'
    permission_required = 'gestion_usuarios.accion_usuarios_gestionar_roles'
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




class UsuarioAsignarRolesView(LoginRequiredMixin, ModuleAccessMixin, UsuarioDeMiEstacionMixin, PermissionRequiredMixin, View):
    permission_required = 'gestion_usuarios.accion_usuarios_asignar_roles_usuario'
    template_name = 'gestion_usuarios/pages/asignar_roles.html'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_usuarios')


    def get(self, request, *args, **kwargs):
        """
        Muestra los checkboxes con los roles disponibles agrupados.
        """
        usuario_id = kwargs.get('id')
        estacion_id = request.session.get('active_estacion_id')

        usuario = get_object_or_404(Usuario, id=usuario_id)
        estacion = get_object_or_404(Estacion, id=estacion_id)
        membresia = get_object_or_404(
            Membresia, 
            usuario=usuario, 
            estacion=estacion, 
            estado__in=[Membresia.Estado.ACTIVO, Membresia.Estado.INACTIVO]
        )

        # Obtenemos todos los roles que están disponibles para esta estación:
        # Aquellos donde la estación es nula (universales) O cuya estación es la activa.
        roles_disponibles = Rol.objects.filter(
            Q(estacion__isnull=True) | Q(estacion=estacion)
        ).order_by('nombre')
        
        # Separamos los roles en dos grupos para mostrarlos en la plantilla.
        roles_universales = roles_disponibles.filter(estacion__isnull=True)
        roles_de_estacion = roles_disponibles.filter(estacion=estacion)

        context = {
            'usuario': usuario,
            'estacion': estacion,
            'roles_universales': roles_universales,
            'roles_de_estacion': roles_de_estacion,
            'usuario_roles_ids': set(membresia.roles.values_list('id', flat=True))
        }
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        """
        Guarda los roles seleccionados en la membresía del usuario.
        """

        usuario_id = kwargs.get('id')
        estacion_id = request.session.get('active_estacion_id')

        usuario = get_object_or_404(Usuario, id=usuario_id)
        estacion = get_object_or_404(Estacion, id=estacion_id)
        membresia = get_object_or_404(
            Membresia, 
            usuario=usuario, 
            estacion=estacion, 
            estado__in=[Membresia.Estado.ACTIVO, Membresia.Estado.INACTIVO]
        )

        # VALIDAR ROLES
        # 1. Obtenemos la lista de IDs que el usuario envió desde el formulario.
        selected_roles_ids_str = request.POST.getlist('roles')

        # 2. Obtenemos el CONJUNTO de IDs de roles que son REALMENTE VÁLIDOS para esta estación.
        #    (Los universales + los de la estación). Usar un set() es muy eficiente.
        roles_validos_ids = set(Rol.objects.filter(
            Q(estacion__isnull=True) | Q(estacion=estacion)
        ).values_list('id', flat=True))

        # 3. Validamos la lista del usuario.
        #    Convertimos los IDs de string a int y nos quedamos SOLO con los que
        #    están presentes en nuestro conjunto de roles válidos.
        roles_finales_para_guardar = []
        for role_id_str in selected_roles_ids_str:
            try:
                role_id = int(role_id_str)
                if role_id in roles_validos_ids:
                    roles_finales_para_guardar.append(role_id)
                else:
                    print(f"ALERTA DE SEGURIDAD: El usuario {request.user.id} intentó asignar el rol no válido {role_id} al usuario {usuario_id}.")
            except (ValueError, TypeError):
                # Ignorar si el dato enviado no es un número válido.
                continue

        
        # Usamos set() para actualizar la relación ManyToMany de forma eficiente.
        membresia.roles.set(roles_finales_para_guardar)
        
        messages.success(request, f"Roles de '{usuario.get_full_name.title()}' actualizados correctamente.")
        return redirect('gestion_usuarios:ruta_ver_usuario', id=usuario.id) # Ajusta la URL de redirección




class UsuarioRestablecerContrasena(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, UsuarioDeMiEstacionMixin, View):
    """
    Vista para que un administrador inicie el proceso de restablecimiento
    de contraseña para otro usuario.
    """
    permission_required = 'gestion_usuarios.accion_usuarios_restablecer_contrasena'
    
    def post(self, request, id, *args, **kwargs):
        # El mixin UsuarioDeMiEstacionMixin ya ha verificado que el admin
        # tiene derecho a gestionar a este usuario.

        usuario_a_resetear = get_object_or_404(Usuario, id=id)

        if not usuario_a_resetear.email:
            messages.error(request, f"El usuario {usuario_a_resetear.get_full_name()} no tiene un correo electrónico registrado para enviarle el enlace.")
            return redirect(reverse('gestion_usuarios:ruta_ver_usuario', kwargs={'id': id}))

        # Usamos el formulario de reseteo de Django, pasándole el email del usuario.
        form = PasswordResetForm({'email': usuario_a_resetear.email})

        if form.is_valid():
            # El método save() se encarga de todo.
            form.save(
                request=request,
                from_email='noreply@bomberil.cl',
                email_template_name='acceso/emails/password_reset_email.txt',
                html_email_template_name='acceso/emails/password_reset_email.html',
                subject_template_name='acceso/emails/password_reset_subject.txt',
                
                # --- LÍNEA CLAVE AÑADIDA ---
                # Le decimos a Django que busque las URLs de reseteo
                # en el namespace 'acceso'.
                domain_override='acceso'
            )
            messages.success(request, f"Se ha enviado un correo para restablecer la contraseña a {usuario_a_resetear.email}.")

        return redirect(reverse('gestion_usuarios:ruta_ver_usuario', kwargs={'id': id}))




class UsuarioVerPermisos(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin,UsuarioDeMiEstacionMixin, View):
    """
    Muestra una lista de solo lectura de todos los permisos que un usuario
    posee en la estación activa, consolidados de todos sus roles.
    """
    permission_required = 'gestion_usuarios.accion_usuarios_ver_permisos_usuario'
    template_name = 'gestion_usuarios/pages/ver_permisos_usuario.html'

    def get(self, request, id, *args, **kwargs):
        # El mixin UsuarioDeMiEstacionMixin ya ha verificado que podemos ver a este usuario.
        usuario = get_object_or_404(Usuario, id=id)
        active_station_id = request.session.get('active_estacion_id')
        
        # Obtenemos la membresía del usuario en la estación actual.
        membresia = get_object_or_404(
            Membresia, 
            usuario=usuario, 
            estacion_id=active_station_id,
            estado__in=[Membresia.Estado.ACTIVO, Membresia.Estado.INACTIVO]
        )

        # Recopilamos todos los permisos de todos los roles del usuario.
        # Usamos un conjunto (set) para evitar duplicados si dos roles
        # tuvieran el mismo permiso.
        permisos_del_usuario = set()
        for rol in membresia.roles.prefetch_related('permisos__content_type'):
            permisos_del_usuario.update(rol.permisos.all())
        
        # Agrupamos los permisos por módulo/app para una mejor visualización.
        permisos_agrupados = defaultdict(list)
        for perm in sorted(list(permisos_del_usuario), key=lambda p: p.name):
            # Usamos el verbose_name de la app del modelo al que pertenece el permiso
            if perm.content_type.model_class():
                app_config = perm.content_type.model_class()._meta.app_config
                module_name = app_config.verbose_name
            else: # Para permisos anclados a 'common'
                module_name = "Permisos Generales"
                
            permisos_agrupados[module_name].append(perm)

        context = {
            'membresia': membresia,
            'permisos_agrupados': dict(sorted(permisos_agrupados.items())),
            'total_permisos': len(permisos_del_usuario)
        }
        
        return render(request, self.template_name, context)