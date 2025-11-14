import pprint
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.models import Permission
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.forms import PasswordResetForm
from django.db import IntegrityError, transaction
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseNotAllowed, Http404
from django.utils import timezone
from django.db.models import Q, Count
from collections import defaultdict
from django.apps import apps

# Clases para paginación manual
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Usuario, Membresia, Rol
from .forms import FormularioCrearUsuario, FormularioEditarUsuario, FormularioRol
from .mixins import UsuarioDeMiEstacionMixin, RolValidoParaEstacionMixin, MembresiaGestionableMixin
from apps.common.mixins import ModuleAccessMixin, ObjectInStationRequiredMixin, BaseEstacionMixin
from .utils import generar_contraseña_segura
from apps.gestion_inventario.models import Estacion



class UsuarioInicioView(BaseEstacionMixin, View):
    '''Vista para la página inicial de Gestión de Usuarios'''

    def get(self, request):
        return render(request, "gestion_usuarios/pages/home.html")



class UsuarioListaView(BaseEstacionMixin, PermissionRequiredMixin, View):
    '''Vista para listar usuarios con membresías vigentes en la estación. Se excluyen membresías con el estado "FINALIZADO".'''

    template_name = "gestion_usuarios/pages/lista_usuarios.html"
    permission_required = 'gestion_usuarios.accion_usuarios_ver_usuarios_compania'
    model = Membresia
    paginate_by = 20

    def get_queryset(self):    
        queryset = (
            self.model.objects
            .filter(
                estacion_id=self.estacion_activa,
                estado__in=[self.model.Estado.ACTIVO, self.model.Estado.INACTIVO]
            )
            .select_related('usuario')
            .prefetch_related('roles') # Optimización para cargar roles
        )

        # 3. Aplicamos el filtro de Búsqueda (q)
        # Usamos self.search_q, que definiremos en el método get()
        if hasattr(self, 'search_q') and self.search_q:
            queryset = queryset.filter(
                Q(usuario__first_name__icontains=self.search_q) |
                Q(usuario__last_name__icontains=self.search_q) |
                Q(usuario__email__icontains=self.search_q)
            )

        # 4. Aplicamos el filtro de Estado (estado)
        if hasattr(self, 'filter_estado') and self.filter_estado:
            queryset = queryset.filter(estado=self.filter_estado)

        # 5. Aplicamos el filtro de Rol (rol)
        if hasattr(self, 'filter_rol') and self.filter_rol:
            queryset = queryset.filter(roles__id=self.filter_rol)

        # Usamos .distinct() por si un usuario tiene múltiples roles
        # y el filtro de rol causa duplicados.
        return queryset.distinct().order_by('usuario__first_name', 'usuario__last_name')
    
    def get_context_data(self):
        """
        Este método ahora obtiene el queryset filtrado,
        lo pagina manualmente y añade el contexto extra.
        """
        
        # Obtenemos la lista filtrada de membresías
        membresias_filtradas = self.get_queryset()

        # 6. Lógica de Paginación Manual
        paginator = Paginator(membresias_filtradas, self.paginate_by)
        page_number = self.request.GET.get('page') # Obtenemos el N° de página

        try:
            page_obj = paginator.get_page(page_number)
        except PageNotAnInteger:
            # Si 'page' no es un entero, muestra la primera página
            page_obj = paginator.get_page(1)
        except EmptyPage:
            # Si 'page' está fuera de rango, muestra la última página
            page_obj = paginator.get_page(paginator.num_pages)

        # 7. Creamos el contexto final para la plantilla
        context = {
            # El objeto principal que itera la plantilla
            'page_obj': page_obj,
            
            # El contexto para "recordar" los filtros en la plantilla
            'current_q': getattr(self, 'search_q', ''),
            'current_estado': getattr(self, 'filter_estado', ''),
            'current_rol': getattr(self, 'filter_rol', ''),
            
            # El contexto para llenar el dropdown de roles
            'todos_los_roles': Rol.objects.filter(
                Q(estacion_id=self.estacion_activa) | Q(estacion__isnull=True)
            ).order_by('nombre')
        }
        return context
    
    def get(self, request, *args, **kwargs):
        # 8. Almacenamos los filtros en 'self' para que
        # get_queryset() y get_context_data() puedan acceder a ellos.
        self.search_q = request.GET.get('q', '')
        self.filter_estado = request.GET.get('estado', '')
        self.filter_rol = request.GET.get('rol', '')
        
        # 9. Obtenemos el contexto completo (que ahora incluye paginación y filtros)
        context = self.get_context_data()
        
        # 10. Renderizamos la plantilla
        return render(request, self.template_name, context)



class UsuarioObtenerView(BaseEstacionMixin, PermissionRequiredMixin, MembresiaGestionableMixin, View):
    """
    Vista para obtener el detalle de la última membresía 
    (activa/inactiva) de un usuario en la estación actual.
    """
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/ver_usuario.html"
    permission_required = 'gestion_usuarios.accion_usuarios_ver_usuarios_compania'
    model = Membresia

    # --- 2. Métodos Helper (Obtención y Contexto) ---
    def get_object(self):
        """
        Obtiene la *última* membresía (de cualquier estado)
        del usuario en la estación actual.
        El 'MembresiaGestionableMixin' la validará.
        """
        usuario_id = self.kwargs.get('id') 
        
        try:
            membresia = self.model.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id
            ).select_related('usuario', 'estacion'
            ).prefetch_related('roles').latest('fecha_inicio')
            
            return membresia
            
        except self.model.DoesNotExist:
            # Si no hay NINGUNA membresía, lanzamos 404
            raise Http404(
                "No se encontró ninguna membresía "
                "para este usuario en la estación actual."
            )

    def get_context_data(self, **kwargs):
        """Prepara el contexto para el template."""
        context = {
            # 'self.object' fue establecido y validado por el mixin
            'membresia': self.object 
        }
        return context

    def get(self, request, *args, **kwargs):
        # (El 'dispatch' del mixin ya llamó a 'get_object'
        # y validó el estado. Si era 'FINALIZADO', ya redirigió)
        
        context = self.get_context_data()
        return render(request, self.template_name, context)




class UsuarioAgregarView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista para agregar un usuario existente (sin membresía activa)
    a la estación actual.
    """
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/agregar_usuario.html"
    permission_required = 'gestion_usuarios.accion_usuarios_crear_usuario'
    # URLs para redirección
    success_redirect_url = 'gestion_usuarios:ruta_lista_usuarios'
    fail_redirect_url = 'gestion_usuarios:ruta_agregar_usuario'


    def get(self, request, *args, **kwargs):
        """Maneja GET: Simplemente renderiza el template."""
        return render(request, self.template_name)


    def post(self, request, *args, **kwargs):
        """
        Maneja POST: Valida y crea la nueva membresía.
        """
        
        # 1. OBTENER DATOS de la petición
        usuario_id = request.POST.get('usuario_id')

        # 2. VALIDAR DATOS DE ENTRADA
        if not usuario_id:
            messages.error(request, 'No se proporcionó un ID de usuario.')
            return redirect(self.fail_redirect_url)

        try:
            # 3. OBTENER OBJETOS
            usuario = Usuario.objects.get(id=usuario_id)
            
            # 4. REGLA DE NEGOCIO: Verificar que el usuario esté disponible
            # (Usamos el Enum del modelo como buena práctica)
            estados_restringidos = [
                Membresia.Estado.ACTIVO,
                Membresia.Estado.INACTIVO
            ]
            
            if Membresia.objects.filter(
                usuario=usuario, 
                estado__in=estados_restringidos
            ).exists():
                messages.warning(request, f'El usuario {usuario.get_full_name().title()} ya se encuentra activo o inactivo en otra estación.')
                return redirect(self.fail_redirect_url)

            # 5. CREAR LA MEMBRESÍA (envuelta en transacción)
            with transaction.atomic():
                Membresia.objects.create(
                    usuario=usuario,
                    estacion=self.estacion_activa, # <-- Usamos el objeto del mixin
                    estado=Membresia.Estado.ACTIVO, # <-- Usamos el Enum
                    fecha_inicio=timezone.now().date()
                )

            messages.success(request, f'¡{usuario.get_full_name().title()} ha sido agregado a la estación exitosamente!')
            return redirect(self.success_redirect_url)

        except Usuario.DoesNotExist:
            messages.error(request, 'El usuario que intentas agregar no existe.')
            return redirect(self.fail_redirect_url)
    




class UsuarioCrearView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista para crear un nuevo Usuario y su Membresía inicial.
    Refactorizada con el patrón de helpers de CBV.
    """
    
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/crear_usuario.html"
    permission_required = 'gestion_usuarios.accion_usuarios_crear_usuario'
    form_class = FormularioCrearUsuario
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_usuarios')

    # --- 2. Métodos Helper (Formulario, Contexto) ---
    def get_form(self, data=None, files=None):
        """Helper para instanciar el formulario (incluye files)."""
        return self.form_class(data, files)

    def get_context_data(self, **kwargs):
        """Helper para poblar el contexto."""
        context = {'formulario': kwargs.get('form')}
        return context


    def get(self, request, *args, **kwargs):
        form = self.get_form()
        context = self.get_context_data(form=form)
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        form = self.get_form(request.POST, request.FILES)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
            

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # 1. Obtener la estación (del Mixin)
                estacion_actual = self.estacion_activa

                # 2. Crear el usuario
                datos_limpios = form.cleaned_data
                contrasena_plana = generar_contraseña_segura()

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

                # 3. Crear membresía inicial
                Membresia.objects.create(
                    usuario=nuevo_usuario,
                    estacion=estacion_actual,
                    estado=Membresia.Estado.ACTIVO, # Usando el Enum
                    fecha_inicio=timezone.now().date()
                )

            print(f"Contraseña para {nuevo_usuario.email}: {contrasena_plana}")
            messages.success(self.request, f"Usuario {nuevo_usuario.get_full_name().title()} creado y asignado a la estación exitosamente.")
            return redirect(self.success_url)

        except IntegrityError:
            # Si 'create_user' falla (RUT/email duplicado)
            messages.error(self.request, "Ya existe un usuario con el mismo RUT o correo electrónico.")
        except Exception as e:
            # Captura cualquier otro error inesperado
            print(f"Ocurrió un error inesperado: {e}")
            messages.error(self.request, "Ocurrió un error inesperado. Intenta nuevamente más tarde.")
        
        # Si la transacción falló, volvemos a renderizar el formulario
        return self.form_invalid(form)
    

    def form_invalid(self, form):
        # Añadimos un mensaje de error solo si 'form_valid' no lo hizo ya
        if not messages.get_messages(self.request):
            messages.error(self.request, "Formulario no válido. Por favor, revisa los campos.")
            
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)




class UsuarioEditarView(BaseEstacionMixin, PermissionRequiredMixin, MembresiaGestionableMixin, View):
    """
    Vista para editar la información personal de un Usuario.
    
    SOLUCIÓN:
    1. 'MembresiaGestionableMixin' valida que la 'Membresia' (obtenida por 'id'
       de la URL) sea ACTIVA/INACTIVA y pertenezca a la estación.
    2. Los métodos 'get' y 'post' usan 'self.object.usuario' (el Usuario)
       como la instancia para el formulario.
    """
    
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/editar_usuario.html"
    permission_required = 'gestion_usuarios.accion_usuarios_modificar_info_personal'
    form_class = FormularioEditarUsuario
    model = Usuario # El formulario edita un Usuario
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_usuarios')
    
    # Personalizamos el mensaje del mixin para esta vista
    mensaje_no_gestiona = (
        "No se puede editar este usuario porque "
        "su membresía está 'Finalizada'."
    )


    # --- 2. Método de Obtención (Requerido por el Mixin) ---
    def get_object(self):
        """
        Este método es llamado por 'MembresiaGestionableMixin'.
        Obtiene la *última membresía* basada en el 'usuario_id' de la URL.
        """
        usuario_id = self.kwargs.get('id') 
        
        try:
            # Buscamos la *última* membresía de este usuario
            # en la estación activa.
            membresia = Membresia.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id
            ).latest('fecha_inicio')
            
            return membresia
            
        except Membresia.DoesNotExist:
            raise Http404(
                "No se encontró ninguna membresía para este usuario "
                "en la estación actual."
            )


    # --- 3. Métodos Helper (sin cambios) ---
    def get_form(self, data=None, files=None, instance=None):
        return self.form_class(data, files, instance=instance)

    def get_context_data(self, **kwargs):
        context = {
            'formulario': kwargs.get('form'),
            'usuario': kwargs.get('usuario_obj'),
            'membresia': self.object # 'self.object' es la Membresia
        }
        return context

    def get_success_url(self):
        return self.success_url


    # --- 4. Manejador GET ---
    def get(self, request, *args, **kwargs):
        usuario_a_editar = self.object.usuario # 'self.object' (la Membresia) ya fue validada por el mixin.
        
        form = self.get_form(instance=usuario_a_editar)
        context = self.get_context_data(form=form, usuario_obj=usuario_a_editar)
        return render(request, self.template_name, context)


    # --- 5. Manejador POST ---
    def post(self, request, *args, **kwargs):
        usuario_a_editar = self.object.usuario # 'self.object' (la Membresia) ya fue validada por el mixin.
        
        form = self.get_form(
            request.POST, 
            request.FILES, 
            instance=usuario_a_editar
        )

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
          
            
    # --- 6. Lógica de Formulario ---
    def form_valid(self, form):
        usuario = form.save()
        messages.success(self.request, f"Usuario {usuario.get_full_name().title()} actualizado exitosamente.")
        return redirect(self.get_success_url())
    
    def form_invalid(self, form):
        messages.error(self.request, "Formulario no válido. Por favor, revisa los datos.")
        context = self.get_context_data(
            form=form, 
            usuario_obj=self.object.usuario 
        )
        return render(self.request, self.template_name, context)



class UsuarioDesactivarView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista (solo POST) para desactivar la membresía de un usuario
    (cambia su estado a 'INACTIVO').
    """
    
    # --- 1. Atributos de Configuración ---
    permission_required = 'gestion_usuarios.accion_usuarios_desactivar_usuario'
    success_url = reverse_lazy("gestion_usuarios:ruta_lista_usuarios")


    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])


    def get_object(self):
        """
        Obtiene la membresía que se va a desactivar.
        Lanza Http404 si no se encuentra, o si no está 'ACTIVA'.
        """
        usuario_id = self.kwargs.get('id')
        
        try:
            # 1. Buscamos la *última* membresía (para evitar MultipleObjectsReturned)
            #    'self.estacion_activa_id' viene de BaseEstacionMixin.
            membresia = Membresia.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id
            ).latest('fecha_inicio')
        
        except Membresia.DoesNotExist:
            raise Http404("El usuario no tiene una membresía en esta estación.")

        # 2. Lógica de Negocio: Solo podemos desactivar membresías 'ACTIVA'
        if membresia.estado != Membresia.Estado.ACTIVO:
            raise Http404(f"No se puede desactivar esta membresía. Su estado actual es '{membresia.estado}'.")
        
        return membresia


    def post(self, request, *args, **kwargs):
        try:
            # 1. Obtenemos el objeto (ya validado por get_object)
            membresia = self.get_object() 
            
            # 2. Ejecutamos la acción
            membresia.estado = Membresia.Estado.INACTIVO
            membresia.save()

            messages.success(request, f"El usuario '{membresia.usuario.get_full_name().title()}' ha sido desactivado correctamente.")

        except Http404 as e:
            # 3. Si get_object falló, mostramos el error
            messages.error(request, str(e))
            
        except Exception as e:
            # 4. Cualquier otro error
            messages.error(request, f"Ocurrió un error inesperado: {e}")

        # 5. Redirigimos
        return redirect(self.success_url)




class UsuarioActivarView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista (solo POST) para activar la membresía de un usuario
    (cambia su estado a 'ACTIVO').
    """
    # --- 1. Atributos de Configuración ---
    permission_required = 'gestion_usuarios.accion_usuarios_desactivar_usuario'
    
    success_url = reverse_lazy("gestion_usuarios:ruta_lista_usuarios")
    model = Membresia

    # --- 2. Método GET (Correcto: esta acción no debe ser GET) ---
    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    # --- 3. Método de Obtención de Objeto ---
    def get_object(self):
        """
        Obtiene la membresía que se va a activar.
        Lanza Http404 si no se encuentra, o si no está 'INACTIVA'.
        """
        usuario_id = self.kwargs.get('id')
        
        try:
            # 1. Buscamos la *última* membresía de este usuario
            #    en la estación activa (viene de BaseEstacionMixin)
            membresia = self.model.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id
            ).latest('fecha_inicio')
        
        except self.model.DoesNotExist:
            raise Http404("El usuario no tiene una membresía en esta estación.")

        # 2. Lógica de Negocio: Solo podemos activar membresías 'INACTIVA'
        if membresia.estado != self.model.Estado.INACTIVO:
            raise Http404(f"No se puede activar esta membresía. Su estado actual es '{membresia.estado}'.")
        
        return membresia

    # --- 4. Manejador POST (Lógica de la Acción) ---
    def post(self, request, *args, **kwargs):
        try:
            # 1. Obtenemos el objeto (ya validado por get_object)
            membresia = self.get_object() 
            
            # 2. Ejecutamos la acción
            membresia.estado = self.model.Estado.ACTIVO # <-- Usando Enum
            membresia.save()

            messages.success(request, f"El usuario '{membresia.usuario.get_full_name().title()}' ha sido activado correctamente.")

        except Http404 as e:
            # 3. Si get_object falló, mostramos el error
            messages.error(request, str(e))
            
        except Exception as e:
            # 4. Cualquier otro error
            messages.error(request, f"Ocurrió un error inesperado: {e}")

        # 5. Redirigimos
        return redirect(self.success_url)




class RolListaView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Muestra una lista de roles (globales y de la estación)
    con filtros de búsqueda y tipo.
    """

    template_name = "gestion_usuarios/pages/lista_roles.html"
    permission_required = 'gestion_usuarios.accion_usuarios_ver_roles'

    def get(self, request, *args, **kwargs):

        # 1. Obtener el ID de la estación activa
        estacion_id = request.session.get('active_estacion_id')

        if not estacion_id:
            messages.error(request, "No se pudo determinar la estación activa. Por favor, inicie sesión de nuevo.")
            # Redirige a una ruta segura, por ejemplo el dashboard
            return redirect('portal:ruta_portal') 
        
        estacion = get_object_or_404(Estacion, id=estacion_id)

        # 2. Obtener parámetros de filtro de la URL
        self.search_q = request.GET.get('q', '')
        self.filter_tipo = request.GET.get('tipo', '')

        # 3. Consulta base: roles globales (isnull=True) Y de esta estación
        query = Q(estacion__isnull=True) | Q(estacion=estacion)
        roles_queryset = Rol.objects.filter(query)

        # 4. Aplicar filtros de búsqueda
        if self.search_q:
            roles_queryset = roles_queryset.filter(nombre__icontains=self.search_q)

        if self.filter_tipo == 'global':
            roles_queryset = roles_queryset.filter(estacion__isnull=True)
        elif self.filter_tipo == 'personalizado':
            roles_queryset = roles_queryset.filter(estacion__isnull=False) # Solo de la estación

        # 5. Anotar el conteo de permisos y ordenar
        # .annotate() es la forma eficiente de obtener el conteo
        roles_filtrados = roles_queryset.annotate(
            permisos_count=Count('permisos')
        ).order_by('nombre')


        # 6. Preparar contexto
        context = {
            'estacion': estacion,
            'roles': roles_filtrados, # El queryset filtrado y anotado
            
            # Devolvemos los filtros para repoblar el formulario
            'current_q': self.search_q,
            'current_tipo': self.filter_tipo,
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




class UsuarioFinalizarMembresiaView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, UsuarioDeMiEstacionMixin, View):
    """
    Muestra una página de confirmación y gestiona la finalización
    de la membresía de un usuario en la estación activa.
    """
    template_name = 'gestion_usuarios/pages/finalizar_membresia.html'
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_finalizar_membresia'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_usuarios')

    def dispatch(self, request, *args, **kwargs):
        """
        Obtiene y almacena la membresía a finalizar.
        El mixin UsuarioDeMiEstacionMixin ya validó que el usuario
        pertenece a nuestra estación.
        """
        usuario_id = kwargs.get('id')
        estacion_id = request.session.get('active_estacion_id')
        
        # Obtenemos la membresía activa o inactiva del usuario
        self.membresia = get_object_or_404(
            Membresia,
            usuario_id=usuario_id,
            estacion_id=estacion_id,
            estado__in=[Membresia.Estado.ACTIVO, Membresia.Estado.INACTIVO]
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """Muestra la página de confirmación."""
        context = {
            'membresia': self.membresia
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Ejecuta la finalización de la membresía.
        """
        usuario_nombre = self.membresia.usuario.get_full_name
        
        # Actualizamos el estado y la fecha de fin
        self.membresia.estado = Membresia.Estado.FINALIZADO
        self.membresia.fecha_fin = timezone.now().date()
        self.membresia.save()
        
        messages.success(request, f"La membresía de '{usuario_nombre}' ha sido finalizada correctamente.")
        return redirect(self.success_url)




class HistorialMembresiasView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Muestra un historial paginado de todas las membresías FINALIZADAS
    de la estación activa, con filtros de búsqueda y fecha.
    """
    template_name = 'gestion_usuarios/pages/historial_membresias.html'
    permission_required = 'gestion_usuarios.accion_usuarios_ver_usuarios_compania'
    model = Membresia
    paginate_by = 20

    def get_queryset(self):
        """
        Obtiene el queryset base (solo membresías finalizadas)
        y aplica los filtros de búsqueda y fecha.
        """
        
        # 1. Queryset Base: Solo membresías FINALIZADAS de la estación activa.
        # (self.estacion_activa viene del BaseEstacionMixin)
        queryset = (
            self.model.objects
            .filter(
                estacion_id=self.estacion_activa,
                estado=Membresia.Estado.FINALIZADO
            )
            .select_related('usuario')
            .prefetch_related('roles')
            .order_by('-fecha_fin') # Ordenar por fecha de fin (más reciente primero)
        )

        # 2. Aplicar filtro de Búsqueda (q)
        if hasattr(self, 'search_q') and self.search_q:
            queryset = queryset.filter(
                Q(usuario__first_name__icontains=self.search_q) |
                Q(usuario__last_name__icontains=self.search_q) |
                Q(usuario__email__icontains=self.search_q) |
                Q(usuario__rut__icontains=self.search_q)
            )

        # 3. Aplicar filtros de Fecha (sobre fecha_fin)
        if hasattr(self, 'fecha_desde') and self.fecha_desde:
            queryset = queryset.filter(fecha_fin__gte=self.fecha_desde)
        if hasattr(self, 'fecha_hasta') and self.fecha_hasta:
            queryset = queryset.filter(fecha_fin__lte=self.fecha_hasta)
            
        return queryset.distinct()

    def get_context_data(self):
        """
        Prepara el contexto para la plantilla, incluyendo la paginación
        y los valores de los filtros.
        """
        membresias_filtradas = self.get_queryset()

        paginator = Paginator(membresias_filtradas, self.paginate_by)
        page_number = self.request.GET.get('page')

        try:
            page_obj = paginator.get_page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.get_page(1)
        except EmptyPage:
            page_obj = paginator.get_page(paginator.num_pages)

        context = {
            'page_obj': page_obj,
            'current_q': getattr(self, 'search_q', ''),
            'current_fecha_desde': getattr(self, 'fecha_desde', ''),
            'current_fecha_hasta': getattr(self, 'fecha_hasta', ''),
        }
        return context

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET.
        Captura los filtros de la URL antes de llamar a get_context_data.
        """
        self.search_q = request.GET.get('q', '')
        self.fecha_desde = request.GET.get('fecha_desde', '')
        self.fecha_hasta = request.GET.get('fecha_hasta', '')
        
        context = self.get_context_data()
        return render(request, self.template_name, context)