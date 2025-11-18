from django.shortcuts import render
from django.views import View
from django.views.generic import ListView, DetailView
from django.db.models import Count, Q

from .mixins import SuperuserRequiredMixin
from apps.gestion_inventario.models import Estacion, Ubicacion, Vehiculo, Prestamo, Producto, Activo


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

        # --- 1. MINI DASHBOARD (KPIs) ---
        # Cantidad de SKUs (Productos únicos en el catálogo local)
        context['kpi_total_productos'] = Producto.objects.filter(estacion=estacion).count()
        # Cantidad de Activos Físicos (Equipos serializados reales)
        context['kpi_total_activos'] = Activo.objects.filter(estacion=estacion).count()
        # Préstamos que están pendientes (En manos de terceros)
        context['kpi_prestamos_pendientes'] = Prestamo.objects.filter(
            estacion=estacion, 
            estado='PEN'
        ).count()

        # --- 2. FLOTA VEHICULAR ---
        # Obtenemos los vehículos a través de sus ubicaciones, optimizando la consulta
        # Traemos la marca y el tipo para no hacer consultas extra en el template
        context['vehiculos'] = Vehiculo.objects.filter(
            ubicacion__estacion=estacion
        ).select_related('ubicacion', 'tipo_vehiculo', 'marca').order_by('ubicacion__nombre')

        # --- 3. INFRAESTRUCTURA (ÁREAS) ---
        # Obtenemos las ubicaciones que NO son vehículos (Bodegas, Oficinas, Pañoles)
        # Usamos 'Vehículo' textualmente porque así está definido en tu modelo como string
        context['ubicaciones_fisicas'] = Ubicacion.objects.filter(
            estacion=estacion
        ).exclude(
            tipo_ubicacion__nombre='Vehículo'
        ).select_related('tipo_ubicacion').annotate(
            # Opcional: Contar cuántos compartimentos tiene cada ubicación
            total_compartimentos=Count('compartimento')
        ).order_by('nombre')

        context['menu_activo'] = 'estaciones'
        return context