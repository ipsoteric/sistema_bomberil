import json
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse

from .models import PlanMantenimiento, PlanActivoConfig
from .forms import PlanMantenimientoForm
from apps.common.mixins import BaseEstacionMixin, ObjectInStationRequiredMixin
from apps.gestion_inventario.models import Activo


class MantenimientoInicioView(View):
    def get(self, request):
        return render(request, "gestion_mantenimiento/pages/home.html")




class PlanMantenimientoListView(BaseEstacionMixin, ListView):
    """
    Vista para listar los planes de mantenimiento.
    Incluye búsqueda, paginación y filtrado estricto por Estación Activa.
    """
    model = PlanMantenimiento
    template_name = 'gestion_mantenimiento/pages/lista_planes.html'
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




class PlanMantenimientoCrearView(BaseEstacionMixin, CreateView):
    """
    Vista para crear un nuevo plan de mantenimiento.
    Asigna automáticamente la estación activa al plan.
    """
    model = PlanMantenimiento
    form_class = PlanMantenimientoForm
    template_name = 'gestion_mantenimiento/pages/crear_plan.html'
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
        
        messages.success(self.request, f'El plan "{plan.nombre}" ha sido creado exitosamente.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Por favor corrija los errores en el formulario.')
        return super().form_invalid(form)




class PlanMantenimientoGestionarView(BaseEstacionMixin, ObjectInStationRequiredMixin, DetailView):
    """
    Vista principal para gestionar los activos de un plan específico.
    Muestra la lista actual y provee la interfaz para añadir/quitar.
    """
    model = PlanMantenimiento
    template_name = 'gestion_mantenimiento/pages/gestionar_plan.html'
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




class PlanMantenimientoEditarView(BaseEstacionMixin, ObjectInStationRequiredMixin, UpdateView):
    """
    Vista para editar un plan existente.
    Protegida por ObjectInStationRequiredMixin para asegurar propiedad.
    """
    model = PlanMantenimiento
    form_class = PlanMantenimientoForm
    template_name = 'gestion_mantenimiento/pages/editar_plan.html'
    success_url = reverse_lazy('gestion_mantenimiento:ruta_lista_planes')
    station_lookup = 'estacion' # Define el campo para verificar la propiedad

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Editar Plan: {self.object.nombre}'
        return context

    def form_valid(self, form):
        messages.success(self.request, f'Los cambios en el plan "{self.object.nombre}" se han guardado.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'No se pudieron guardar los cambios. Revise el formulario.')
        return super().form_invalid(form)




class PlanMantenimientoEliminarView(BaseEstacionMixin, ObjectInStationRequiredMixin, DeleteView):
    """
    Vista para eliminar un plan de mantenimiento.
    Protegida para asegurar que solo se borren planes de la propia estación.
    """
    model = PlanMantenimiento
    template_name = 'gestion_mantenimiento/pages/eliminar_plan.html'
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
        messages.success(self.request, f'El plan "{nombre_plan}" ha sido eliminado correctamente.')
        return response




class ApiTogglePlanActivoView(View):
    pass




# --- APIs para Interactividad AJAX ---
class ApiBuscarActivoParaPlanView(BaseEstacionMixin, View):
    """
    API: Busca activos de la estación que NO estén ya en el plan actual.
    GET params: q (búsqueda), plan_id
    """
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        plan_id = request.GET.get('plan_id')

        if not query or len(query) < 2:
            return JsonResponse({'results': []})

        # 1. Obtener el plan para saber qué excluir
        plan = get_object_or_404(PlanMantenimiento, id=plan_id, estacion=self.estacion_activa)
        
        # 2. Filtrar activos:
        # - Pertenecen a mi estación
        # - Coinciden con nombre o código
        # - NO están ya en este plan
        activos = Activo.objects.filter(
            estacion=self.estacion_activa
        ).filter(
            Q(codigo_activo__icontains=query) | 
            Q(producto__producto_global__nombre_oficial__icontains=query)
        ).exclude(
            configuraciones_plan__plan=plan
        ).select_related(
            'producto__producto_global', 
            'compartimento__ubicacion', 
        )[:10] # Limitar resultados

        # 3. Serializar
        results = []
        for activo in activos:
            ubicacion_str = f"{activo.compartimento.ubicacion.nombre} > {activo.compartimento.nombre}" if activo.compartimento else "Sin ubicación"
            results.append({
                'id': activo.id,
                'codigo': activo.codigo_activo,
                'nombre': activo.producto.producto_global.nombre_oficial,
                'ubicacion': ubicacion_str,
                'imagen_url': activo.producto.producto_global.imagen_thumb_small.url if activo.producto.producto_global.imagen_thumb_small else None
            })

        return JsonResponse({'results': results})




class ApiAnadirActivoEnPlanView(BaseEstacionMixin, View):
    """
    API: Añade un activo a un plan.
    POST body: { plan_id, activo_id }
    """
    def post(self, request, plan_pk, *args, **kwargs):
        try:
            data = json.loads(request.body)
            activo_id = data.get('activo_id')
            
            # Validaciones de seguridad
            plan = get_object_or_404(PlanMantenimiento, pk=plan_pk, estacion=self.estacion_activa)
            activo = get_object_or_404(Activo, pk=activo_id, estacion=self.estacion_activa)

            # Crear la relación si no existe
            config, created = PlanActivoConfig.objects.get_or_create(
                plan=plan,
                activo=activo,
                defaults={
                    'horas_uso_en_ultima_mantencion': activo.horas_uso_totales 
                    # Inicializamos con las horas actuales para que empiece a contar desde ahora
                }
            )

            if not created:
                return JsonResponse({'status': 'error', 'message': 'El activo ya está en el plan.'}, status=400)

            messages.success(request, f"Activo {activo.codigo_activo} añadido al plan.")
            return JsonResponse({'status': 'ok'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)




class ApiQuitarActivoDePlanView(BaseEstacionMixin, View):
    """
    API: Quita un activo de un plan.
    DELETE: URL param pk (id de PlanActivoConfig)
    """
    def delete(self, request, pk, *args, **kwargs):
        try:
            # Validamos que la configuración pertenezca a un plan de MI estación
            config = get_object_or_404(PlanActivoConfig, pk=pk, plan__estacion=self.estacion_activa)
            activo_nombre = config.activo.codigo_activo
            config.delete()
            
            messages.warning(request, f"Activo {activo_nombre} removido del plan.")
            return JsonResponse({'status': 'ok'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)