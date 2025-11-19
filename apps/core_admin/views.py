from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView
from django.db.models import Count, Q, ProtectedError
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponseRedirect

from .mixins import SuperuserRequiredMixin
from .forms import EstacionForm, ProductoGlobalForm
from apps.gestion_inventario.models import Estacion, Ubicacion, Vehiculo, Prestamo, Compartimento, Categoria, Marca, ProductoGlobal, Producto, Activo, LoteInsumo, MovimientoInventario
from apps.gestion_usuarios.models import Membresia


class AdministracionInicioView(View):
    template_name = "core_admin/pages/home.html"
    def get(self, request):
        return render(request, self.template_name)
    



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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Eliminar Producto Maestro"
        return context