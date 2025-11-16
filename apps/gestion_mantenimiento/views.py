import json
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

from .models import PlanMantenimiento, PlanActivoConfig, OrdenMantenimiento, RegistroMantenimiento
from .forms import PlanMantenimientoForm, OrdenCorrectivaForm
from apps.common.mixins import BaseEstacionMixin, ObjectInStationRequiredMixin
from apps.gestion_inventario.models import Activo, Estado


class MantenimientoInicioView(View):
    def get(self, request):
        return render(request, "gestion_mantenimiento/pages/home.html")




# === GESTIÓN DE PLANES ===

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




class ApiTogglePlanActivoView(BaseEstacionMixin, View):
    """
    API: Cambia el estado 'activo_en_sistema' de un plan (On/Off).
    POST: URL param pk (id del PlanMantenimiento)
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            # 1. Buscar el plan asegurando que pertenece a la estación activa
            plan = get_object_or_404(PlanMantenimiento, pk=pk, estacion=self.estacion_activa)
            
            # 2. Toggle del booleano
            plan.activo_en_sistema = not plan.activo_en_sistema
            plan.save(update_fields=['activo_en_sistema'])
            
            # 3. Respuesta
            estado_texto = "Activado" if plan.activo_en_sistema else "Desactivado"
            return JsonResponse({
                'status': 'ok',
                'nuevo_estado': plan.activo_en_sistema,
                'mensaje': f'Plan {estado_texto} correctamente.'
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)




# === GESTIÓN DE ÓRDENES DE TRABAJO ===

class OrdenMantenimientoListView(BaseEstacionMixin, ListView):
    """
    Bandeja de Entrada de Órdenes de Trabajo.
    Muestra las órdenes filtradas por estado y estación.
    """
    model = OrdenMantenimiento
    template_name = 'gestion_mantenimiento/pages/lista_ordenes.html'
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




class OrdenCorrectivaCreateView(BaseEstacionMixin, CreateView):
    """
    Vista para crear una Orden de Mantenimiento Correctiva (sin plan).
    """
    model = OrdenMantenimiento
    form_class = OrdenCorrectivaForm
    template_name = 'gestion_mantenimiento/pages/crear_orden_correctiva.html'
    
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
        
        # Mensaje de éxito
        messages.success(self.request, f"Orden Correctiva #{orden.id} creada. Ahora añade los activos afectados.")
        
        # Redirección: Al detalle de la orden (Espacio de Trabajo) para añadir los activos
        # NOTA: Asumimos que la ruta 'ruta_gestionar_orden' existe y espera un <pk>
        return redirect(reverse('gestion_mantenimiento:ruta_gestionar_orden', kwargs={'pk': orden.pk}))




class OrdenMantenimientoDetalleView(BaseEstacionMixin, ObjectInStationRequiredMixin, DetailView):
    """
    Panel de control para ejecutar una orden de trabajo específica.
    Muestra los activos involucrados y permite registrar tareas.
    """
    model = OrdenMantenimiento
    template_name = 'gestion_mantenimiento/pages/gestionar_orden.html'
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




# --- APIs DE FLUJO DE TRABAJO ---

class ApiCambiarEstadoOrdenView(BaseEstacionMixin, View):
    """
    API: Cambia el estado global de la orden (INICIAR / FINALIZAR / CANCELAR).
    POST: { accion: 'iniciar' | 'finalizar' | 'cancelar' }
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=self.estacion_activa)
            data = json.loads(request.body)
            accion = data.get('accion')

            if accion == 'iniciar':
                if orden.estado != OrdenMantenimiento.EstadoOrden.PENDIENTE:
                    return JsonResponse({'status': 'error', 'message': 'La orden no está pendiente.'}, status=400)
                
                orden.estado = OrdenMantenimiento.EstadoOrden.EN_CURSO
                orden.save()

                # INTEGRACIÓN: Poner activos en "EN REPARACIÓN"
                # Buscamos el estado en la DB (asumiendo que existen esos nombres según tu contexto)
                try:
                    estado_reparacion = Estado.objects.get(nombre__iexact="EN REPARACIÓN")
                    orden.activos_afectados.update(estado=estado_reparacion)
                except Estado.DoesNotExist:
                    pass # Si no existe el estado, ignoramos (o logueamos warning)

                messages.success(request, "Orden iniciada. Los activos pasaron a estado 'En Reparación'.")

            elif accion == 'finalizar':
                # Validar que todos tengan registro? Opcional. Por ahora permitimos cierre flexible.
                orden.estado = OrdenMantenimiento.EstadoOrden.REALIZADA
                orden.fecha_cierre = timezone.now()
                orden.save()
                messages.success(request, "Orden finalizada exitosamente.")

            elif accion == 'cancelar':
                orden.estado = OrdenMantenimiento.EstadoOrden.CANCELADA
                orden.fecha_cierre = timezone.now()
                orden.save()
                # INTEGRACIÓN: Devolver activos a "DISPONIBLE" si se cancela
                try:
                    estado_disponible = Estado.objects.get(nombre__iexact="DISPONIBLE")
                    orden.activos_afectados.update(estado=estado_disponible)
                except Estado.DoesNotExist:
                    pass
                messages.info(request, "Orden cancelada.")

            else:
                return JsonResponse({'status': 'error', 'message': 'Acción no válida.'}, status=400)

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)




class ApiRegistrarTareaMantenimientoView(BaseEstacionMixin, View):
    """
    API: Crea un RegistroMantenimiento para un activo específico dentro de la orden.
    POST: { activo_id, notas, exitoso (bool) }
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=self.estacion_activa)
            
            if orden.estado != OrdenMantenimiento.EstadoOrden.EN_CURSO:
                return JsonResponse({'status': 'error', 'message': 'Debe INICIAR la orden antes de registrar tareas.'}, status=400)

            data = json.loads(request.body)
            activo_id = data.get('activo_id')
            notas = data.get('notas')
            fue_exitoso = data.get('exitoso', True)

            activo = get_object_or_404(Activo, pk=activo_id, estacion=self.estacion_activa)

            # 1. Crear el Registro (Bitácora)
            # Usamos update_or_create para permitir editar la nota si vuelven a guardar
            registro, created = RegistroMantenimiento.objects.update_or_create(
                orden_mantenimiento=orden,
                activo=activo,
                defaults={
                    'usuario_ejecutor': request.user,
                    'fecha_ejecucion': timezone.now(),
                    'notas': notas,
                    'fue_exitoso': fue_exitoso
                }
            )

            # 2. INTEGRACIÓN: Actualizar estado del Activo Físico
            if fue_exitoso:
                # Si la mantención fue buena, el activo vuelve a estar operativo
                try:
                    nuevo_estado = Estado.objects.get(nombre__iexact="DISPONIBLE")
                    activo.estado = nuevo_estado
                except Estado.DoesNotExist:
                    pass
            else:
                # Si falló, queda No Operativo o En Reparación
                try:
                    nuevo_estado = Estado.objects.get(nombre__iexact="NO OPERATIVO") # O 'PENDIENTE REVISIÓN'
                    activo.estado = nuevo_estado
                except Estado.DoesNotExist:
                    pass
            
            activo.save()
            
            # 3. Actualizar configuración del Plan (si aplica) para resetear contadores
            # Solo si es exitoso y viene de un plan
            if fue_exitoso and orden.plan_origen:
                plan_config = PlanActivoConfig.objects.filter(plan=orden.plan_origen, activo=activo).first()
                if plan_config:
                    plan_config.fecha_ultima_mantencion = timezone.now()
                    plan_config.horas_uso_en_ultima_mantencion = activo.horas_uso_totales
                    plan_config.save()

            return JsonResponse({'status': 'ok', 'mensaje': 'Registro guardado.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)