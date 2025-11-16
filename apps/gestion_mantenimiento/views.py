from django.shortcuts import render
from django.views import View
from django.views.generic import ListView
from django.db.models import Q

from .models import PlanMantenimiento
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




class PlanMantenimientoCrearView(View):
    pass

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

class MantenimientoInicioView(View):
    pass