import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from core.settings import DEFAULT_FROM_EMAIL
from django.views import View
from django.views.generic import ListView
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import Permission
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.forms import PasswordResetForm
from django.db import IntegrityError, transaction
from django.db.models import Q, Count, ProtectedError
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseNotAllowed, Http404
from django.utils import timezone
from collections import defaultdict
from django.apps import apps
from django.core.exceptions import PermissionDenied
from user_sessions.models import Session

# Clases para paginación manual
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Usuario, Membresia, Rol, RegistroActividad
from .forms import FormularioCrearUsuario, FormularioEditarUsuario, FormularioRol
from .mixins import MembresiaGestionableMixin
from .utils import servicio_crear_usuario_y_notificar
from apps.common.mixins import BaseEstacionMixin, AuditoriaMixin, CustomPermissionRequiredMixin


class UsuarioInicioView(BaseEstacionMixin, View):
    '''
    Dashboard principal de Gestión de Usuarios.
    Muestra KPIs, Gráficos, Feed de Actividad y Alertas de Higiene.
    '''
    template_name = "gestion_usuarios/pages/home.html"

    def get(self, request):
        estacion = self.estacion_activa
        hoy = timezone.now()
        hace_90_dias = hoy - timedelta(days=90)
        hace_6_meses = hoy - timedelta(days=180)

        # 1. KPIs Principales
        membresias_activas = Membresia.objects.filter(estacion=estacion, estado='ACTIVO')
        membresias_inactivas = Membresia.objects.filter(estacion=estacion, estado='INACTIVO')
        
        # Roles (Locales + Globales visibles)
        roles_count = Rol.objects.filter(
            Q(estacion=estacion) | Q(estacion__isnull=True)
        ).count()
        
        # Actividad de hoy
        actividad_hoy = RegistroActividad.objects.filter(
            estacion=estacion,
            fecha__date=hoy.date()
        ).count()

        # 2. Datos para Gráficos (Chart.js)
        
        # A. Distribución de Roles (Top 5 + Otros)
        # Contamos cuántas membresías ACTIVAS tienen cada rol
        roles_dist = Rol.objects.filter(
            asignaciones__estacion=estacion,
            asignaciones__estado='ACTIVO'
        ).annotate(total=Count('asignaciones')).order_by('-total')

        labels_roles = [r.nombre for r in roles_dist[:5]]
        data_roles = [r.total for r in roles_dist[:5]]
        
        # B. Curva de Ingresos (Últimos 6 meses)
        # Agrupamos por mes
        ingresos_por_mes = (
            membresias_activas
            .filter(fecha_inicio__gte=hace_6_meses)
            .extra(select={'month': "EXTRACT(month FROM fecha_inicio)"}) # Nota: Esto varía según DB (SQLite/Postgres), usaremos python para ser agnósticos
        )
        # Procesamiento agnóstico en Python para la gráfica de línea
        from collections import  OrderedDict
        meses_data = OrderedDict()
        for i in range(5, -1, -1):
            mes_ref = hoy - timedelta(days=i*30)
            mes_key = mes_ref.strftime('%b') # Ej: "Nov"
            meses_data[mes_key] = 0
            
        for m in ingresos_por_mes:
            mes_key = m.fecha_inicio.strftime('%b')
            if mes_key in meses_data:
                meses_data[mes_key] += 1

        # 3. Feed de Actividad (Últimos 10)
        actividad_reciente = RegistroActividad.objects.filter(
            estacion=estacion
        ).select_related('actor').order_by('-fecha')[:10]

        # 4. Alertas de Higiene (Seguridad y Limpieza)
        alertas = []
        
        # Alerta A: Usuarios activos sin roles (Riesgo/Error)
        usuarios_sin_rol = membresias_activas.annotate(num_roles=Count('roles')).filter(num_roles=0).count()
        if usuarios_sin_rol > 0:
            alertas.append({
                'tipo': 'danger',
                'icono': 'fa-user-shield',
                'mensaje': f'Hay {usuarios_sin_rol} usuarios activos sin ningún rol asignado.',
                'accion_url': reverse('gestion_usuarios:ruta_lista_usuarios') + '?q=&estado=ACTIVO&rol=',
                'accion_texto': 'Revisar'
            })

        # Alerta B: Usuarios "Fantasma" (Sin login > 90 días)
        usuarios_fantasma = membresias_activas.filter(
            usuario__last_login__lt=hace_90_dias
        ).count()
        if usuarios_fantasma > 0:
            alertas.append({
                'tipo': 'warning',
                'icono': 'fa-user-clock',
                'mensaje': f'{usuarios_fantasma} usuarios no han iniciado sesión en los últimos 3 meses.',
                'accion_url': reverse('gestion_usuarios:ruta_lista_usuarios'), # Se puede crear un filtro especial
                'accion_texto': 'Ver lista'
            })

        context = {
            'kpi': {
                'activos': membresias_activas.count(),
                'inactivos': membresias_inactivas.count(),
                'roles': roles_count,
                'actividad': actividad_hoy
            },
            'graficos': {
                'roles_labels': json.dumps(labels_roles),
                'roles_data': json.dumps(data_roles),
                'historia_labels': json.dumps(list(meses_data.keys())),
                'historia_data': json.dumps(list(meses_data.values())),
            },
            'actividad_reciente': actividad_reciente,
            'alertas': alertas
        }
        return render(request, self.template_name, context)



class UsuarioListaView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
    '''Vista para listar usuarios con membresías vigentes en la estación. Se excluyen membresías con el estado "FINALIZADO".'''

    template_name = "gestion_usuarios/pages/lista_usuarios.html"
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_ver_usuarios'
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



class UsuarioObtenerView(BaseEstacionMixin, CustomPermissionRequiredMixin, MembresiaGestionableMixin, View):
    """
    Vista para obtener el detalle de la última membresía 
    (activa/inactiva) de un usuario en la estación actual.
    """
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/ver_usuario.html"
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_ver_usuarios'
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
            ).prefetch_related('roles').latest('created_at')
            
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




class UsuarioAgregarView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para agregar un usuario existente (sin membresía activa)
    a la estación actual.
    """
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/agregar_usuario.html"
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_crear_usuario'
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
                messages.warning(request, f'El usuario {usuario.get_full_name.title()} ya se encuentra activo o inactivo en otra estación.')
                return redirect(self.fail_redirect_url)

            # 5. CREAR LA MEMBRESÍA (envuelta en transacción)
            with transaction.atomic():
                Membresia.objects.create(
                    usuario=usuario,
                    estacion=self.estacion_activa, # <-- Usamos el objeto del mixin
                    estado=Membresia.Estado.ACTIVO, # <-- Usamos el Enum
                    fecha_inicio=timezone.now().date()
                )
                # --- AUDITORÍA ---
                self.auditar(
                    verbo="agregó a la compañía a",
                    objetivo=usuario
                )

            messages.success(request, f'¡{usuario.get_full_name.title()} ha sido agregado a la estación exitosamente!')
            return redirect(self.success_redirect_url)

        except Usuario.DoesNotExist:
            messages.error(request, 'El usuario que intentas agregar no existe.')
            return redirect(self.fail_redirect_url)
    




class UsuarioCrearView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para crear un nuevo Usuario y su Membresía inicial.
    Refactorizada con el patrón de helpers de CBV.
    """
    
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/crear_usuario.html"
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_crear_usuario'
    form_class = FormularioCrearUsuario
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_usuarios')

    # --- 2. Métodos Helper (Formulario, Contexto) ---
    def get_form(self, data=None, files=None):
        """Helper para instanciar el formulario (incluye files y valores iniciales)."""
        
        # Si es una petición GET (sin datos POST), intentamos pre-llenar
        if data is None:
            rut_prellenado = self.request.GET.get('rut') # Capturamos '?rut=...'
            if rut_prellenado:
                # 'initial' es la forma correcta de pre-llenar un Django Form
                return self.form_class(initial={'rut': rut_prellenado})
        
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
            # 4. CREACIÓN DE USUARIO, MEMBRESÍA Y GENERACIÓN DEL CORREO DE BIENVENIDA
            nuevo_usuario = servicio_crear_usuario_y_notificar(
                datos_usuario=form.cleaned_data,
                estacion=self.estacion_activa,
                request=self.request
            )

            # 5. Auditoría
            self.auditar(
                verbo="creó y envió invitación a",
                objetivo=nuevo_usuario,
                detalles={'rut': nuevo_usuario.rut}
            )

            messages.success(self.request, f"Usuario creado. Se ha enviado un correo a {nuevo_usuario.email} para que configure su contraseña.")
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




class UsuarioEditarView(BaseEstacionMixin, CustomPermissionRequiredMixin, MembresiaGestionableMixin, AuditoriaMixin, View):
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
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_modificar_info'
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
            ).latest('created_at')
            
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
        try:
            usuario = form.save()

            # --- AUDITORÍA (Con Diff de campos) ---
            if form.changed_data:
                self.auditar(
                    verbo="modificó la información personal de",
                    objetivo=usuario,
                    detalles={'campos_modificados': form.changed_data}
                )

            messages.success(self.request, f"Usuario {usuario.get_full_name.title()} actualizado exitosamente.")
            return redirect(self.get_success_url())
        
        except Exception as e:
            messages.error(self.request, f"Error al actualizar el usuario: {str(e)}")
            return self.form_invalid(form)
        
    
    def form_invalid(self, form):
        messages.error(self.request, "Formulario no válido. Por favor, revisa los datos.")
        context = self.get_context_data(
            form=form, 
            usuario_obj=self.object.usuario 
        )
        return render(self.request, self.template_name, context)



class UsuarioDesactivarView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista (solo POST) para desactivar la membresía de un usuario
    (cambia su estado a 'INACTIVO').
    """
    
    # --- 1. Atributos de Configuración ---
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_desactivar_cuenta'
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
            ).latest('created_at')
        
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

            # --- AUDITORÍA ---
            self.auditar(
                verbo="desactivó el acceso a la compañía de",
                objetivo=membresia.usuario,
                detalles={'motivo': 'Desactivación manual por administrador'}
            )

            messages.success(request, f"El usuario '{membresia.usuario.get_full_name.title()}' ha sido desactivado correctamente.")

        except Http404 as e:
            # 3. Si get_object falló, mostramos el error
            messages.error(request, str(e))
            
        except Exception as e:
            # 4. Cualquier otro error
            messages.error(request, f"Ocurrió un error inesperado: {e}")

        # 5. Redirigimos
        return redirect(self.success_url)




class UsuarioActivarView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista (solo POST) para activar la membresía de un usuario
    (cambia su estado a 'ACTIVO').
    """
    # --- 1. Atributos de Configuración ---
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_desactivar_cuenta'
    
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
            ).latest('created_at')
        
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

            # --- AUDITORÍA ---
            self.auditar(
                verbo="reactivó el acceso a la compañía de",
                objetivo=membresia.usuario
            )

            messages.success(request, f"El usuario '{membresia.usuario.get_full_name.title()}' ha sido activado correctamente.")

        except Http404 as e:
            # 3. Si get_object falló, mostramos el error
            messages.error(request, str(e))
            
        except Exception as e:
            # 4. Cualquier otro error
            messages.error(request, f"Ocurrió un error inesperado: {e}")

        # 5. Redirigimos
        return redirect(self.success_url)




class RolListaView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
    """
    Muestra una lista de roles (globales y de la estación)
    con filtros de búsqueda y tipo.
    """
    
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/lista_roles.html"
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_ver_roles'

    # --- 2. Método de Consulta (El corazón de la vista) ---
    def get_queryset(self):
        """
        Construye la consulta filtrada de Roles.
        Accede directamente a self.request.GET para los filtros.
        """
        # a. Obtener parámetros de la URL
        search_q = self.request.GET.get('q', '')
        filter_tipo = self.request.GET.get('tipo', '')

        # b. Consulta base: 
        # Roles globales (estacion es Null) O Roles de ESTA estación.
        # Usamos self.estacion_activa (provisto por el Mixin)
        query = Q(estacion__isnull=True) | Q(estacion=self.estacion_activa)
        qs = Rol.objects.filter(query)

        # c. Aplicar filtro de búsqueda (Nombre)
        if search_q:
            qs = qs.filter(nombre__icontains=search_q)

        # d. Aplicar filtro de Tipo (Global vs Personalizado)
        if filter_tipo == 'global':
            qs = qs.filter(estacion__isnull=True)
        elif filter_tipo == 'personalizado':
            qs = qs.filter(estacion__isnull=False)

        # e. Optimización: Anotar conteo y ordenar
        # Usamos distinct=True por seguridad al hacer joins (aunque con Count a veces no es estricto, es buena práctica)
        qs = qs.annotate(
            permisos_count=Count('permisos', distinct=True)
        ).order_by('nombre')

        return qs

    # --- 3. Método de Contexto ---
    def get_context_data(self, **kwargs):
        """Prepara el contexto para el template."""
        context = {
            'estacion': self.estacion_activa, # Del mixin
            'roles': self.get_queryset(),     # Ejecutamos la consulta aquí
            
            # Devolvemos los filtros para mantener el estado en el input/select
            'current_q': self.request.GET.get('q', ''),
            'current_tipo': self.request.GET.get('tipo', ''),
        }
        return context

    # --- 4. Manejador GET ---
    def get(self, request, *args, **kwargs):
        """
        Maneja GET: Solo orquesta la obtención de datos y renderizado.
        """
        context = self.get_context_data()
        return render(request, self.template_name, context)




class RolObtenerView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
    """
    Vista para obtener el detalle de un rol.
    
    SEGURIDAD:
    - BaseEstacionMixin: Garantiza sesión y estación activa.
    - get_object: Garantiza que solo se vean roles Globales 
      o de la Estación Activa.
    """
    
    template_name = "gestion_usuarios/pages/ver_rol.html"
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_ver_roles'


    # --- 1. Método de Obtención (SEGURIDAD CRÍTICA) ---
    def get_object(self):
        """
        Obtiene el rol asegurando que el usuario tenga permiso de verlo.
        Reglas:
        1. El ID debe coincidir.
        2. El rol debe ser GLOBAL (estacion IS NULL) 
           O pertenecer a la estación activa (self.estacion_activa).
        """
        rol_id = self.kwargs.get('id')
        
        # Construimos la query de seguridad
        # Usamos self.estacion_activa (gracias a BaseEstacionMixin)
        filtro_seguridad = Q(estacion__isnull=True) | Q(estacion=self.estacion_activa)
        
        # Optimizamos la consulta con prefetch
        queryset = Rol.objects.filter(filtro_seguridad).prefetch_related('permisos__content_type')
        
        return get_object_or_404(queryset, id=rol_id)


    # --- 2. Lógica de Negocio (Agrupación) ---
    def _agrupar_permisos(self, rol):
        """
        Helper privado que contiene la lógica compleja de agrupación
        de permisos (Padres 'acceso_' e Hijos 'accion_').
        """
        # A. Obtener permisos relevantes del rol
        permisos_del_rol = rol.permisos.filter(
            Q(codename__startswith='acceso_') | Q(codename__startswith='accion_')
        ).select_related('content_type')

        grouped_perms = {} 
        app_labels_found = []

        # B. PRIMERA PASADA: PADRES (acceso_)
        parent_perms = permisos_del_rol.filter(codename__startswith='acceso_')
        
        for perm in parent_perms:
            try:
                # 'acceso_gestion_inventario' -> 'gestion_inventario'
                app_label = perm.codename.split('_', 1)[1]
                config = apps.get_app_config(app_label)
                
                grouped_perms[app_label] = {
                    'verbose_name': config.verbose_name,
                    'main_perm': perm,
                    'children': []
                }
                app_labels_found.append(app_label)
            except (LookupError, IndexError):
                continue 

        # C. SEGUNDA PASADA: HIJOS (accion_)
        child_perms = permisos_del_rol.filter(codename__startswith='accion_')

        for perm in child_perms:
            found_parent = False
            try:
                # Intentamos emparejar el hijo con un padre encontrado
                for app_label in app_labels_found:
                    expected_prefix = f"accion_{app_label}_"
                    
                    if perm.codename.startswith(expected_prefix):
                        grouped_perms[app_label]['children'].append(perm)
                        found_parent = True
                        break
                
                # Si no tiene padre (huérfano), va a "Varios"
                if not found_parent:
                    if 'misc' not in grouped_perms:
                        grouped_perms['misc'] = {
                            'verbose_name': 'Permisos Varios',
                            'main_perm': None,
                            'children': []
                        }
                    grouped_perms['misc']['children'].append(perm)
            
            except Exception as e:
                print(f"Error procesando permiso {perm.codename}: {e}")
                continue 

        # D. Ordenar hijos alfabéticamente
        for app_label in grouped_perms:
            grouped_perms[app_label]['children'].sort(key=lambda x: x.name)
            
        return grouped_perms


    # --- 3. Método de Contexto ---
    def get_context_data(self, **kwargs):
        """Arma el contexto final."""
        
        # Ejecutamos la lógica de agrupación
        grouped_perms = self._agrupar_permisos(self.object)
        
        # Ordenamos los módulos alfabéticamente para la vista
        permisos_ordenados = dict(
            sorted(grouped_perms.items(), key=lambda item: item[1]['verbose_name'])
        )

        context = {
            'rol': self.object,
            'permisos_por_modulo': permisos_ordenados
        }
        return context


    # --- 4. Manejador GET ---
    def get(self, request, *args, **kwargs):
        """
        Orquestador principal.
        """
        self.object = self.get_object() # Valida seguridad y obtiene rol
        context = self.get_context_data() # Procesa la agrupación
        return render(request, self.template_name, context)




class RolEditarView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para editar roles (nombre y descripción).
    
    SEGURIDAD: 
    Sólo permite editar roles que pertenecen explícitamente 
    a la estación activa. Bloquea roles globales y de otras estaciones.
    """
    
    # --- 1. Atributos de Configuración ---
    template_name = "gestion_usuarios/pages/editar_rol.html"
    form_class = FormularioRol
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_gestionar_roles'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')


    # --- 2. Método de Obtención (SEGURIDAD) ---
    def get_object(self):
        """
        Obtiene el rol a editar.
        Filtra estrictamente por el ID de la estación activa.
        """
        rol_id = self.kwargs.get('id')
        
        # BaseEstacionMixin nos da 'self.estacion_activa_id'
        # Al filtrar por estacion_id, excluimos automáticamente:
        # 1. Roles Globales (su estacion_id es None)
        # 2. Roles de otras estaciones (su ID es diferente)
        return get_object_or_404(
            Rol, 
            id=rol_id, 
            estacion_id=self.estacion_activa_id
        )


    # --- 3. Métodos Helper ---
    def get_form(self, data=None, instance=None):
        return self.form_class(data, instance=instance)

    def get_context_data(self, **kwargs):
        context = {
            'formulario': kwargs.get('form'),
            'rol': self.object # Pasamos el objeto validado
        }
        return context

    def get_success_url(self):
        return self.success_url


    # --- 4. Manejador GET ---
    def get(self, request, *args, **kwargs):
        """
        Maneja GET: Muestra el formulario pre-llenado.
        """
        self.object = self.get_object()
        form = self.get_form(instance=self.object)
        
        context = self.get_context_data(form=form)
        return render(request, self.template_name, context)


    # --- 5. Manejador POST ---
    def post(self, request, *args, **kwargs):
        """
        Maneja POST: Valida y guarda.
        """
        self.object = self.get_object()
        form = self.get_form(request.POST, instance=self.object)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


    # --- 6. Lógica de Formulario ---
    def form_valid(self, form):
        """Guarda el rol y redirige."""
        try:
            rol = form.save()
            # --- AUDITORÍA ---
            if form.changed_data:
                self.auditar(
                    verbo="modificó la información del rol",
                    objetivo=rol,
                    objetivo_repr=rol.nombre,
                    detalles={'campos_modificados': form.changed_data}
                )
            messages.success(self.request, f"Rol '{rol.nombre}' actualizado exitosamente.")
            return redirect(self.get_success_url())
    
        except Exception as e:
            messages.error(self.request, f"Error al guardar el rol: {str(e)}")
            return self.form_invalid(form)


    def form_invalid(self, form):
        """Muestra errores de validación."""
        messages.error(self.request, "Formulario no válido. Por favor, revisa los datos.")
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)




class RolCrearView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para crear roles personalizados.
    Los roles se asocian automáticamente a la estación activa del usuario.
    """
    
    # --- 1. Atributos de Configuración ---
    form_class = FormularioRol
    template_name = 'gestion_usuarios/pages/crear_rol.html'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_gestionar_roles'

    # --- 2. Métodos Helper (Formulario y Contexto) ---
    def get_form(self, data=None):
        """
        Helper para instanciar el formulario.
        INYECCIÓN DE DEPENDENCIA: Pasamos 'self.estacion_activa' al form.
        """
        # BaseEstacionMixin ya obtuvo la estación por nosotros
        return self.form_class(data, estacion=self.estacion_activa)

    def get_context_data(self, **kwargs):
        """Helper para poblar el contexto."""
        context = {
            'formulario': kwargs.get('form'),
            'estacion': self.estacion_activa # Disponible en el template si se requiere
        }
        return context

    # --- 3. Manejador GET ---
    def get(self, request, *args, **kwargs):
        """Maneja GET: Muestra formulario vacío."""
        form = self.get_form()
        context = self.get_context_data(form=form)
        return render(request, self.template_name, context)

    # --- 4. Manejador POST ---
    def post(self, request, *args, **kwargs):
        """Maneja POST: Procesa el formulario."""
        form = self.get_form(request.POST)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


    # --- 5. Lógica de Validación ---
    def form_valid(self, form):
        """
        Guarda el rol.
        El formulario se encarga de asignar la estación internamente
        porque se la pasamos en el __init__ (ver get_form).
        """
        try:
            rol = form.save()
            # --- AUDITORÍA ---
            self.auditar(
                verbo="creó el rol personalizado",
                objetivo=rol,
                objetivo_repr=rol.nombre,
                detalles={'nombre': rol.nombre}
            )
            messages.success(self.request, "Rol creado correctamente.")
            return redirect(self.success_url)
        
        except Exception as e:
            messages.error(self.request, f"Error al crear el rol: {str(e)}")
            return self.form_invalid(form)


    def form_invalid(self, form):
        """Muestra errores."""
        messages.error(self.request, "Formulario no válido. Revisa los campos.")
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)




class RolAsignarPermisosView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para asignar permisos a un rol.
    Muestra una lista de TODOS los permisos del sistema agrupados por módulo.
    """
    
    # --- 1. Configuración ---
    template_name = 'gestion_usuarios/pages/asignar_permisos.html'
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_gestionar_roles'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')

    # --- 2. Método de Obtención (Seguridad Idéntica a RolEditarView) ---
    def get_object(self):
        """
        Obtiene el rol a editar.
        Filtra estrictamente por el ID de la estación activa.
        Bloquea roles globales y de otras estaciones.
        """
        rol_id = self.kwargs.get('id')
        return get_object_or_404(
            Rol, 
            id=rol_id, 
            estacion_id=self.estacion_activa_id # Del Mixin
        )

    # --- 3. Helper de Negocio (Agrupación de TODOS los permisos) ---
    def _agrupar_todos_los_permisos(self):
        """
        Obtiene y agrupa TODOS los permisos de negocio del sistema.
        (Lógica similar a RolObtenerView, pero sobre Permission.objects.all)
        """
        # A. Obtener TODOS los permisos relevantes
        all_perms = Permission.objects.filter(
            Q(codename__startswith='acceso_') | Q(codename__startswith='accion_')
        )
        
        grouped_perms = {}
        app_labels_found = []

        # B. PRIMERA PASADA: PADRES (acceso_)
        parent_perms = all_perms.filter(codename__startswith='acceso_')
        for perm in parent_perms:
            try:
                app_label = perm.codename.split('_', 1)[1]
                config = apps.get_app_config(app_label)
                grouped_perms[app_label] = {
                    'verbose_name': config.verbose_name,
                    'main_perm': perm,
                    'children': []
                }
                app_labels_found.append(app_label)
            except (LookupError, IndexError):
                continue

        # C. SEGUNDA PASADA: HIJOS (accion_)
        child_perms = all_perms.filter(codename__startswith='accion_')
        for perm in child_perms:
            try:
                for app_label in app_labels_found:
                    if perm.codename.startswith(f"accion_{app_label}_"):
                        grouped_perms[app_label]['children'].append(perm)
                        break
            except Exception:
                continue

        # D. Ordenar
        for app_label in grouped_perms:
            grouped_perms[app_label]['children'].sort(key=lambda x: x.name)
            
        return grouped_perms

    # --- 4. Método de Contexto ---
    def get_context_data(self, **kwargs):
        """Arma el contexto para la matriz de permisos."""
        
        # 1. Obtenemos el diccionario agrupado
        grouped_perms = self._agrupar_todos_los_permisos()
        
        # 2. Ordenamos los grupos por nombre del módulo
        permissions_by_app = dict(
            sorted(grouped_perms.items(), key=lambda item: item[1]['verbose_name'])
        )
        
        # 3. IDs actuales (para marcar los checkboxes)
        current_ids = set(self.object.permisos.values_list('id', flat=True))

        context = {
            'rol': self.object,
            'permissions_by_app': permissions_by_app,
            'rol_permissions_ids': current_ids
        }
        return context

    # --- 5. Manejador GET ---
    def get(self, request, *args, **kwargs):
        """Maneja GET: Muestra la matriz de selección."""
        self.object = self.get_object() # Valida y obtiene el rol
        context = self.get_context_data()
        return render(request, self.template_name, context)

    # --- 6. Manejador POST ---
    def post(self, request, *args, **kwargs):
        """
        Maneja POST: Guarda la selección de permisos.
        """
        self.object = self.get_object() # Valida y obtiene el rol
        # Obtiene la lista de IDs seleccionados
        selected_ids = request.POST.getlist('permisos')

        try:
            # Actualiza la relación ManyToMany
            self.object.permisos.set(selected_ids)
            # --- AUDITORÍA ---
            self.auditar(
                verbo="actualizó los permisos del rol",
                objetivo=self.object,
                objetivo_repr=self.object.nombre,
                detalles={'total_permisos_asignados': len(selected_ids)}
            )
            messages.success(request, f"Permisos del rol '{self.object.nombre}' actualizados correctamente.")

        except Exception as e:
            messages.error(request, f"Error al guardar los permisos: {str(e)}")
        
        return redirect(self.success_url)




class RolEliminarView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para eliminar un rol personalizado.
    
    SEGURIDAD:
    Sólo permite eliminar roles que pertenecen explícitamente 
    a la estación activa. Bloquea la eliminación de roles globales 
    y de roles pertenecientes a otras estaciones.
    """

    # --- 1. Atributos de Configuración ---
    template_name = 'gestion_usuarios/pages/eliminar_rol.html'
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_gestionar_roles'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_roles')

    # --- 2. Método de Obtención (SEGURIDAD) ---
    def get_object(self):
        """
        Obtiene el rol a eliminar.
        Filtra estrictamente por el ID de la estación activa.
        """
        rol_id = self.kwargs.get('id')
        
        # BaseEstacionMixin nos da 'self.estacion_activa_id'
        # Al filtrar por estacion_id, garantizamos que solo se toque
        # lo que pertenece a esta estación.
        return get_object_or_404(
            Rol, 
            id=rol_id, 
            estacion_id=self.estacion_activa_id
        )

    # --- 3. Manejador GET ---
    def get(self, request, *args, **kwargs):
        """Muestra la página de confirmación de eliminación."""
        self.object = self.get_object()
        return render(request, self.template_name, {'rol': self.object})

    # --- 4. Manejador POST ---
    def post(self, request, *args, **kwargs):
        """Ejecuta la eliminación del rol."""
        # Volvemos a obtener y validar el objeto antes de borrar
        self.object = self.get_object()
        rol_nombre = self.object.nombre

        try:
            self.object.delete()
            # --- AUDITORÍA ---
            # Pasamos 'objetivo=None' porque ya no existe en BD, 
            self.auditar(
                verbo="eliminó permanentemente el rol",
                objetivo=None, 
                objetivo_repr=rol_nombre,
                detalles={'nombre_rol_eliminado': rol_nombre}
            )
            messages.success(request, f"El rol '{rol_nombre.title()}' ha sido eliminado exitosamente.")

        except ProtectedError:
            messages.error(request, f"No se puede eliminar el rol '{rol_nombre}' porque está asignado a usuarios activos.")
        except Exception as e:
            messages.error(request, f"Error al eliminar el rol: {str(e)}")

        return redirect(self.success_url)




class UsuarioAsignarRolesView(BaseEstacionMixin, CustomPermissionRequiredMixin, MembresiaGestionableMixin, AuditoriaMixin, View):
    """
    Vista para gestionar los ROLES de un usuario dentro de la estación activa.
    
    FUNCIONAMIENTO:
    1. Obtiene la Membresía del usuario (validada por Mixins).
    2. Muestra una lista de roles disponibles (Globales + De la Estación).
    3. Permite marcar/desmarcar roles y guardar los cambios.
    
    SEGURIDAD:
    - Solo permite ver usuarios de la propia estación (via get_object).
    - Solo permite asignar roles que pertenezcan a la estación o sean globales (via POST validation).
    """
    
    template_name = 'gestion_usuarios/pages/asignar_roles.html'
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_asignar_roles'
    
    # Mensaje específico si el mixin bloquea el acceso
    mensaje_no_gestiona = "No se pueden asignar roles porque la membresía del usuario no está vigente."


    # --- 1. Método de Obtención (El corazón de la seguridad) ---
    def get_object(self):
        """
        Obtiene la *última* membresía del usuario en la estación activa.
        El mixin 'MembresiaGestionableMixin' usará esto para validar 
        que sea ACTIVA o INACTIVA.
        """
        usuario_id = self.kwargs.get('id')
        try:
            return Membresia.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id # Del BaseEstacionMixin
            ).latest('created_at')
        except Membresia.DoesNotExist:
            raise Http404("El usuario no pertenece a esta estación.")


    def get_success_url(self):
        """Redirige al perfil del usuario."""
        return reverse('gestion_usuarios:ruta_ver_usuario', kwargs={'id': self.object.usuario.id})


    # --- 2. Helper de Roles Disponibles ---
    def get_roles_queryset(self):
        """
        Retorna el QuerySet de todos los roles que esta estación PUEDE usar.
        (Roles Globales + Roles creados en esta estación).
        """
        return Rol.objects.filter(
            Q(estacion__isnull=True) | Q(estacion=self.estacion_activa_id)
        ).order_by('nombre')


    # --- 3. Contexto ---
    def get_context_data(self, **kwargs):
        roles_disponibles = self.get_roles_queryset()
        
        context = {
            'membresia': self.object, # La membresía validada
            'usuario': self.object.usuario,
            'estacion': self.object.estacion,
            
            # Agrupación para la vista
            'roles_universales': roles_disponibles.filter(estacion__isnull=True),
            'roles_de_estacion': roles_disponibles.filter(estacion__isnull=False),
            
            # IDs actuales para marcar los checkboxes
            'usuario_roles_ids': set(self.object.roles.values_list('id', flat=True))
        }
        return context


    # --- 4. Manejador GET ---
    def get(self, request, *args, **kwargs):
        # El mixin ya llamó a get_object, validó el estado y guardó en self.object
        context = self.get_context_data()
        return render(request, self.template_name, context)


    # --- 5. Manejador POST (Validación de Seguridad) ---
    def post(self, request, *args, **kwargs):
        # El mixin valida nuevamente la membresía
        self.object = self.get_object() 
        
        # --- VALIDACIÓN DE ROLES (CRÍTICO) ---
        # El usuario envía una lista de IDs. Debemos asegurarnos de que NO 
        # esté intentando inyectar un ID de un rol que no le pertenece (de otra estación).
        
        # 1. IDs enviados por el usuario
        selected_roles_ids = request.POST.getlist('roles')
        
        # 2. IDs válidos (Trusted Source)
        # Usamos values_list para obtener solo los IDs de la query segura
        valid_roles_ids = set(self.get_roles_queryset().values_list('id', flat=True))
        
        # 3. Filtrado Seguro
        # Convertimos a int y filtramos. Solo pasan los que existen en valid_roles_ids.
        roles_para_guardar = []
        for role_id in selected_roles_ids:
            try:
                rid = int(role_id)
                if rid in valid_roles_ids:
                    roles_para_guardar.append(rid)
                else:
                    # Opcional: Loguear intento de hacking
                    print(f"SECURITY WARNING: Intento de asignar rol inválido {rid}")
            except (ValueError, TypeError):
                continue

        try:
            # --- GUARDADO ---
            # .set() reemplaza los roles anteriores con la nueva lista limpia
            self.object.roles.set(roles_para_guardar)
            # --- AUDITORÍA ---
            # Registramos sobre el usuario, no sobre la membresía (más legible)
            self.auditar(
                verbo="actualizó la asignación de roles de",
                objetivo=self.object.usuario, 
                objetivo_repr=self.object.usuario.get_full_name,
                detalles={'cantidad_roles': len(roles_para_guardar)}
            )
            messages.success(request, f"Roles de '{self.object.usuario.get_full_name.title()}' actualizados correctamente.")

        except Exception as e:
            messages.error(request, f"Error al asignar roles: {str(e)}")

        return redirect(self.get_success_url())




class UsuarioRestablecerContrasena(BaseEstacionMixin, CustomPermissionRequiredMixin, MembresiaGestionableMixin, AuditoriaMixin, View):
    """
    Vista para que un administrador inicie el proceso de restablecimiento
    de contraseña para otro usuario de su estación.
    
    SEGURIDAD:
    - Solo funciona vía POST.
    - Verifica que el usuario tenga una membresía ACTIVA/INACTIVA en la estación.
    """
    
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_restablecer_pass'
    
    # --- 1. Configuración ---
    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    # --- 2. Método de Obtención (Requerido por el Mixin) ---
    def get_object(self):
        """
        Obtiene la última membresía válida del usuario en la estación.
        El mixin validará si su estado permite la gestión.
        """
        usuario_id = self.kwargs.get('id')
        try:
            return Membresia.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id
            ).latest('created_at')
        except Membresia.DoesNotExist:
            raise Http404("El usuario no pertenece a esta estación.")

    # --- 3. Manejador POST ---
    def post(self, request, *args, **kwargs):
        # El mixin ya validó la membresía y la guardó en self.object
        membresia = self.object
        usuario_a_resetear = membresia.usuario

        # Validación: Email existente
        if not usuario_a_resetear.email:
            messages.error(request, f"El usuario {usuario_a_resetear.get_full_name} no tiene un correo electrónico registrado.")
            return redirect(reverse('gestion_usuarios:ruta_ver_usuario', kwargs={'id': usuario_a_resetear.id}))

        # Instanciamos el formulario estándar de Django
        form = PasswordResetForm({'email': usuario_a_resetear.email})

        if form.is_valid():
            # Enviamos el correo
            # NOTA: domain_override usualmente espera un dominio (ej: 'bomberil.cl').
            # 'acceso' funciona porque hay una config muy específica,
            try:
                form.save(
                    request=request,
                    from_email=DEFAULT_FROM_EMAIL,
                    email_template_name='acceso/emails/password_reset_email.txt',
                    html_email_template_name='acceso/emails/password_reset_email.html',
                    subject_template_name='acceso/emails/password_reset_subject.txt',
                    # extra_email_context={'nombre_usuario': usuario_a_resetear.first_name}, # Útil si quieres personalizar el email
                )
                # --- AUDITORÍA ---
                self.auditar(
                    verbo="solicitó el restablecimiento de contraseña para",
                    objetivo=usuario_a_resetear,
                    objetivo_repr=usuario_a_resetear.get_full_name,
                    detalles={'metodo': 'email'}
                )
                messages.success(request, f"Se ha enviado un correo para restablecer la contraseña a {usuario_a_resetear.email}.")
            
            except Exception as e:
                messages.error(request, f"Error al enviar el correo: {str(e)}")

        messages.error(request, "Error interno al procesar el correo del usuario.")
        return redirect(reverse('gestion_usuarios:ruta_ver_usuario', kwargs={'id': usuario_a_resetear.id}))




class UsuarioVerPermisos(BaseEstacionMixin, CustomPermissionRequiredMixin, MembresiaGestionableMixin, View):
    """
    Muestra una lista consolidada de solo lectura de todos los permisos 
    que un usuario posee en la estación activa (suma de sus roles).
    """
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_ver_permisos'
    template_name = 'gestion_usuarios/pages/ver_permisos_usuario.html'

    # --- 1. Método de Obtención ---
    def get_object(self):
        """
        Obtiene la membresía válida (Activa/Inactiva) del usuario.
        El mixin se encargará de validarla.
        """
        usuario_id = self.kwargs.get('id')
        try:
            return Membresia.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id
            ).latest('created_at')
        except Membresia.DoesNotExist:
            raise Http404("El usuario no pertenece a esta estación.")


    # --- 2. Lógica de Agrupación ---
    def _agrupar_permisos(self, queryset_permisos):
        """
        Agrupa los permisos por el nombre verbose de su aplicación.
        """
        agrupados = defaultdict(list)
        all_apps = apps.get_app_configs()
        
        for perm in queryset_permisos:
            nombre_modulo = "Permisos Generales"

            for app in all_apps:
                # Convención: 'acceso_APPLABEL' o 'accion_APPLABEL_...'
                prefix_acceso = f"acceso_{app.label}"
                prefix_accion = f"accion_{app.label}_"
                
                if perm.codename == prefix_acceso or perm.codename.startswith(prefix_accion):
                    nombre_modulo = app.verbose_name
                    break
            
            agrupados[nombre_modulo].append(perm)
        
        # Ordenamos el diccionario por nombre de módulo
        return dict(sorted(agrupados.items()))


    # --- 3. Manejador GET ---
    def get(self, request, *args, **kwargs):
        # El mixin obtiene y valida la membresía en self.object
        membresia = self.object

        # 1. Obtener todos los roles de la membresía
        roles = membresia.roles.all()
        
        # 2. Recopilar IDs de permisos únicos de todos los roles
        permission_ids = set()
        for rol in roles:
            permission_ids.update(rol.permisos.values_list('id', flat=True))
        
        # 3. Traer los objetos Permission (QuerySet)
        permisos_del_usuario = Permission.objects.filter(
            id__in=permission_ids
        ).order_by('codename')
        
        # 4. Agruparlos correctamente
        permisos_agrupados = self._agrupar_permisos(permisos_del_usuario)
        
        context = {
            'membresia': membresia,
            'roles_asignados': roles, 
            'permisos_agrupados': permisos_agrupados,
            'total_permisos': len(permisos_del_usuario)
        }
        
        return render(request, self.template_name, context)




class UsuarioFinalizarMembresiaView(BaseEstacionMixin, CustomPermissionRequiredMixin, MembresiaGestionableMixin, AuditoriaMixin, View):
    """
    Muestra una página de confirmación y gestiona la finalización
    de la membresía de un usuario en la estación activa.
    
    SEGURIDAD:
    - MembresiaGestionableMixin asegura que solo entremos aquí si la 
      membresía está ACTIVA o INACTIVA. Si ya está FINALIZADA, bloquea el acceso.
    """
    
    # --- 1. Configuración ---
    template_name = 'gestion_usuarios/pages/finalizar_membresia.html'
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_finalizar_membresia'
    success_url = reverse_lazy('gestion_usuarios:ruta_lista_usuarios')
    
    # Opcional: Personalizar el mensaje si intentan entrar a una ya finalizada
    mensaje_no_gestiona = "Este usuario ya se encuentra desvinculado (Finalizado), no se puede volver a finalizar."

    # --- 2. Método de Obtención ---
    def get_object(self):
        """
        Obtiene la última membresía del usuario en la estación actual.
        El Mixin la validará (debe ser ACTIVA o INACTIVA).
        """
        usuario_id = self.kwargs.get('id')
        
        try:
            # Buscamos la última membresía (por si hubiera historial)
            return Membresia.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id # De BaseEstacionMixin
            ).latest('created_at')
            
        except Membresia.DoesNotExist:
            raise Http404("El usuario no pertenece a esta estación.")

    # --- 3. Manejador GET ---
    def get(self, request, *args, **kwargs):
        """Muestra la página de confirmación."""
        # self.object ya está cargado y validado por el mixin
        context = {
            'membresia': self.object
        }
        return render(request, self.template_name, context)

    # --- 4. Manejador POST ---
    def post(self, request, *args, **kwargs):
        """Ejecuta la finalización."""
        # El mixin asegura que self.object es la membresía vigente
        membresia = self.object
        usuario_nombre = membresia.usuario.get_full_name
        
        try:
            # Actualizamos el estado y la fecha de fin
            membresia.estado = Membresia.Estado.FINALIZADO
            membresia.fecha_fin = timezone.now().date()
            membresia.save()
            # --- AUDITORÍA (Mensaje Claro y Contundente) ---
            self.auditar(
                verbo="desvinculó permanentemente de la estación a",
                objetivo=membresia.usuario,
                objetivo_repr=membresia.usuario.get_full_name,
                detalles={'razon': 'Finalización administrativa de membresía'}
            )
            messages.success(request, f"La membresía de '{usuario_nombre}' ha sido finalizada correctamente.")
        
        except Exception as e:
            messages.error(request, f"Error al finalizar la membresía: {str(e)}")

        return redirect(self.success_url)




class HistorialMembresiasView(BaseEstacionMixin, CustomPermissionRequiredMixin, ListView):
    """
    Muestra un historial paginado de todas las membresías FINALIZADAS
    de la estación activa.
    
    OPTIMIZACIÓN: 
    - Se usa ListView para manejar la paginación automáticamente.
    - Se mantiene la seguridad y las consultas optimizadas (select_related).
    """
    
    # --- 1. Configuración ---
    model = Membresia
    template_name = 'gestion_usuarios/pages/historial_membresias.html'
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_ver_auditoria'
    paginate_by = 20
    
    # Nombre de la variable en el template (ListView usa 'page_obj' para paginación 
    # y 'object_list' para la lista, pero podemos definir uno principal)
    context_object_name = 'membresias' 

    # --- 2. Consulta (Filtros y Seguridad) ---
    def get_queryset(self):
        """
        Construye la consulta aplicando seguridad, optimización y filtros.
        """
        # A. Obtener parámetros GET directamente de self.request
        search_q = self.request.GET.get('q', '')
        fecha_desde = self.request.GET.get('fecha_desde', '')
        fecha_hasta = self.request.GET.get('fecha_hasta', '')

        # B. Queryset Base (Seguridad + Optimización)
        # BaseEstacionMixin nos da self.estacion_activa
        queryset = (
            self.model.objects
            .filter(
                estacion=self.estacion_activa, 
                estado=Membresia.Estado.FINALIZADO
            )
            .select_related('usuario')
            .prefetch_related('roles')
            .order_by('-fecha_fin')
        )

        # C. Filtros Dinámicos
        if search_q:
            queryset = queryset.filter(
                Q(usuario__first_name__icontains=search_q) |
                Q(usuario__last_name__icontains=search_q) |
                Q(usuario__email__icontains=search_q) |
                Q(usuario__rut__icontains=search_q)
            )

        if fecha_desde:
            queryset = queryset.filter(fecha_fin__gte=fecha_desde)
        
        if fecha_hasta:
            queryset = queryset.filter(fecha_fin__lte=fecha_hasta)
            
        return queryset.distinct()

    # --- 3. Contexto Adicional ---
    def get_context_data(self, **kwargs):
        """
        Añadimos los filtros actuales al contexto para mantener
        el estado de la barra de búsqueda en la plantilla.
        """
        # ListView ya añade 'page_obj', 'paginator', 'is_paginated' automáticamente.
        context = super().get_context_data(**kwargs)
        
        context['current_q'] = self.request.GET.get('q', '')
        context['current_fecha_desde'] = self.request.GET.get('fecha_desde', '')
        context['current_fecha_hasta'] = self.request.GET.get('fecha_hasta', '')
        
        return context




class RegistroActividadView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
    """
    Muestra el "Feed de Actividad" (legible por humanos)
    para la estación activa del usuario.
    """
    template_name = 'gestion_usuarios/pages/registro_actividad.html'
    # Asegúrate de que este permiso exista en models.py
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_ver_auditoria'
    paginate_by = 30 # Puedes ajustar este número

    def get_queryset(self):
        """
        Obtiene el queryset base (solo registros de la estación activa)
        y aplica los filtros de la URL.
        """
        
        # 1. Queryset Base:
        #    Filtra solo los registros de la estación activa.
        #    (self.estacion_activa viene de BaseEstacionMixin)
        queryset = RegistroActividad.objects.filter(
            estacion_id=self.estacion_activa
        ).select_related('actor').order_by('-fecha') # (actor es el "usuario" que hizo la acción)

        # 2. Aplicar filtro de Búsqueda por Usuario (Actor)
        if hasattr(self, 'search_user') and self.search_user:
            queryset = queryset.filter(
                Q(actor__first_name__icontains=self.search_user) |
                Q(actor__last_name__icontains=self.search_user)
            )

        # 3. Aplicar filtros de Rango de Fechas
        if hasattr(self, 'fecha_desde') and self.fecha_desde:
            try:
                # Filtra desde el inicio del día
                fecha_desde_dt = datetime.strptime(self.fecha_desde, '%Y-%m-%d')
                queryset = queryset.filter(fecha__gte=fecha_desde_dt)
            except (ValueError, TypeError):
                pass # Ignora fecha inválida

        if hasattr(self, 'fecha_hasta') and self.fecha_hasta:
            try:
                # Filtra hasta el *final* de ese día
                fecha_hasta_dt = datetime.strptime(self.fecha_hasta, '%Y-%m-%d')
                # Añadimos 1 día y filtramos por "menor que" (lt)
                # para incluir todo el día de 'fecha_hasta'.
                fecha_hasta_plus_one = fecha_hasta_dt + timedelta(days=1)
                queryset = queryset.filter(fecha__lt=fecha_hasta_plus_one)
            except (ValueError, TypeError):
                pass # Ignora fecha inválida
            
        return queryset

    def get_context_data(self):
        """
        Prepara el contexto para la plantilla, incluyendo la paginación
        y los valores de los filtros.
        """
        logs_filtrados = self.get_queryset()

        paginator = Paginator(logs_filtrados, self.paginate_by)
        page_number = self.request.GET.get('page')

        try:
            page_obj = paginator.get_page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.get_page(1)
        except EmptyPage:
            page_obj = paginator.get_page(paginator.num_pages)

        context = {
            'page_obj': page_obj,
            # Devolvemos los valores de los filtros a la plantilla
            'current_q_user': getattr(self, 'search_user', ''),
            'current_fecha_desde': getattr(self, 'fecha_desde', ''),
            'current_fecha_hasta': getattr(self, 'fecha_hasta', ''),
        }
        return context

    def get(self, request, *args, **kwargs):
        """
        Maneja la solicitud GET.
        Captura los filtros de la URL antes de llamar a get_context_data.
        """
        self.search_user = request.GET.get('q_user', '')
        self.fecha_desde = request.GET.get('fecha_desde', '')
        self.fecha_hasta = request.GET.get('fecha_hasta', '')
        
        context = self.get_context_data()
        return render(request, self.template_name, context)




class UsuarioForzarCierreSesionView(BaseEstacionMixin, CustomPermissionRequiredMixin, MembresiaGestionableMixin, AuditoriaMixin, View):
    """
    Elimina todas las sesiones activas de un usuario específico
    usando 'django-user-sessions' para un rendimiento óptimo (O(1)).
    """
    permission_required = 'gestion_usuarios.accion_gestion_usuarios_forzar_logout'
    
    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(['POST'])

    def get_object(self):
        """Obtiene la membresía válida (validada por el Mixin)."""
        usuario_id = self.kwargs.get('id')
        try:
            return Membresia.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id
            ).latest('created_at')
        except Membresia.DoesNotExist:
            raise Http404("El usuario no pertenece a esta estación.")

    def post(self, request, *args, **kwargs):
        # 1. Validación de seguridad (Mixin)
        membresia = self.object 
        usuario_objetivo = membresia.usuario
        
        try:
            # Ya no hay bucles for. La base de datos hace el trabajo duro.
            # .delete() retorna una tupla: (total_eliminados, diccionario_tipos)
            deleted_count, _ = Session.objects.filter(user=usuario_objetivo).delete()

            # --- AUDITORÍA Y MENSAJES ---
            if deleted_count > 0:
                self.auditar(
                    verbo=f"forzó el cierre remoto de {deleted_count} sesión(es) de",
                    objetivo=usuario_objetivo,
                    objetivo_repr=usuario_objetivo.get_full_name,
                    detalles={'sesiones_cerradas': deleted_count}
                )
                messages.success(request, f"Se han cerrado exitosamente {deleted_count} sesiones activas de {usuario_objetivo.get_full_name}.")
            else:
                messages.info(request, f"El usuario {usuario_objetivo.get_full_name} no tenía sesiones activas.")
        
        except Exception as e:
            messages.error(request, f"Error al cerrar sesiones: {str(e)}")

        return redirect(reverse('gestion_usuarios:ruta_ver_usuario', kwargs={'id': usuario_objetivo.id}))




class UsuarioImpersonarView(BaseEstacionMixin, UserPassesTestMixin, MembresiaGestionableMixin, AuditoriaMixin, View):
    """
    Inicia la suplantación de identidad.
    
    OPTIMIZACIÓN:
    - Usa MembresiaGestionableMixin para asegurar que el objetivo 
      pertenece a la estación activa y su membresía es válida.
    """
    
    # --- 1. Configuración ---
    
    # Mensaje si el objetivo no es válido (no es miembro o está finalizado)
    mensaje_no_gestiona = "No puedes impersonar a este usuario porque no pertenece activamente a esta estación."
    
    def test_func(self):
        """Solo superusuarios pueden impersonar."""
        return self.request.user.is_superuser

    # --- 2. Obtención del Objetivo (Para el Mixin) ---
    def get_object(self):
        """
        El mixin llama a esto para validar la membresía.
        Buscamos la última membresía del usuario en la estación actual.
        """
        usuario_id = self.kwargs.get('id')
        
        # Validación extra: Auto-impersonación
        if str(usuario_id) == str(self.request.user.id):
            # Lanzamos 404 o manejamos aquí. El mixin capturará errores.
            raise Http404("Auto-impersonación no permitida.")

        try:
            return Membresia.objects.filter(
                usuario_id=usuario_id,
                estacion_id=self.estacion_activa_id
            ).latest('created_at')
        except Membresia.DoesNotExist:
            raise Http404("El usuario no pertenece a esta estación.")

    # --- 3. Manejador POST ---
    def post(self, request, id):
        # El mixin ya validó la membresía y la guardó en self.object
        membresia_objetivo = self.object
        usuario_objetivo = membresia_objetivo.usuario
        usuario_original = request.user
        
        try:
            # --- AUDITORÍA DE SEGURIDAD ---
            # Registramos que el admin (request.user actual) va a entrar como otro.
            self.auditar(
                verbo="asumió la identidad digital (Impersonación) de",
                objetivo=usuario_objetivo,
                objetivo_repr=usuario_objetivo.get_full_name,
                detalles={'advertencia': 'Inicio de sesión simulada con permisos de superusuario'}
            )

            # --- IMPERSONACIÓN ---
            # 1. Guardamos datos clave antes de destruir la sesión
            estacion_id = self.estacion_activa_id
            estacion_nombre = self.estacion_activa.nombre
            impersonator_id = str(usuario_original.id)

            # 2. Login del objetivo (Destruye sesión anterior)
            usuario_objetivo.backend = 'apps.gestion_usuarios.backends.RolBackend'
            login(request, usuario_objetivo)

            # 3. Reconstruir contexto en la NUEVA sesión
            request.session['active_estacion_id'] = estacion_id
            request.session['active_estacion_nombre'] = estacion_nombre

            # 4. La marca de impersonación
            request.session['impersonator_id'] = impersonator_id
            request.session['is_impersonating'] = True

            messages.info(request, f"Estás navegando como {usuario_objetivo.get_full_name} en {estacion_nombre}.")
            return redirect('portal:ruta_inicio')
        
        except Exception as e:
            messages.error(request, f"Error crítico al intentar impersonar: {str(e)}")
            return redirect('gestion_usuarios:ruta_ver_usuario', id=id)




class UsuarioDetenerImpersonacionView(LoginRequiredMixin, AuditoriaMixin, View):
    """
    Restaura la sesión del administrador original.
    """
    def get(self, request):
        # 1. Obtener ID del impersonador
        impersonator_id = request.session.get('impersonator_id')

        # 2. Capturar al usuario que estaba siendo suplantado (ANTES de perder la sesión)
        #    En este punto, request.user sigue siendo el "Usuario Objetivo"
        usuario_impersonado = request.user 
        
        if not impersonator_id:
            return redirect('portal:ruta_inicio')

        # Guardamos el contexto de salida para intentar volver ahí
        estacion_id_salida = request.session.get('active_estacion_id')
        estacion_nombre_salida = request.session.get('active_estacion_nombre')

        try:
            # 3. Recuperar al admin original
            admin_original = Usuario.objects.get(id=impersonator_id)

            # 4. Validación de Seguridad: ¿Sigue siendo superusuario?
            if not admin_original.is_superuser:
                raise PermissionDenied("El usuario original perdió sus privilegios.")
            
            # 5. Restaurar sesión (Login destruye la sesión impersonada)
            admin_original.backend = 'apps.gestion_usuarios.backends.RolBackend'
            login(request, admin_original)
            
            # 6. Restaurar contexto de estación (si existía)
            if estacion_id_salida:
                request.session['active_estacion_id'] = estacion_id_salida
                request.session['active_estacion_nombre'] = estacion_nombre_salida

            # 7. --- AUDITORÍA DE CIERRE ---
            #    Se ejecuta YA como el Admin Original.
            self.auditar(
                verbo="finalizó la sesión simulada y retomó su identidad original",
                objetivo=usuario_impersonado, # Guardamos referencia de quién era
                objetivo_repr=usuario_impersonado.get_full_name,
                detalles={'sesion_duracion': 'N/A'} # Se puede calcular duración si se guarda el timestamp de inicio
            )
            
            messages.success(request, "Has vuelto a tu identidad original.")
            
        except Usuario.DoesNotExist:
            # Caso borde crítico
            messages.error(request, "Error crítico: La cuenta original no existe.")
            return redirect('acceso:ruta_login')
        
        return redirect('portal:ruta_inicio')