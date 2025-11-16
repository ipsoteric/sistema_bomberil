from django.views import View
from django.views.generic import ListView, CreateView
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages

from .models import PlanMantenimiento
from .forms import PlanMantenimientoForm
from apps.common.mixins import BaseEstacionMixin


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

class PlanMantenimientoGestionarView(View):
    pass

class PlanMantenimientoEditarView(View):
    pass

class PlanMantenimientoEliminarView(View):
    pass

class ApiTogglePlanActivoView(View):
    pass

class ApiBuscarActivoParaPlanView(View):
    pass

class ApiAnadirActivoEnPlanView(View):
    pass

class ApiQuitarActivoDePlanView(View):
    pass