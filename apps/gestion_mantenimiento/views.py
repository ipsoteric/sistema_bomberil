import json
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import JsonResponse
from django.utils import timezone

from .models import PlanMantenimiento, PlanActivoConfig, OrdenMantenimiento, RegistroMantenimiento
from .forms import PlanMantenimientoForm, OrdenCorrectivaForm
from apps.common.mixins import BaseEstacionMixin, ObjectInStationRequiredMixin, AuditoriaMixin
from apps.gestion_inventario.models import Activo, Estado


class MantenimientoInicioView(BaseEstacionMixin, TemplateView):
    """
    Dashboard principal del módulo.
    Ofrece métricas clave, alertas de vencimiento y accesos rápidos.
    """
    template_name = 'gestion_mantenimiento/pages/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.now()
        estacion = self.estacion_activa

        # --- 1. KPIs Principales (Tarjetas Superiores) ---
        # Órdenes Pendientes (Todo lo que no está cerrado)
        ordenes_activas = OrdenMantenimiento.objects.filter(
            estacion=estacion,
            estado__in=['PENDIENTE', 'EN_CURSO']
        )
        context['kpi_pendientes'] = ordenes_activas.count()
        
        # Planes Activos
        context['kpi_planes'] = PlanMantenimiento.objects.filter(
            estacion=estacion, 
            activo_en_sistema=True
        ).count()

        # Activos Fuera de Servicio (En Reparación)
        # Buscamos por nombre de estado, siendo flexibles con mayúsculas/minúsculas
        context['kpi_en_taller'] = Activo.objects.filter(
            estacion=estacion,
            estado__nombre__icontains='REPARACIÓN' # Ajustar según tus nombres reales de estado
        ).count()

        # --- 2. Órdenes Urgentes (Tabla) ---
        # Mostramos las 5 órdenes más urgentes (Vencidas o próximas a vencer)
        context['ordenes_urgentes'] = ordenes_activas.order_by('fecha_programada')[:5]

        # --- 3. Datos para Gráficos (Chart.js) ---
        # Gráfico de Distribución de Estado de Órdenes
        datos_estado = OrdenMantenimiento.objects.filter(estacion=estacion).values('estado').annotate(total=Count('estado'))
        
        # Preparamos estructura para JS: {'PENDIENTE': 5, 'REALIZADA': 10...}
        stats_dict = {item['estado']: item['total'] for item in datos_estado}
        
        context['chart_labels'] = json.dumps(['Pendiente', 'En Curso', 'Realizada', 'Cancelada'])
        context['chart_data'] = json.dumps([
            stats_dict.get('PENDIENTE', 0),
            stats_dict.get('EN_CURSO', 0),
            stats_dict.get('REALIZADA', 0),
            stats_dict.get('CANCELADA', 0),
        ])

        context['hoy'] = hoy # Para comparar fechas en template
        return context




# === GESTIÓN DE PLANES ===

class PlanMantenimientoListView(BaseEstacionMixin, PermissionRequiredMixin, ListView):
    """
    Vista para listar los planes de mantenimiento.
    Incluye búsqueda, paginación y filtrado estricto por Estación Activa.
    """
    model = PlanMantenimiento
    template_name = 'gestion_mantenimiento/pages/lista_planes.html'
    permission_required = 'gestion_mantenimiento.accion_gestion_mantenimiento_ver_ordenes'
    context_object_name = 'planes'
    paginate_by = 10  # Elementos por página

    def get_queryset(self):
        """
        Sobrescribimos el queryset para filtrar por la estación activa y búsquedas.
        """
        # 1. Filtro Base: Solo planes de la estación activa en sesión
        # self.estacion_activa viene del BaseEstacionMixin
        queryset = PlanMantenimiento.objects.filter(
            estacion=self.estacion_activa
        )

        # 2. Búsqueda (Search)
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(nombre__icontains=q)
            )

        # 3. Ordenamiento: Más recientes primero
        return queryset.order_by('-fecha_creacion')

    def get_context_data(self, **kwargs):
        """
        Agregamos datos extra al contexto.
        """
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Planes de Mantenimiento'
        context['busqueda'] = self.request.GET.get('q', '')
        return context




class PlanMantenimientoCrearView(BaseEstacionMixin, PermissionRequiredMixin, AuditoriaMixin, CreateView):
    """
    Vista para crear un nuevo plan de mantenimiento.
    Asigna automáticamente la estación activa al plan.
    """
    model = PlanMantenimiento
    form_class = PlanMantenimientoForm
    template_name = 'gestion_mantenimiento/pages/crear_plan.html'
    permission_required = 'gestion_mantenimiento.accion_gestion_mantenimiento_gestionar_planes'
    success_url = reverse_lazy('gestion_mantenimiento:ruta_lista_planes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Crear Plan de Mantenimiento'
        return context

    def form_valid(self, form):
        """
        Antes de guardar, asignamos la estación activa de la sesión
        al objeto PlanMantenimiento.
        """
        plan = form.save(commit=False)
        plan.estacion = self.estacion_activa
        plan.save()

        # --- AUDITORÍA ---
        self.auditar(
            verbo="creó un nuevo plan de mantenimiento preventivo",
            objetivo=plan,
            objetivo_repr=plan.nombre,
            detalles={
                'nombre_plan': plan.nombre,
                # Si tienes un campo 'frecuencia' o 'descripcion' en el modelo, 
                # sería bueno agregarlo aquí también.
            }
        )
        
        messages.success(self.request, f'El plan "{plan.nombre}" ha sido creado exitosamente.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Por favor corrija los errores en el formulario.')
        return super().form_invalid(form)




class PlanMantenimientoGestionarView(BaseEstacionMixin, PermissionRequiredMixin, ObjectInStationRequiredMixin, DetailView):
    """
    Vista principal para gestionar los activos de un plan específico.
    Muestra la lista actual y provee la interfaz para añadir/quitar.
    """
    model = PlanMantenimiento
    template_name = 'gestion_mantenimiento/pages/gestionar_plan.html'
    permission_required = 'gestion_mantenimiento.accion_gestion_mantenimiento_gestionar_planes'
    context_object_name = 'plan'
    station_lookup = 'estacion' # Para ObjectInStationRequiredMixin

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Gestionar: {self.object.nombre}'
        
        # Obtenemos la configuración de activos (la tabla intermedia)
        # Usamos select_related para evitar N+1 queries al mostrar detalles del activo
        context['activos_config'] = PlanActivoConfig.objects.filter(
            plan=self.object
        ).select_related('activo', 'activo__producto__producto_global')
        
        return context




class PlanMantenimientoEditarView(BaseEstacionMixin, PermissionRequiredMixin, ObjectInStationRequiredMixin, AuditoriaMixin, UpdateView):
    """
    Vista para editar un plan existente.
    Protegida por ObjectInStationRequiredMixin para asegurar propiedad.
    """
    model = PlanMantenimiento
    form_class = PlanMantenimientoForm
    template_name = 'gestion_mantenimiento/pages/editar_plan.html'
    permission_required = 'gestion_mantenimiento.accion_gestion_mantenimiento_gestionar_planes'
    success_url = reverse_lazy('gestion_mantenimiento:ruta_lista_planes')
    station_lookup = 'estacion' # Define el campo para verificar la propiedad

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Editar Plan: {self.object.nombre}'
        return context

    def form_valid(self, form):

        # 2. --- AUDITORÍA ---
        if form.changed_data:
            self.auditar(
                verbo="actualizó la configuración del plan de mantenimiento",
                objetivo=self.object,
                objetivo_repr=self.object.nombre,
                detalles={
                    'nombre_plan': self.object.nombre,
                    'campos_modificados': form.changed_data
                }
            )

        messages.success(self.request, f'Los cambios en el plan "{self.object.nombre}" se han guardado.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'No se pudieron guardar los cambios. Revise el formulario.')
        return super().form_invalid(form)




class PlanMantenimientoEliminarView(BaseEstacionMixin, PermissionRequiredMixin, ObjectInStationRequiredMixin, AuditoriaMixin, DeleteView):
    """
    Vista para eliminar un plan de mantenimiento.
    Protegida para asegurar que solo se borren planes de la propia estación.
    """
    model = PlanMantenimiento
    template_name = 'gestion_mantenimiento/pages/eliminar_plan.html'
    permission_required = 'gestion_mantenimiento.accion_gestion_mantenimiento_gestionar_planes'
    success_url = reverse_lazy('gestion_mantenimiento:ruta_lista_planes')
    station_lookup = 'estacion'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Eliminar Plan: {self.object.nombre}'
        
        # Información de impacto para mostrar en la alerta
        context['ordenes_pendientes'] = self.object.ordenes_generadas.filter(
            estado__in=['PENDIENTE', 'EN_CURSO']
        ).count()
        return context

    def form_valid(self, form):
        nombre_plan = self.object.nombre
        response = super().form_valid(form)

        # 2. --- AUDITORÍA ---
        # Usamos objetivo=None porque el plan ya no existe en BD,
        # pero usamos objetivo_repr para que el log sea legible.
        self.auditar(
            verbo="eliminó permanentemente el plan de mantenimiento",
            objetivo=None,
            objetivo_repr=nombre_plan,
            detalles={'nombre_plan_eliminado': nombre_plan}
        )

        messages.success(self.request, f'El plan "{nombre_plan}" ha sido eliminado correctamente.')
        return response




# === GESTIÓN DE ÓRDENES DE TRABAJO ===
class OrdenMantenimientoListView(BaseEstacionMixin, PermissionRequiredMixin, ListView):
    """
    Bandeja de Entrada de Órdenes de Trabajo.
    Muestra las órdenes filtradas por estado y estación.
    """
    model = OrdenMantenimiento
    template_name = 'gestion_mantenimiento/pages/lista_ordenes.html'
    permission_required = 'gestion_mantenimiento.accion_gestion_mantenimiento_ver_ordenes'
    context_object_name = 'ordenes'
    paginate_by = 15

    def get_queryset(self):
        # 1. Base: Solo órdenes de mi estación
        queryset = OrdenMantenimiento.objects.filter(
            estacion=self.estacion_activa
        ).select_related('plan_origen', 'responsable').prefetch_related('activos_afectados')

        # 2. Filtro por Estado (Tabs de navegación)
        # 'activos': Pendientes y En Curso (Default)
        # 'historial': Realizadas y Canceladas
        filtro_estado = self.request.GET.get('estado', 'activos')
        
        if filtro_estado == 'historial':
            queryset = queryset.filter(estado__in=[
                OrdenMantenimiento.EstadoOrden.REALIZADA,
                OrdenMantenimiento.EstadoOrden.CANCELADA
            ])
            # Ordenar por fecha de cierre descendente (lo más reciente primero)
            queryset = queryset.order_by('-fecha_cierre', '-fecha_programada')
        else:
            # Por defecto mostramos lo pendiente (lo que requiere acción)
            queryset = queryset.filter(estado__in=[
                OrdenMantenimiento.EstadoOrden.PENDIENTE,
                OrdenMantenimiento.EstadoOrden.EN_CURSO
            ])
            # Ordenar por urgencia: Primero lo más antiguo programado (vencido)
            queryset = queryset.order_by('fecha_programada')

        # 3. Búsqueda manual (ID o Nombre del Plan)
        q = self.request.GET.get('q')
        if q:
            # Buscamos por ID numérico o nombre del plan
            if q.isdigit():
                queryset = queryset.filter(id=q)
            else:
                queryset = queryset.filter(
                    Q(plan_origen__nombre__icontains=q) | 
                    Q(tipo_orden__icontains=q)
                )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Órdenes de Trabajo'
        context['filtro_estado'] = self.request.GET.get('estado', 'activos')
        context['busqueda'] = self.request.GET.get('q', '')
        context['hoy'] = timezone.now() # Para lógica visual de "Vencido" en template
        return context




class OrdenCorrectivaCreateView(BaseEstacionMixin, PermissionRequiredMixin, AuditoriaMixin, CreateView):
    """
    Vista para crear una Orden de Mantenimiento Correctiva (sin plan).
    """
    model = OrdenMantenimiento
    form_class = OrdenCorrectivaForm
    template_name = 'gestion_mantenimiento/pages/crear_orden_correctiva.html'
    permission_required = 'gestion_mantenimiento.accion_gestion_mantenimiento_gestionar_ordenes'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Nueva Orden Correctiva'
        return context

    def form_valid(self, form):
        orden = form.save(commit=False)
        # Asignamos datos automáticos
        orden.estacion = self.estacion_activa
        orden.tipo_orden = OrdenMantenimiento.TipoOrden.CORRECTIVA
        orden.estado = OrdenMantenimiento.EstadoOrden.PENDIENTE
        orden.save()

        # --- AUDITORÍA ---
        self.auditar(
            verbo="creó una nueva Orden de Mantenimiento Correctiva",
            objetivo=orden,
            objetivo_repr=f"Orden #{orden.id} (Correctiva)",
            detalles={
                'descripcion_inicial': orden.descripcion_falla if hasattr(orden, 'descripcion_falla') else 'Sin descripción inicial'
            }
        )
        
        # Mensaje de éxito
        messages.success(self.request, f"Orden Correctiva #{orden.id} creada. Ahora añade los activos afectados.")
        
        # Redirección: Al detalle de la orden (Espacio de Trabajo) para añadir los activos
        # NOTA: Asumimos que la ruta 'ruta_gestionar_orden' existe y espera un <pk>
        return redirect(reverse('gestion_mantenimiento:ruta_gestionar_orden', kwargs={'pk': orden.pk}))




class OrdenMantenimientoDetalleView(BaseEstacionMixin, PermissionRequiredMixin, ObjectInStationRequiredMixin, DetailView):
    """
    Panel de control para ejecutar una orden de trabajo específica.
    Muestra los activos involucrados y permite registrar tareas.
    """
    model = OrdenMantenimiento
    template_name = 'gestion_mantenimiento/pages/gestionar_orden.html'
    permission_required = 'gestion_mantenimiento.accion_gestion_mantenimiento_gestionar_ordenes'
    context_object_name = 'orden'
    station_lookup = 'estacion'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Orden #{self.object.id}'
        
        # Obtenemos los activos afectados
        # Optimizamos consulta trayendo datos del producto
        activos = self.object.activos_afectados.select_related(
            'producto__producto_global', 
            'compartimento__ubicacion'
        ).all()

        # Estructuramos los datos para la plantilla:
        # Necesitamos saber para cada activo si YA TIENE un registro en esta orden.
        lista_activos = []
        registros_existentes = {
            reg.activo_id: reg for reg in self.object.registros.all()
        }

        for activo in activos:
            registro = registros_existentes.get(activo.id)
            lista_activos.append({
                'activo': activo,
                'registro': registro, # Será None si no se ha trabajado aún
                'estado_trabajo': 'COMPLETADO' if registro else 'PENDIENTE'
            })
        
        context['lista_activos_trabajo'] = lista_activos
        
        # Progreso
        total = len(activos)
        completados = len(registros_existentes)
        context['progreso'] = {
            'total': total,
            'completados': completados,
            'porcentaje': int((completados / total) * 100) if total > 0 else 0
        }

        return context