from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView, TemplateView
from django.db.models import Count, Q, ProtectedError
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail

from .mixins import SuperuserRequiredMixin, PermisosMatrixMixin
from .forms import EstacionForm, ProductoGlobalForm, UsuarioCreationForm, UsuarioChangeForm, AsignarMembresiaForm, RolGlobalForm, MarcaForm, CategoriaForm
from apps.gestion_inventario.models import Estacion, Ubicacion, Vehiculo, Prestamo, Compartimento, Categoria, Marca, ProductoGlobal, Producto, Activo, LoteInsumo, MovimientoInventario
from apps.gestion_usuarios.models import Membresia, Rol
from core.settings import DEFAULT_FROM_EMAIL


class AdministracionInicioView(SuperuserRequiredMixin, TemplateView):
    template_name = 'core_admin/pages/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Panel de Control General"
        
        User = get_user_model()

        # --- 1. KPIs SUPERIORES (Signos Vitales) ---
        # Usuarios
        context['kpi_usuarios_total'] = User.objects.count()
        context['kpi_usuarios_activos'] = User.objects.filter(is_active=True).count()
        
        # Estaciones
        context['kpi_estaciones_total'] = Estacion.objects.count()
        context['kpi_estaciones_cias'] = Estacion.objects.filter(es_departamento=False).count()
        
        # Catálogo Global
        context['kpi_productos_globales'] = ProductoGlobal.objects.count()
        
        # Roles Globales
        context['kpi_roles_globales'] = Rol.objects.filter(estacion__isnull=True).count()

        # --- 2. AUDITORÍA DE CALIDAD (Alertas) ---
        # Productos incompletos (Sin imagen o sin marca)
        context['audit_productos_incompletos'] = ProductoGlobal.objects.filter(
            Q(imagen='') | Q(marca__isnull=True)
        ).count()

        # Estaciones Fantasma (Sin miembros asignados)
        # Usamos annotate para contar miembros y filtramos los que tienen 0
        context['audit_estaciones_vacias'] = Estacion.objects.annotate(
            num_miembros=Count('miembros')
        ).filter(num_miembros=0).count()

        # Taxonomías Huérfanas (Sin uso)
        # Marcas sin productos NI vehículos
        marcas_huerfanas = Marca.objects.annotate(
            uso_prod=Count('productoglobal'),
            uso_veh=Count('vehiculo')
        ).filter(uso_prod=0, uso_veh=0).count()
        
        # Categorías sin productos
        cats_huerfanas = Categoria.objects.annotate(
            uso_prod=Count('productoglobal')
        ).filter(uso_prod=0).count()

        context['audit_taxonomias_huerfanas'] = marcas_huerfanas + cats_huerfanas

        # --- 3. ESTADÍSTICAS DE USO (Top 5) ---
        context['top_categorias'] = Categoria.objects.annotate(
            total=Count('productoglobal')
        ).order_by('-total')[:5]

        context['top_marcas'] = Marca.objects.annotate(
            total=Count('productoglobal')
        ).order_by('-total')[:5]

        return context
    



class EstacionListaView(SuperuserRequiredMixin, ListView):
    model = Estacion
    template_name = 'core_admin/pages/lista_estaciones.html'
    context_object_name = 'estaciones'
    paginate_by = 10  # Paginación para no saturar la vista si crecen las compañías
    
    def get_queryset(self):
        """
        Retorna las estaciones optimizando la consulta a la DB.
        Ordenamos por nombre por defecto.
        """
        queryset = Estacion.objects.select_related('comuna', 'comuna__region').all().order_by('nombre')
        
        # Opcional: Si quieres añadir un buscador simple por nombre
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(nombre__icontains=q)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Administración de Estaciones"
        context['segmento'] = "estaciones" # Para resaltar el menú lateral si usas uno
        return context




class EstacionDetalleView(SuperuserRequiredMixin, DetailView):
    model = Estacion
    template_name = 'core_admin/pages/ver_estacion.html'
    context_object_name = 'estacion'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        estacion = self.object

        # --- 1. KPIs DE INVENTARIO ---
        # Catálogo
        context['kpi_total_productos'] = Producto.objects.filter(estacion=estacion).count()
        # Activos (Equipos serializados)
        context['kpi_total_activos'] = Activo.objects.filter(estacion=estacion).count()
        # Insumos (Lotes fungibles) - NUEVO
        context['kpi_total_insumos'] = LoteInsumo.objects.filter(
            compartimento__ubicacion__estacion=estacion
        ).count()

        # --- 2. KPIs OPERATIVOS ---
        # Vehículos
        vehiculos_qs = Vehiculo.objects.filter(ubicacion__estacion=estacion).select_related('ubicacion', 'tipo_vehiculo', 'marca')
        context['vehiculos'] = vehiculos_qs # Para el listado
        context['kpi_total_vehiculos'] = vehiculos_qs.count() # Para el KPI
        
        # Compartimentos (Total de gavetas/espacios de almacenaje) - NUEVO
        context['kpi_total_compartimentos'] = Compartimento.objects.filter(
            ubicacion__estacion=estacion
        ).count()
        
        # Personal (Membresías activas) - NUEVO
        # Asumimos que Membresia tiene un campo 'activo' o 'is_active'
        context['kpi_total_usuarios'] = Membresia.objects.filter(
            estacion=estacion
            # Si tu modelo Membresia tiene un campo booleano de activo, úsalo aquí:
            # , is_active=True 
        ).count()

        # Préstamos Pendientes
        context['kpi_prestamos_pendientes'] = Prestamo.objects.filter(
            estacion=estacion, 
            estado='PEN'
        ).count()

        # --- 3. INFO ROBUSTA ADICIONAL ---
        # Últimos 5 movimientos de inventario en esta estación
        context['ultimos_movimientos'] = MovimientoInventario.objects.filter(
            estacion=estacion
        ).select_related('usuario', 'activo', 'lote_insumo').order_by('-fecha_hora')[:5]

        # Ubicaciones físicas (Infraestructura)
        context['ubicaciones_fisicas'] = Ubicacion.objects.filter(
            estacion=estacion
        ).exclude(
            tipo_ubicacion__nombre='Vehículo'
        ).select_related('tipo_ubicacion').annotate(
            total_compartimentos=Count('compartimento')
        ).order_by('nombre')

        context['menu_activo'] = 'estaciones'
        return context



class EstacionEditarView(SuperuserRequiredMixin, UpdateView):
    model = Estacion
    form_class = EstacionForm
    template_name = 'core_admin/pages/estacion_form.html'
    context_object_name = 'estacion'
    
    def get_success_url(self):
        # Redirigir al detalle de la estación editada
        return reverse_lazy('core_admin:ruta_ver_estacion', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Título dinámico para reutilizar template si decides hacer el CreateView después
        context['titulo_pagina'] = f"Editar: {self.object.nombre}"
        context['accion'] = "Guardar Cambios"
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Estación '{form.instance.nombre}' guardada correctamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Error en el formulario. Por favor revisa los campos marcados en rojo.")
        return super().form_invalid(form)
    



class EstacionCrearView(SuperuserRequiredMixin, CreateView):
    model = Estacion
    form_class = EstacionForm
    template_name = 'core_admin/pages/estacion_form.html'
    
    def get_success_url(self):
        # Al crear, redirigimos al detalle de la nueva estación para confirmar los datos
        return reverse_lazy('core_admin:ruta_ver_estacion', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Registrar Nueva Estación"
        context['accion'] = "Crear Estación" # Texto del botón de submit
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Estación '{form.instance.nombre}' guardada correctamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Error en el formulario. Por favor revisa los campos marcados en rojo.")
        return super().form_invalid(form)




class EstacionEliminarView(SuperuserRequiredMixin, DeleteView):
    model = Estacion
    template_name = 'core_admin/pages/confirmar_eliminar_estacion.html'
    context_object_name = 'estacion'
    success_url = reverse_lazy('core_admin:ruta_lista_estaciones')

    def post(self, request, *args, **kwargs):
        """
        Sobrescribimos el POST para capturar el error de protección (ProtectedError).
        Si la estación tiene datos hijos (ubicaciones, productos, etc.), Django
        lanzará este error debido a on_delete=models.PROTECT.
        """
        self.object = self.get_object()
        success_url = self.get_success_url()

        try:
            self.object.delete()
            messages.success(request, f"La estación '{self.object.nombre}' ha sido eliminada correctamente.")
            return HttpResponseRedirect(success_url)
        
        except ProtectedError:
            # Error: Hay datos vinculados
            messages.error(request, 
                "No se puede eliminar esta estación porque tiene registros asociados "
                "(Ubicaciones, Inventario, Usuarios, etc.). Debe eliminar esos registros primero."
            )
            # Redirigimos al detalle para que el usuario vea qué tiene la estación
            return redirect('core_admin:ruta_ver_estacion', pk=self.object.pk)
        
        except Exception as e:
            messages.error(request, f"Error del sistema al intentar eliminar la estación: {e}")
            return redirect('core_admin:ruta_ver_estacion', pk=self.object.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Eliminar Estación"
        return context




class EstacionSwitchView(SuperuserRequiredMixin, View):
    """
    Vista lógica para 'entrar' a una estación.
    Establece la estación seleccionada como activa en la sesión y redirige al portal.
    """
    def get(self, request, pk):
        estacion = get_object_or_404(Estacion, pk=pk)
        
        # 1. Configurar la variable de sesión crítica 
        request.session['active_estacion_id'] = estacion.id
        request.session['active_estacion_nombre'] = estacion.nombre

        try:
            # Obtener el logo de la estación
            if estacion.logo_thumb_small:
                request.session['active_estacion_logo'] = estacion.logo_thumb_small.url
            elif estacion.logo:
                request.session['active_estacion_logo'] = estacion.logo.url
            else:
                request.session['active_estacion_logo'] = None

        except Exception:
            request.session['active_estacion_logo'] = None
        
        # 2. Feedback al usuario
        messages.success(request, f"Has ingresado a la gestión de: {estacion.nombre}")
        
        # 3. Redirigir al Dashboard operativo (Portal) [cite: 9]
        # Asumiendo que el namespace de tu portal es 'portal' y la url 'ruta_inicio'
        return redirect('portal:ruta_inicio')




class ProductoGlobalListView(SuperuserRequiredMixin, ListView):
    model = ProductoGlobal
    template_name = 'core_admin/pages/lista_catalogo_global.html'
    context_object_name = 'productos'
    paginate_by = 20 # Un poco más denso para administración

    def get_queryset(self):
        # Optimización: Traemos marca y categoría para no hacer N+1 queries.
        # Annotate: Contamos cuántas veces se usa este producto en 'Producto' (catalogo local)
        qs = ProductoGlobal.objects.select_related('marca', 'categoria').annotate(
            total_usos=Count('variantes_locales')
        ).order_by('-created_at')

        # --- FILTROS ---
        q = self.request.GET.get('q')
        categoria_id = self.request.GET.get('categoria')
        marca_id = self.request.GET.get('marca')

        if q:
            qs = qs.filter(
                Q(nombre_oficial__icontains=q) | 
                Q(modelo__icontains=q) |
                Q(gtin__icontains=q)
            )
        
        if categoria_id:
            qs = qs.filter(categoria_id=categoria_id)
        
        if marca_id:
            qs = qs.filter(marca_id=marca_id)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Catálogo Maestro Global"
        
        # Listas para los selectores del filtro
        context['all_categorias'] = Categoria.objects.all().order_by('nombre')
        context['all_marcas'] = Marca.objects.all().order_by('nombre')
        
        # Mantener el estado de los filtros en la paginación
        context['current_search'] = self.request.GET.get('q', '')
        context['current_categoria'] = self.request.GET.get('categoria', '')
        context['current_marca'] = self.request.GET.get('marca', '')

        # --- KPIs DE AUDITORÍA ---
        # Total absoluto
        context['kpi_total'] = ProductoGlobal.objects.count()
        # Productos sin imagen (Para saber qué falta completar)
        context['kpi_sin_imagen'] = ProductoGlobal.objects.filter(imagen='').count()
        # Productos "Huérfanos" (Nadie los usa aún)
        context['kpi_sin_uso'] = ProductoGlobal.objects.annotate(
            cnt=Count('variantes_locales')
        ).filter(cnt=0).count()

        return context




class ProductoGlobalCreateView(SuperuserRequiredMixin, CreateView):
    model = ProductoGlobal
    form_class = ProductoGlobalForm
    template_name = 'core_admin/pages/producto_global_form.html'
    success_url = reverse_lazy('core_admin:ruta_catalogo_global')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Alta de Producto Global"
        context['accion'] = "Crear Producto"
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Producto global '{form.instance.nombre_oficial}' guardado correctamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Error en el formulario. Por favor revisa los campos marcados en rojo.")
        return super().form_invalid(form)




class ProductoGlobalUpdateView(SuperuserRequiredMixin, UpdateView):
    model = ProductoGlobal
    form_class = ProductoGlobalForm
    template_name = 'core_admin/pages/producto_global_form.html' # Reutilizamos template
    success_url = reverse_lazy('core_admin:ruta_catalogo_global')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar: {self.object.nombre_oficial}"
        context['accion'] = "Guardar Cambios"
        
        # Mensaje de advertencia para el admin
        # Es útil recordarle que este cambio impacta a todas las estaciones
        context['mensaje_alerta'] = (
            "Atención: Al editar este producto maestro, los cambios (nombre, marca, modelo) "
            "se reflejarán en todas las estaciones que lo tengan en su inventario."
        )
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Producto global '{form.instance.nombre_oficial}' guardado correctamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Error en el formulario. Por favor revisa los campos marcados en rojo.")
        return super().form_invalid(form)




class ProductoGlobalDeleteView(SuperuserRequiredMixin, DeleteView):
    model = ProductoGlobal
    template_name = 'core_admin/pages/confirmar_eliminar_producto_global.html'
    success_url = reverse_lazy('core_admin:ruta_catalogo_global')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()

        try:
            self.object.delete()
            messages.success(request, f"El producto '{self.object.nombre_oficial}' ha sido eliminado del catálogo maestro.")
            return HttpResponseRedirect(success_url)
        
        except ProtectedError:
            # Capturamos el intento de borrar algo que está en uso
            messages.error(
                request, 
                f"Bloqueado: El producto '{self.object.nombre_oficial}' no se puede eliminar porque "
                "ya fue importado por una o más estaciones. Debe retirarse de los inventarios locales primero."
            )
            # Redirigimos a la lista para que vea el estado
            return redirect('core_admin:producto_global_list')
        
        except Exception as e:
            messages.error(request, f"Error inesperado al eliminar el producto: {e}")
            return redirect('core_admin:producto_global_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Eliminar Producto Maestro"
        return context




class UsuarioListView(SuperuserRequiredMixin, ListView):
    model = get_user_model()
    template_name = 'core_admin/pages/lista_usuarios.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        User = get_user_model()
        # Optimización: Traemos las membresías y las estaciones relacionadas
        # para evitar consultas N+1 en el template.
        queryset = User.objects.prefetch_related(
            'membresias',
            'membresias__estacion'
        ).order_by('-created_at')

        # --- FILTROS ---
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q) | 
                Q(email__icontains=q) |
                Q(first_name__icontains=q) | 
                Q(last_name__icontains=q)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Gestión de Usuarios del Sistema"
        context['current_search'] = self.request.GET.get('q', '')
        
        # KPI Rápido
        User = get_user_model()
        context['kpi_total_usuarios'] = User.objects.count()
        context['kpi_activos'] = User.objects.filter(is_active=True).count()
        context['kpi_staff'] = User.objects.filter(is_staff=True).count()
        
        return context




class UsuarioCreateView(SuperuserRequiredMixin, CreateView):
    model = get_user_model()
    form_class = UsuarioCreationForm
    template_name = 'core_admin/pages/usuario_form.html'
    success_url = reverse_lazy('core_admin:ruta_lista_usuarios')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Registrar Nuevo Usuario"
        context['accion'] = "Crear Usuario"
        context['subtitulo'] = "Complete los datos de identidad y credenciales de acceso."
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.get_full_name or form.instance.username}' guardado exitosamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Error en el formulario. Por favor revisa los campos marcados en rojo.")
        return super().form_invalid(form)




class UsuarioUpdateView(SuperuserRequiredMixin, UpdateView):
    model = get_user_model()
    form_class = UsuarioChangeForm
    template_name = 'core_admin/pages/usuario_form.html' # Reutilizamos el template
    success_url = reverse_lazy('core_admin:ruta_lista_usuarios')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Usuario: {self.object.get_full_name}"
        context['accion'] = "Guardar Cambios"
        context['subtitulo'] = "Modifique los datos personales y niveles de acceso."
        
        # Bandera para ocultar sección de password en el template
        context['is_edit_mode'] = True 
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.get_full_name or form.instance.username}' guardado exitosamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Error en el formulario. Por favor revisa los campos marcados en rojo.")
        return super().form_invalid(form)




class UsuarioResetPasswordView(SuperuserRequiredMixin, View):
    """
    Vista para que el Superusuario fuerce el envío de un correo de 
    recuperación de contraseña. Reutiliza los templates del sistema.
    ESTRATEGIA MANUAL: Generación de tokens y send_mail directo.
    """
    
    def post(self, request, pk):
        # 1. Buscamos al usuario globalmente (sin restricción de estación)
        User = get_user_model()
        usuario = get_object_or_404(User, pk=pk)

        # 2. Validación: Email existente
        if not usuario.email:
            messages.error(request, f"El usuario {usuario.get_full_name} no tiene un correo registrado. No se puede enviar el reset.")
            return redirect('core_admin:usuario_list')

        try:
            # --- ESTRATEGIA MANUAL ---
            
            # A. Generar Tokens
            uid = urlsafe_base64_encode(force_bytes(usuario.pk))
            token = default_token_generator.make_token(usuario)

            # B. Preparar Contexto
            context = {
                'email': usuario.email,
                'domain': request.get_host(),
                'site_name': 'Bomberil System',
                'uid': uid,
                'user': usuario,
                'token': token,
                'protocol': 'https' if request.is_secure() else 'http',
            }

            # C. Renderizar Templates (Usando los mismos que ya te funcionan)
            subject = render_to_string('acceso/emails/password_reset_subject.txt', context).strip()
            body = render_to_string('acceso/emails/password_reset_email.txt', context)
            html_email = render_to_string('acceso/emails/password_reset_email.html', context)

            # D. Enviar Correo (Fail Loudly)
            send_mail(
                subject=subject,
                message=body,
                from_email=DEFAULT_FROM_EMAIL, 
                recipient_list=[usuario.email],
                html_message=html_email,
                fail_silently=False
            )

            # E. Mensaje de Éxito
            messages.success(request, f"Correo de restablecimiento enviado a {usuario.email}.")

        except Exception as e:
            # F. Captura de errores reales
            print(f"ERROR CRÍTICO CORE_ADMIN: {e}")
            messages.error(request, f"Error al enviar correo: {str(e)}")

        # 3. Retorno
        return redirect('core_admin:ruta_lista_usuarios')




class ApiRolesPorEstacionView(SuperuserRequiredMixin, View):
    """
    Devuelve los roles disponibles para una estación específica:
    Roles Globales (estacion=None) + Roles Locales (estacion=ID)
    """
    def get(self, request):
        estacion_id = request.GET.get('estacion_id')
        
        # Consulta base: Roles Globales
        criterio = Q(estacion__isnull=True)
        
        # Si seleccionaron una estación, sumamos sus roles locales
        if estacion_id:
            if str(estacion_id).isdigit():
                criterio = criterio | Q(estacion_id=estacion_id)
            else:
                # Opcional: Loguear intento inválido
                pass
            
        roles = Rol.objects.filter(criterio).values('id', 'nombre', 'estacion__nombre').order_by('estacion', 'nombre')
        
        # Formateamos para el frontend
        data = []
        for rol in roles:
            tipo = f"Específico de {rol['estacion__nombre']}" if rol['estacion__nombre'] else "Global / Sistema"
            data.append({
                'id': rol['id'],
                'nombre': f"{rol['nombre']} ({tipo})"
            })
            
        return JsonResponse({'roles': data})




class MembresiaCreateView(SuperuserRequiredMixin, CreateView):
    model = Membresia
    form_class = AsignarMembresiaForm
    template_name = 'core_admin/pages/membresia_form.html'
    success_url = reverse_lazy('core_admin:ruta_lista_usuarios')


    def get_initial(self):
        """
        Pre-selecciona el usuario usando datos GET de la URL.
        Esto genera el HTML con el <option selected> ya marcado.
        """
        initial = super().get_initial()
        # Capturamos ?usuario_id=123 de la URL
        usuario_id = self.request.GET.get('usuario_id')
        if usuario_id:
            initial['usuario'] = usuario_id
        return initial


    def form_valid(self, form):
        try:
            with transaction.atomic():
                # 1. Guardamos la Membresía
                self.object = form.save(commit=False)
                self.object.estado = 'ACTIVO'
                self.object.save()

                # 2. Guardamos los Roles
                roles = form.cleaned_data['roles_seleccionados']
                self.object.roles.set(roles)
            messages.success(self.request, f"Membresía creada exitosamente para {self.object.usuario} en {self.object.estacion}.")
            return super().form_valid(form)
            
        except Exception as e:
            messages.error(self.request, f"Error crítico al crear la membresía: {e}")
            return self.form_invalid(form)
    

    def form_invalid(self, form):
        messages.error(self.request, "Error en el formulario. Por favor revisa los campos marcados en rojo.")
        return super().form_invalid(form)
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Asignar Acceso a Estación"
        # YA NO NECESITAMOS PASAR 'usuario_preseleccionado' al contexto
        return context




class UsuarioFinalizarMembresiasView(SuperuserRequiredMixin, View):
    """
    Cierra (finaliza) todas las membresías activas de un usuario específico.
    Útil para revocar acceso inmediato a todas las estaciones.
    """
    def post(self, request, pk):
        User = get_user_model()
        usuario = get_object_or_404(User, pk=pk)
        
        # 1. Buscar membresías activas
        membresias_activas = Membresia.objects.filter(
            usuario=usuario,
            estado='ACTIVO'
        )
        
        cantidad = membresias_activas.count()
        
        if cantidad > 0:
            # 2. Actualización masiva (Bulk Update)
            # Establecemos estado FINALIZADO y fecha de fin = Hoy
            try:
                membresias_activas.update(
                    estado='FINALIZADO',
                    fecha_fin=timezone.now().date()
                )
                messages.success(
                    request, 
                    f"Se han finalizado {cantidad} membresía(s) activa(s) para {usuario.get_full_name}."
                )
            except Exception as e:
                messages.error(request, f"Error del sistema al intentar finalizar las membresías: {e}")
                return redirect('core_admin:ruta_lista_usuarios', pk=self.object.pk)
            
        else:
            messages.warning(
                request, 
                f"El usuario {usuario.get_full_name} no tiene ninguna membresía activa para finalizar."
            )
            
        return redirect('core_admin:ruta_lista_usuarios')




class RolGlobalListView(SuperuserRequiredMixin, ListView):
    model = Rol
    template_name = 'core_admin/pages/lista_roles.html'
    context_object_name = 'roles'
    
    def get_queryset(self):
        filtro_negocio = Q(permisos__codename__startswith='accion_') | \
                         Q(permisos__codename__startswith='acceso_')
        
        filtro_activos = Q(asignaciones__estado='ACTIVO')

        return Rol.objects.filter(estacion__isnull=True).annotate(
            total_permisos=Count('permisos', filter=filtro_negocio, distinct=True),
            total_asignaciones=Count('asignaciones', filter=filtro_activos, distinct=True),
            total_historial=Count('asignaciones', distinct=True)
        ).order_by('nombre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Roles Maestros del Sistema"
        # KPIs simples
        context['kpi_total'] = self.object_list.count()
        # Rol más usado (el que tiene más asignaciones)
        mas_usado = self.object_list.order_by('-total_asignaciones').first()
        context['kpi_popular'] = mas_usado.nombre if mas_usado else "N/A"
        return context




class RolGlobalCreateView(SuperuserRequiredMixin, PermisosMatrixMixin, CreateView):
    model = Rol
    form_class = RolGlobalForm
    template_name = 'core_admin/pages/rol_form.html'
    success_url = reverse_lazy('core_admin:ruta_lista_roles')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Crear Nuevo Rol Global"
        context['accion'] = "Guardar Rol"
        
        # 1. Inyectar la matriz (Es vital para que el bucle del template funcione)
        context['permissions_matrix'] = self.get_permissions_matrix()
        
        # 2. IDs vacíos (importante para que el template no falle al verificar 'checked')
        context['rol_permissions_ids'] = []
        
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # 1. Guardar el objeto Rol (sin M2M aún)
                self.object = form.save(commit=False)
                self.object.estacion = None # Forzar Global
                self.object.save()

                # 2. GUARDADO EXPLÍCITO
                # Obtenemos los permisos limpios del formulario (ya filtrados por el queryset)
                permisos_seleccionados = form.cleaned_data['permisos']

                # Debug (Opcional: para ver en consola qué está llegando)
                print(f"DEBUG: Guardando {permisos_seleccionados.count()} permisos para el rol {self.object.nombre}")

                # .set() reemplaza TODO lo que había con la nueva lista.
                # Esto elimina automáticamente cualquier permiso basura (sys_, add_, etc.)
                self.object.permisos.set(permisos_seleccionados)
            messages.success(self.request, f"Rol global '{self.object.nombre}' creado con {permisos_seleccionados.count()} permisos.")
            return redirect(self.get_success_url())
        
        except Exception as e:
            messages.error(self.request, f"Error de integridad al guardar el Rol: {e}")
            return self.form_invalid(form)
    

    def form_invalid(self, form):
        messages.error(self.request, "No se pudo guardar el Rol. Revisa que el nombre sea único y los datos correctos.")
        return super().form_invalid(form)




class RolGlobalUpdateView(SuperuserRequiredMixin, PermisosMatrixMixin, UpdateView):
    model = Rol
    form_class = RolGlobalForm
    template_name = 'core_admin/pages/rol_form.html'
    success_url = reverse_lazy('core_admin:ruta_lista_roles')

    def get_queryset(self):
        return Rol.objects.filter(estacion__isnull=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Rol: {self.object.nombre}"
        context['accion'] = "Actualizar Rol"
        
        # 1. Inyectar la matriz de permisos (del Mixin)
        context['permissions_matrix'] = self.get_permissions_matrix()
        
        # 2. Inyectar los IDs actuales para que aparezcan marcados (checked)
        context['rol_permissions_ids'] = set(self.object.permisos.values_list('id', flat=True))
        
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # 1. Guardar cambios básicos (nombre, descripción)
                self.object = form.save(commit=False)
                self.object.save()

                # 2. GUARDADO EXPLÍCITO (La Solución)
                permisos_seleccionados = form.cleaned_data['permisos']

                print(f"DEBUG: Actualizando a {permisos_seleccionados.count()} permisos para {self.object.nombre}")

                # Limpieza total y reasignación
                self.object.permisos.set(permisos_seleccionados)
            messages.success(self.request, f"Rol actualizado. Permisos activos: {permisos_seleccionados.count()}.")
            return redirect(self.get_success_url())
        
        except Exception as e:
            messages.error(self.request, f"Error de integridad al guardar el Rol: {e}")
            return self.form_invalid(form)
    

    def form_invalid(self, form):
        messages.error(self.request, "No se pudo guardar el Rol. Revisa que el nombre sea único y los datos correctos.")
        return super().form_invalid(form)




class RolGlobalDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Rol
    template_name = 'core_admin/pages/confirmar_eliminar_rol.html'
    success_url = reverse_lazy('core_admin:ruta_lista_roles')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # --- VALIDACIÓN MANUAL ESTRICTA ---
        # Usamos 'asignaciones' (related_name en Membresia) para ver si se usó alguna vez.
        # .exists() retorna True si hay CUALQUIER registro (Activo, Inactivo o Finalizado).
        if self.object.asignaciones.exists():
            cantidad = self.object.asignaciones.count()
            messages.error(
                request, 
                f"BLOQUEADO: El rol '{self.object.nombre}' no se puede eliminar porque está vinculado "
                f"a {cantidad} membresía(s) histórica(s) o activa(s). Esto dañaría la hoja de vida de los voluntarios."
            )
            return redirect('core_admin:rol_global_list')

        # Si pasa la validación, procedemos con el borrado estándar
        try:
            self.object.delete()
            messages.success(request, f"El rol '{self.object.nombre}' ha sido eliminado correctamente.")
        except Exception as e:
            messages.error(request, f"Error inesperado al eliminar: {e}")
            
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Eliminar Rol Global"
        # Pasamos el conteo al template para advertir antes de que den clic
        context['conteo_uso'] = self.object.asignaciones.count()
        return context




# --- LISTAR MARCAS ---
class MarcaListView(SuperuserRequiredMixin, ListView):
    model = Marca
    template_name = 'core_admin/pages/lista_marcas.html'
    context_object_name = 'marcas'
    paginate_by = 20

    def get_queryset(self):
        # Annotate: Contamos uso en Productos Globales y en Vehículos
        return Marca.objects.annotate(
            total_productos=Count('productoglobal', distinct=True),
            total_vehiculos=Count('vehiculo', distinct=True)
        ).order_by('nombre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Gestión de Marcas"
        # KPI simple
        context['kpi_total'] = self.object_list.count()
        return context




# --- CREAR MARCA ---
class MarcaCreateView(SuperuserRequiredMixin, CreateView):
    model = Marca
    form_class = MarcaForm
    template_name = 'core_admin/pages/marca_form.html'
    success_url = reverse_lazy('core_admin:ruta_lista_marcas')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Nueva Marca"
        context['accion'] = "Crear Marca"
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Marca '{form.instance.nombre}' guardada correctamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "No se pudo guardar el registro. Verifica que el nombre no esté duplicado.")
        return super().form_invalid(form)




# --- EDITAR MARCA ---
class MarcaUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Marca
    form_class = MarcaForm
    template_name = 'core_admin/pages/marca_form.html'
    success_url = reverse_lazy('core_admin:ruta_lista_marcas')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar: {self.object.nombre}"
        context['accion'] = "Guardar Cambios"
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Marca '{form.instance.nombre}' guardada correctamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "No se pudo guardar el registro. Verifica que el nombre no esté duplicado.")
        return super().form_invalid(form)




# --- ELIMINAR MARCA ---
class MarcaDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Marca
    template_name = 'core_admin/pages/confirmar_eliminar_marca.html'
    success_url = reverse_lazy('core_admin:ruta_lista_marcas')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # --- VALIDACIÓN ESTRICTA DE NEGOCIO ---
        # 1. Verificar uso en Productos Globales
        if self.object.productoglobal_set.exists():
            count = self.object.productoglobal_set.count()
            messages.error(
                request, 
                f"BLOQUEADO: La marca '{self.object.nombre}' está asignada a {count} producto(s) del catálogo global."
            )
            return redirect('core_admin:ruta_lista_marcas')

        # 2. Verificar uso en Vehículos
        if self.object.vehiculo_set.exists():
            count = self.object.vehiculo_set.count()
            messages.error(
                request, 
                f"BLOQUEADO: La marca '{self.object.nombre}' está asignada a {count} vehículo(s) del sistema."
            )
            return redirect('core_admin:ruta_lista_marcas')

        # Si pasa, borramos
        try:
            self.object.delete()
            messages.success(request, f"Marca '{self.object.nombre}' eliminada correctamente.")
        except Exception as e:
            messages.error(request, f"Error de base de datos: {e}")
            
        return redirect(self.success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Eliminar Marca"
        # Pasamos datos para advertencia visual
        context['uso_productos'] = self.object.productoglobal_set.count()
        context['uso_vehiculos'] = self.object.vehiculo_set.count()
        return context




# --- LISTAR CATEGORÍAS ---
class CategoriaListView(SuperuserRequiredMixin, ListView):
    model = Categoria
    template_name = 'core_admin/pages/lista_categorias.html'
    context_object_name = 'categorias'
    paginate_by = 20

    def get_queryset(self):
        # Annotate: Contamos cuántos productos globales usan esta categoría
        return Categoria.objects.annotate(
            total_productos=Count('productoglobal')
        ).order_by('nombre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Gestión de Categorías"
        context['kpi_total'] = self.object_list.count()
        return context




# --- CREAR CATEGORÍA ---
class CategoriaCreateView(SuperuserRequiredMixin, CreateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'core_admin/pages/categoria_form.html'
    success_url = reverse_lazy('core_admin:ruta_lista_categorias')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Nueva Categoría"
        context['accion'] = "Crear Categoría"
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Categoría '{form.instance.nombre}' guardada correctamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "No se pudo guardar el registro. Verifica que el nombre no esté duplicado.")
        return super().form_invalid(form)




# --- EDITAR CATEGORÍA ---
class CategoriaUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'core_admin/pages/categoria_form.html'
    success_url = reverse_lazy('core_admin:ruta_lista_categorias')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar: {self.object.nombre}"
        context['accion'] = "Guardar Cambios"
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f"Categoría '{form.instance.nombre}' guardada correctamente.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "No se pudo guardar el registro. Verifica que el nombre no esté duplicado.")
        return super().form_invalid(form)




# --- ELIMINAR CATEGORÍA ---
class CategoriaDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Categoria
    template_name = 'core_admin/pages/confirmar_eliminar_categoria.html'
    success_url = reverse_lazy('core_admin:ruta_lista_categorias')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # --- VALIDACIÓN ESTRICTA ---
        # Si hay productos asociados, bloqueamos la eliminación
        if self.object.productoglobal_set.exists():
            count = self.object.productoglobal_set.count()
            messages.error(
                request, 
                f"BLOQUEADO: La categoría '{self.object.nombre}' contiene {count} producto(s). "
                "Debe reasignar o eliminar esos productos antes de borrar la categoría."
            )
            return redirect('core_admin:ruta_lista_categorias')

        try:
            self.object.delete()
            messages.success(request, f"Categoría '{self.object.nombre}' eliminada correctamente.")
        except Exception as e:
            messages.error(request, f"Error de base de datos: {e}")
            
        return redirect(self.success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Eliminar Categoría"
        context['uso_productos'] = self.object.productoglobal_set.count()
        return context