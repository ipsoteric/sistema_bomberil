import json
import datetime
import qrcode
import io
import uuid
from itertools import chain
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView, DeleteView, UpdateView, ListView, DetailView, CreateView
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db import models
from django.db.models import Count, Sum, Q, Subquery, OuterRef, ProtectedError, Value, Case, When, CharField, F
from django.db.models.functions import Coalesce
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models.functions import Coalesce
from dateutil.relativedelta import relativedelta
from django.db.models.functions import Coalesce, Abs
from django.utils.functional import cached_property

from .utils import generar_sku_sugerido
from core.settings import (
    INVENTARIO_UBICACION_AREA_NOMBRE as AREA_NOMBRE, 
    INVENTARIO_UBICACION_VEHICULO_NOMBRE as VEHICULO_NOMBRE, 
)

from apps.gestion_usuarios.models import Membresia
from apps.common.mixins import ModuleAccessMixin, EstacionActivaRequiredMixin, BaseEstacionMixin
from apps.gestion_inventario.mixins import UbicacionMixin

from .models import (
    Estacion, 
    Ubicacion, 
    Vehiculo,
    TipoUbicacion, 
    Compartimento, 
    Activo,
    ProductoGlobal,
    Producto,
    Marca,
    Categoria,
    LoteInsumo,
    Proveedor,
    ContactoProveedor,
    Region,
    Comuna,
    Estado,
    Prestamo,
    PrestamoDetalle,
    Destinatario,
    MovimientoInventario,
    TipoMovimiento
    )

from .forms import (
    AreaForm, 
    AreaEditForm,
    VehiculoUbicacionCreateForm,
    VehiculoUbicacionEditForm,
    VehiculoDetalleEditForm,
    CompartimentoForm, 
    CompartimentoEditForm, 
    ProductoGlobalForm, 
    ProductoLocalEditForm,
    ProductoStockDetalleFilterForm,
    ProveedorForm,
    ContactoProveedorForm,
    RecepcionCabeceraForm,
    RecepcionDetalleFormSet,
    ActivoSimpleCreateForm,
    LoteInsumoSimpleCreateForm,
    LoteAjusteForm,
    BajaExistenciaForm,
    ExtraviadoExistenciaForm,
    LoteConsumirForm,
    MovimientoFilterForm,
    TransferenciaForm,
    PrestamoCabeceraForm,
    PrestamoDetalleFormSet,
    PrestamoFilterForm,
    DestinatarioFilterForm,
    DestinatarioForm,
    EtiquetaFilterForm
    )


class InventarioInicioView(BaseEstacionMixin, TemplateView):
    """
    Vista de inicio (Dashboard) del módulo de Gestión de Inventario.
    Optimizada con agregaciones condicionales para reducir hits a la BD.
    """
    template_name = "gestion_inventario/pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Datos de fecha
        hoy = timezone.now().date()
        fecha_limite_vencimiento = hoy + relativedelta(days=60)

        # 1. Definir Filtros Base (QuerySets reutilizables)
        # Usamos self.estacion_activa_id provisto por EstacionActivaRequiredMixin
        activos_qs = Activo.objects.filter(estacion_id=self.estacion_activa_id)
        lotes_qs = LoteInsumo.objects.filter(compartimento__ubicacion__estacion_id=self.estacion_activa_id)

        # 2. KPIs Numéricos: Agregación Condicional (1 consulta por modelo en lugar de N)
        kpis_activos = activos_qs.aggregate(
            operativos=Count('id', filter=Q(estado__tipo_estado__nombre='OPERATIVO')),
            no_operativos=Count('id', filter=Q(estado__tipo_estado__nombre='NO OPERATIVO')),
            prestamo=Count('id', filter=Q(estado__nombre='EN PRÉSTAMO EXTERNO')),
            vencen=Count('id', filter=Q(fecha_expiracion__range=[hoy, fecha_limite_vencimiento]) | Q(fin_vida_util_calculada__range=[hoy, fecha_limite_vencimiento]))
        )

        kpis_lotes = lotes_qs.aggregate(
            operativos=Count('id', filter=Q(estado__tipo_estado__nombre='OPERATIVO')),
            no_operativos=Count('id', filter=Q(estado__tipo_estado__nombre='NO OPERATIVO')),
            prestamo=Count('id', filter=Q(estado__nombre='EN PRÉSTAMO EXTERNO')),
            vencen=Count('id', filter=Q(fecha_expiracion__range=[hoy, fecha_limite_vencimiento]))
        )

        # KPI: Stock Bajo
        # **NOTA:** El modelo Producto no tiene un campo 'stock_minimo'.
        # Si se añadiera, la consulta sería:
        # context['kpi_stock_bajo'] = Producto.objects.filter(estacion_id=estacion_activa_id, stock_actual__lt=F('stock_minimo')).count()
        # Por ahora, lo omitimos.

        # Asignación de totales al contexto
        context['kpi_total_operativas'] = kpis_activos['operativos'] + kpis_lotes['operativos']
        context['kpi_total_no_operativas'] = kpis_activos['no_operativos'] + kpis_lotes['no_operativos']
        context['kpi_total_prestamo'] = kpis_activos['prestamo'] + kpis_lotes['prestamo']
        context['kpi_proximos_a_vencer'] = kpis_activos['vencen'] + kpis_lotes['vencen']

        # 3. Listas para Alertas (Widgets)
        # Optimizamos con select_related para evitar N+1 en el template
        select_related_fields = ('producto__producto_global', 'compartimento')
        
        context['alerta_activos_vencen'] = activos_qs.select_related(*select_related_fields).filter(
            Q(fecha_expiracion__range=[hoy, fecha_limite_vencimiento]) |
            Q(fin_vida_util_calculada__range=[hoy, fecha_limite_vencimiento])
        ).order_by('fecha_expiracion')[:5]

        context['alerta_lotes_vencen'] = lotes_qs.select_related(*select_related_fields).filter(
            fecha_expiracion__range=[hoy, fecha_limite_vencimiento]
        ).order_by('fecha_expiracion')[:5]

        context['alerta_activos_revision'] = activos_qs.select_related(*select_related_fields).filter(
            estado__nombre='PENDIENTE REVISIÓN'
        )[:5]
        
        context['alerta_lotes_revision'] = lotes_qs.select_related(*select_related_fields).filter(
            estado__nombre='PENDIENTE REVISIÓN'
        )[:5]

        context['alerta_prestamos_atrasados'] = Prestamo.objects.filter(
            estacion_id=self.estacion_activa_id,
            fecha_devolucion_esperada__lt=hoy,
            estado=Prestamo.EstadoPrestamo.PENDIENTE
        ).select_related('destinatario')[:5]

        # 4. Widget de Actividad Reciente
        # Usamos Abs() en la DB para calcular el valor absoluto sin iterar en Python
        context['actividad_reciente'] = MovimientoInventario.objects.filter(
            estacion_id=self.estacion_activa_id
        ).select_related(
            'usuario', 
            'compartimento_origen', 
            'compartimento_destino',
            'activo__producto__producto_global',
            'lote_insumo__producto__producto_global'
        ).annotate(
            cantidad_abs=Abs('cantidad_movida')
        ).order_by('-fecha_hora')[:10]

        return context




class AreaListaView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista para listar las Áreas (Ubicaciones) de la estación activa,
    excluyendo vehículos y mostrando conteos optimizados.
    """
    template_name = "gestion_inventario/pages/lista_areas.html"
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_ubicaciones"
    model = Ubicacion

    def get_queryset(self):
        return (
            # --- CONSULTA OPTIMIZADA ---
            # Usamos .annotate() para calcular todo en una sola consulta.
            self.model.objects
            .filter(estacion_id=self.estacion_activa_id)
            .filter(tipo_ubicacion__nombre=AREA_NOMBRE)
            .annotate(
                # 1. Contar el número de compartimentos
                total_compartimentos=Count('compartimento', distinct=True),
                # 2. Contar el número de Activos únicos
                total_activos=Count('compartimento__activo', distinct=True),
                # 3. Sumar la CANTIDAD de todos los Lotes de Insumos
                total_cantidad_insumos=Coalesce(Sum('compartimento__loteinsumo__cantidad'), 0)
            )
            .select_related('tipo_ubicacion') # Optimiza la carga del tipo_ubicacion
            .order_by('nombre') # Ordenamos alfabéticamente
        )
    
    def get_context_data(self, **kwargs):
        ubicaciones_con_totales = self.get_queryset()
        # --- CÁLCULO FINAL (Tu lógica) ---
        # Iteramos para sumar los totales en una sola variable para la plantilla.
        for ubicacion in ubicaciones_con_totales:
            ubicacion.total_existencias = ubicacion.total_activos + ubicacion.total_cantidad_insumos

        context = {'ubicaciones': ubicaciones_con_totales}
        return context
         
    def get(self, request):
        context = self.get_context_data()
        return render(request, self.template_name, context)




class AreaCrearView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista para crear ubicaciones de tipo "ÁREA"
    """
    template_name = "gestion_inventario/pages/crear_area.html"
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_ubicaciones"
    form_class = AreaForm

    def get_form(self, data=None): # Helper para instanciar el formulario
        return self.form_class(data)

    def get_context_data(self, **kwargs): # Helper para poblar el contexto
        context = {'formulario': kwargs.get('form')}
        return context
    
    def get_success_url(self, ubicacion_id):
        return reverse('gestion_inventario:ruta_gestionar_ubicacion', kwargs={'ubicacion_id': ubicacion_id})


    def get(self, request, *args, **kwargs):
        form = self.get_form()
        context = self.get_context_data(form=form)
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        form = self.get_form(request.POST)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
        

    def form_valid(self, form):
        # Guardar sin confirmar para asignar campos
        ubicacion = form.save(commit=False)

        # Obtener tipo de ubicación "ÁREA". Si no existe, se crea
        tipo_ubicacion, _ = TipoUbicacion.objects.get_or_create(
            nombre__iexact=AREA_NOMBRE, 
            defaults={'nombre': AREA_NOMBRE}
        )
        # Asignar tipo de ubicación
        ubicacion.tipo_ubicacion = tipo_ubicacion

        # Asignar la estación desde la sesión
        try:
            estacion_obj = self.estacion_activa
            ubicacion.estacion = estacion_obj
        except Estacion.DoesNotExist:
            messages.error(self.request, "La estación activa en sesión no es válida.")
            # Usamos reverse() aquí porque no es a nivel de clase
            return redirect(reverse('portal:ruta_inicio'))
        
        # Guardar el objeto final
        ubicacion.save()

        # Enviar mensaje de éxito
        messages.success(self.request, f'Almacén/ubicación "{ubicacion.nombre.title()}" creado exitosamente.')

        return redirect(self.get_success_url(ubicacion.id))
    

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)




class UbicacionDetalleView(BaseEstacionMixin, PermissionRequiredMixin, UbicacionMixin, View):
    """
    Vista para gestionar un área/ubicación: muestra detalles, 
    resúmenes de stock, lista de compartimentos con sus totales,
    y una lista detallada de todas las existencias en el área.
    """
    template_name = 'gestion_inventario/pages/gestionar_ubicacion.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_ubicaciones"
    redirect_url = reverse_lazy('gestion_inventario:ruta_inicio')
    model = Ubicacion


    def get_object(self):
        ubicacion_id = self.kwargs.get('ubicacion_id')
        return(
            get_object_or_404(self.model, id=ubicacion_id, estacion_id=self.estacion_activa_id)
        )


    def get_context_data(self, **kwargs):
        # 1. Obtener el objeto ubicación
        ubicacion = self.object

        compartimentos_con_stock = Compartimento.objects.filter(ubicacion=ubicacion).annotate(
            total_activos=Count('activo', distinct=True),
            total_cantidad_insumos=Coalesce(Sum('loteinsumo__cantidad'), 0)
        ).order_by('nombre')

        # 4. Calcular el resumen de stock total para el área (Tarjeta Izquierda)
        resumen_activos_area = 0
        resumen_insumos_area = 0
        for c in compartimentos_con_stock:
            c.total_existencias = c.total_activos + c.total_cantidad_insumos
            resumen_activos_area += c.total_activos
            resumen_insumos_area += c.total_cantidad_insumos
        
        resumen_total_area = resumen_activos_area + resumen_insumos_area

        # 5. Obtener la lista detallada de todo el stock en esta área
        activos_en_area = Activo.objects.filter(compartimento__ubicacion=ubicacion).select_related(
            'producto__producto_global', 'compartimento', 'estado'
        )
        lotes_en_area = LoteInsumo.objects.filter(compartimento__ubicacion=ubicacion).select_related(
            'producto__producto_global', 'compartimento'
        )

        stock_items_list = list(chain(activos_en_area, lotes_en_area))
        
        # 6. Ordenar la lista detallada (p.ej. por nombre de compartimento, luego por producto)
        stock_items_list.sort(key=lambda x: (x.compartimento.nombre, x.producto.producto_global.nombre_oficial))
        
        # 7. Preparar el contexto completo
        context = {
            'ubicacion': ubicacion,
            'compartimentos': compartimentos_con_stock, # Queryset anotado
            'stock_items': stock_items_list,           # Lista combinada para la tabla
            'resumen_activos_area': resumen_activos_area,
            'resumen_insumos_area': resumen_insumos_area,
            'resumen_total_area': resumen_total_area,
            'today': timezone.now().date(),
        }
        return context


    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)




class UbicacionDeleteView(BaseEstacionMixin, PermissionRequiredMixin, UbicacionMixin, View):
    """
    Vista para confirmar y ejecutar la eliminación de una Ubicación (Área o Vehículo).
    Maneja ProtectedError si la ubicación aún tiene compartimentos.
    """
    template_name = 'gestion_inventario/pages/eliminar_ubicacion.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_ubicaciones"
    redirect_url = reverse_lazy('gestion_inventario:ruta_gestionar_ubicacion')
    model = Ubicacion

    def get_object(self):
        ubicacion_id = self.kwargs.get('ubicacion_id')
        return (
            get_object_or_404(
            self.model.objects.select_related('tipo_ubicacion'),
            id=ubicacion_id,
            estacion_id=self.estacion_activa
            )
        )
    

    def get_context_data(self, **kwargs):
        ubicacion = self.object
        context = {'ubicacion':ubicacion}
        return context

    
    def get_success_url(self, **kwargs):
        return reverse(f'gestion_inventario:ruta_lista_{kwargs.get("tipo_ubicacion")}')


    def get(self, request, *args, **kwargs):  
        context = self.get_context_data()
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):

        ubicacion = self.object
        
        # Guardamos el tipo y nombre antes de borrar
        tipo_nombre = ubicacion.tipo_ubicacion.nombre
        ubicacion_nombre = ubicacion.nombre
        
        try:
            # Intento de eliminación
            ubicacion.delete()
            
            messages.success(request, f"El {tipo_nombre.lower()} '{ubicacion_nombre}' ha sido eliminado exitosamente.")
            
            # Redirigir a la lista correspondiente
            if tipo_nombre == 'VEHÍCULO':
                return redirect(self.get_success_url(tipo_ubicacion = "vehiculos"))
            else:
                return redirect(self.get_success_url(tipo_ubicacion = "areas"))

        except ProtectedError:
            # Si falla (on_delete=PROTECT), capturamos el error
            messages.error(request, f"No se puede eliminar '{ubicacion_nombre}'. Asegúrese de que todos sus compartimentos (incluido 'General') estén vacíos y hayan sido eliminados primero.")
            # Devolvemos al usuario a la página de gestión
            return redirect(self.redirect_url, ubicacion_id=ubicacion.id)
        
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")
            return redirect(self.redirect_url, ubicacion_id=ubicacion.id)




class AreaEditarView(BaseEstacionMixin, PermissionRequiredMixin, UbicacionMixin, View):
    """
    Editar datos de una ubicación/almacén.
    """
    template_name = "gestion_inventario/pages/editar_area.html"
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_ubicaciones"
    form_class = AreaEditForm
    model = Ubicacion


    def get_object(self):
        ubicacion_id = self.kwargs.get('ubicacion_id')
        return get_object_or_404(
            self.model.objects.select_related('tipo_ubicacion'),
            id=ubicacion_id,
            estacion_id=self.estacion_activa,
            tipo_ubicacion__nombre=AREA_NOMBRE
        )


    def get_context_data(self, **kwargs):
        context = {
            'formulario': kwargs.get('form'),
            # Añadimos 'ubicacion' al contexto (útil en el template)
            # 'self.object' fue establecido por el mixin antes de llegar aquí.
            'ubicacion': self.object 
        }
        return context
    

    def get_success_url(self):
        return reverse('gestion_inventario:ruta_gestionar_ubicacion', kwargs={'ubicacion_id': self.object.id})
    

    def get(self, request, *args, **kwargs):
        # Instanciamos el form con la 'instance' para pre-llenarlo
        form = self.form_class(instance=self.object)
        
        context = self.get_context_data(form=form)
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        # Instanciamos el form con los datos del POST Y la 'instance'
        form = self.form_class(
            request.POST, 
            request.FILES, 
            instance=self.object
        )
        
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
    

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Almacén actualizado correctamente.')
        return redirect(self.get_success_url())


    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)




class VehiculoListaView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista para listar los Vehículos (Ubicaciones de tipo 'VEHÍCULO')
    de la estación activa, mostrando conteos optimizados.
    """
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_ubicaciones"
    template_name = "gestion_inventario/pages/lista_vehiculos.html"
    model = Ubicacion

    def get_queryset(self):
        # Obtener lista de vehículos
        return (
            # --- CONSULTA OPTIMIZADA PARA VEHÍCULOS ---
            self.model.objects
            .filter(
                tipo_ubicacion__nombre__iexact=VEHICULO_NOMBRE,
                estacion_id=self.estacion_activa
            )
            .annotate(
                total_compartimentos=Count('compartimento', distinct=True),
                total_activos=Count('compartimento__activo', distinct=True),
                total_cantidad_insumos=Coalesce(Sum('compartimento__loteinsumo__cantidad'), 0)
            )
            # Incluimos detalles del vehículo y su tipo para mostrar en la tabla
            .select_related(
                'tipo_ubicacion', 
                'detalles_vehiculo', 
                'detalles_vehiculo__tipo_vehiculo',
                'detalles_vehiculo__marca' 
            ) 
            .order_by('nombre')
        )


    def get_context_data(self):
        # Obtener lista de vehículos
        vehiculos_con_totales = self.get_queryset()
        # Calculamos el total de existencias
        for vehiculo in vehiculos_con_totales:
            vehiculo.total_existencias = vehiculo.total_activos + vehiculo.total_cantidad_insumos

        context = {"vehiculos":vehiculos_con_totales}
        return context


    def get(self, request):
        context = self.get_context_data()
        return render(request, self.template_name, context)




class VehiculoCrearView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista para crear un nuevo Vehículo.
    Maneja la creación simultánea en los modelos Ubicacion y Vehiculo.
    """
    template_name = 'gestion_inventario/pages/crear_vehiculo.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_ubicaciones"
    config_error_redirect_url = 'gestion_inventario:ruta_lista_vehiculos'
    form_ubicacion_class = VehiculoUbicacionCreateForm
    form_detalles_class = VehiculoDetalleEditForm

    def get_context_data(self, **kwargs):
        context = {
            'form_ubicacion': kwargs.get('form_ubicacion'),
            'form_detalles': kwargs.get('form_detalles'),
        }
        return context
    
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(
            form_ubicacion=self.form_ubicacion_class(),
            form_detalles=self.form_detalles_class()
        )
        return render(request, self.template_name, context)
    

    def post(self, request, *args, **kwargs):
        # Instanciamos formularios con los datos del POST
        form_ubicacion = self.form_ubicacion_class(request.POST)
        form_detalles = self.form_detalles_class(request.POST)

        # Validamos AMBOS
        if form_ubicacion.is_valid() and form_detalles.is_valid():
            # Obtenemos el TipoUbicacion (solo si los forms son válidos)
            try:
                tipo_vehiculo_obj = TipoUbicacion.objects.get(nombre=VEHICULO_NOMBRE)

            except TipoUbicacion.DoesNotExist:
                messages.error(request, f'Error de configuración: No se encontró el tipo "{VEHICULO_NOMBRE}"')
                return redirect(self.config_error_redirect_url)
            
            return self.form_valid(form_ubicacion, form_detalles, tipo_vehiculo_obj)
        
        else:
            return self.form_invalid(form_ubicacion, form_detalles)
        

    def form_valid(self, form_ubicacion, form_detalles, tipo_vehiculo_obj):
        try:
            # Tu lógica de transacción es perfecta
            with transaction.atomic():
                # 1. Guardar Ubicacion (sin commit)
                ubicacion_obj = form_ubicacion.save(commit=False)
                
                # Asignar campos faltantes
                ubicacion_obj.estacion = self.estacion_activa 
                ubicacion_obj.tipo_ubicacion = tipo_vehiculo_obj
                ubicacion_obj.save() # Guardar en BD

                # 2. Guardar Detalles (sin commit)
                detalles_obj = form_detalles.save(commit=False)
                # Asignar la relación OneToOne al objeto recién creado
                detalles_obj.ubicacion = ubicacion_obj 
                detalles_obj.save() # Guardar en BD
            
            messages.success(self.request, f"Vehículo '{ubicacion_obj.nombre}' creado exitosamente.")
            
            # Redirigimos a la vista de gestión del NUEVO vehículo
            return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion_obj.id)
        
        except Exception as e:
            # Si la transacción falla, volvemos al form_invalid
            messages.error(self.request, f"Ocurrió un error inesperado al guardar: {e}")
            return self.form_invalid(form_ubicacion, form_detalles)
        

    def form_invalid(self, form_ubicacion, form_detalles):
        messages.error(self.request, "Hubo un error. Por favor, revisa los campos de ambos formularios.")

        context = self.get_context_data(
            form_ubicacion=form_ubicacion, 
            form_detalles=form_detalles
        )
        return render(self.request, self.template_name, context)




class VehiculoEditarView(BaseEstacionMixin, PermissionRequiredMixin, UbicacionMixin, View):
    """
    Vista para editar los detalles de un Vehículo.
    Maneja dos formularios:
    1. VehiculoUbicacionEditForm (para el modelo Ubicacion)
    2. VehiculoDetalleEditForm (para el modelo Vehiculo)
    """
    template_name = 'gestion_inventario/pages/editar_vehiculo.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_ubicaciones"
    form_ubicacion_class = VehiculoUbicacionEditForm
    form_detalles_class = VehiculoDetalleEditForm
    model = Ubicacion

    def get_object(self):
        ubicacion_id = self.kwargs.get('ubicacion_id')
        return (
            get_object_or_404(
            self.model,
            id=ubicacion_id,
            estacion_id=self.estacion_activa,
            tipo_ubicacion__nombre=VEHICULO_NOMBRE
            )
        )
    
    def get_details_object(self, ubicacion):
        try:
            return ubicacion.detalles_vehiculo
        except Vehiculo.DoesNotExist:
            return None # El POST creará uno nuevo
    
    def get_context_data(self, **kwargs):
        context = {
            'form_ubicacion': kwargs.get('form_ubicacion'),
            'form_detalles': kwargs.get('form_detalles'),
            'ubicacion': self.object 
        }
        return context
    
    def get_success_url(self):
        return reverse('gestion_inventario:ruta_gestionar_ubicacion', kwargs={'ubicacion_id': self.object.id})
    

    def get(self, request, *args, **kwargs):
        # Obtenemos los objetos
        ubicacion = self.object
        vehiculo_detalles = self.get_details_object(ubicacion)
        
        # Instanciamos los formularios con sus respectivas instancias
        form_ubicacion = self.form_ubicacion_class(instance=self.object)
        form_detalles = self.form_detalles_class(instance=vehiculo_detalles)
        
        context = self.get_context_data(
            form_ubicacion=form_ubicacion, 
            form_detalles=form_detalles
        )
        return render(request, self.template_name, context)
    

    def post(self, request, *args, **kwargs):
        # Ya no necesitamos verificar la sesión, get_object() lo hace.
        ubicacion = self.object
        vehiculo_detalles = self.get_details_object(ubicacion)

        # Instanciamos formularios con los datos del POST y las instancias
        form_ubicacion = self.form_ubicacion_class(
            request.POST, request.FILES, instance=self.object
        )
        form_detalles = self.form_detalles_class(
            request.POST, instance=vehiculo_detalles
        )

        # Validamos AMBOS formularios
        if form_ubicacion.is_valid() and form_detalles.is_valid():
            return self.form_valid(form_ubicacion, form_detalles)
        else:
            return self.form_invalid(form_ubicacion, form_detalles)
        
    
    def form_valid(self, form_ubicacion, form_detalles):
        try:
            with transaction.atomic():
                # Guardamos el formulario de Ubicacion
                form_ubicacion.save()
                
                # Guardamos el formulario de Detalles (sin commit)
                detalles_obj = form_detalles.save(commit=False)
                # Asignamos la relación OneToOne a la Ubicacion (self.object)
                detalles_obj.ubicacion = self.object 
                detalles_obj.save()
            
            messages.success(self.request, f"El vehículo '{self.object.nombre}' se actualizó correctamente.")
            return redirect(self.get_success_url())
        
        except Exception as e:
            # Si la transacción falla, volvemos al form_invalid
            messages.error(self.request, f"Ocurrió un error inesperado: {e}")
            return self.form_invalid(form_ubicacion, form_detalles)
    

    def form_invalid(self, form_ubicacion, form_detalles):
        # Solo mostramos el mensaje de error si no es por una excepción de 'form_valid' (para no duplicar mensajes)
        if not any(form_ubicacion.errors.values()) and not any(form_detalles.errors.values()):
             pass # El error ya fue añadido en form_valid
        else:
             messages.error(self.request, "Hubo un error. Por favor, revisa los campos de ambos formularios.")

        context = self.get_context_data(
            form_ubicacion=form_ubicacion, 
            form_detalles=form_detalles
        )
        return render(self.request, self.template_name, context)




class CompartimentoListaView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Lista potente de compartimentos con filtros, búsqueda, paginación 
    y conteo rápido de existencias.
    """
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_ubicaciones"
    template_name = 'gestion_inventario/pages/lista_compartimentos.html'
    paginate_by = 20

    def get_queryset(self):
        """
        Construye el queryset filtrado por estación y parámetros GET.
        """
        # 1. Base: Filtrar por la estación activa del Mixin y optimizar relaciones
        qs = Compartimento.objects.filter(
            ubicacion__estacion_id=self.estacion_activa_id
        ).select_related(
            'ubicacion', 
            'ubicacion__tipo_ubicacion'
        ).annotate(
            # 2. Optimización: Contar ítems para mostrar en la lista (opcional pero útil)
            total_items=Count('activo', distinct=True) + Count('loteinsumo', distinct=True)
        )

        # 3. Filtros dinámicos (GET)
        ubicacion_id = self.request.GET.get('ubicacion')
        nombre = self.request.GET.get('nombre')
        descripcion_presente = self.request.GET.get('descripcion_presente')

        if ubicacion_id:
            try:
                # Validamos que sea un UUID real antes de filtrar para evitar errores de DB
                uuid.UUID(str(ubicacion_id))
                qs = qs.filter(ubicacion_id=ubicacion_id)
            except ValueError:
                pass # Si el string no es un UUID válido, ignoramos el filtro

        if nombre:
            qs = qs.filter(nombre__icontains=nombre)

        if descripcion_presente == '1':
            qs = qs.exclude(Q(descripcion__isnull=True) | Q(descripcion__exact=''))

        # 4. Ordenamiento
        return qs.order_by('ubicacion__nombre', 'nombre')


    def get(self, request):
        # Obtener queryset filtrado
        qs = self.get_queryset()

        # Paginación
        paginator = Paginator(qs, self.paginate_by)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Datos para los filtros (Select)
        ubicaciones = Ubicacion.objects.filter(
            estacion_id=self.estacion_activa_id
        ).order_by('nombre')

        context = {
            'compartimentos': page_obj, # Objeto paginado
            'paginator': paginator,
            'ubicaciones': ubicaciones,
            # Mantenemos el estado de los filtros en la UI
            'current_ubicacion': request.GET.get('ubicacion', ''),
            'current_nombre': request.GET.get('nombre', ''),
            'current_desc': request.GET.get('descripcion_presente', ''),
        }
        return render(request, self.template_name, context)




class CompartimentoCrearView(BaseEstacionMixin, PermissionRequiredMixin, CreateView):
    """
    Vista para crear un compartimento.
    Utiliza CreateView y @cached_property para una gestión 
    eficiente del objeto padre (Ubicacion) y el ciclo de vida del formulario.
    """
    model = Compartimento
    form_class = CompartimentoForm
    template_name = 'gestion_inventario/pages/crear_compartimento.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_ubicaciones"

    @cached_property
    def ubicacion(self):
        """
        Obtiene y cachea la ubicación padre, asegurando que pertenezca a la estación activa.
        Se ejecuta una sola vez por petición, optimizando el rendimiento.
        """
        return get_object_or_404(
            Ubicacion, 
            id=self.kwargs['ubicacion_id'], 
            estacion_id=self.estacion_activa_id
        )

    def get_context_data(self, **kwargs):
        """
        Override: Añade la ubicación al contexto y mantiene compatibilidad 
        con el nombre 'formulario' que usa tu template.
        """
        context = super().get_context_data(**kwargs)
        context['ubicacion'] = self.ubicacion
        context['formulario'] = context.get('form') 
        return context

    def form_valid(self, form):
        """
        Override: Asigna la relación con la ubicación antes de guardar 
        y añade el mensaje de éxito.
        """
        form.instance.ubicacion = self.ubicacion
        response = super().form_valid(form)
        
        messages.success(
            self.request, 
            f'Compartimento "{self.object.nombre}" creado exitosamente en {self.ubicacion.nombre}.'
        )
        return response

    def get_success_url(self):
        """
        Override: Redirige a la gestión de la ubicación padre.
        """
        return reverse('gestion_inventario:ruta_gestionar_ubicacion', kwargs={'ubicacion_id': self.ubicacion.id})




class CompartimentoDetalleView(BaseEstacionMixin, PermissionRequiredMixin, DetailView):
    """
    Vista de detalle para un compartimento.
    Implementa DetailView, separando la lógica de consulta (queryset)
    de la lógica de presentación (context_data).
    """
    model = Compartimento
    template_name = 'gestion_inventario/pages/detalle_compartimento.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_ubicaciones"
    context_object_name = 'compartimento'
    
    # Indicamos a Django que busque el parámetro 'compartimento_id' en la URL en lugar de 'pk'
    pk_url_kwarg = 'compartimento_id'

    def get_queryset(self):
        """
        Override: Define la consulta base para obtener el objeto principal.
        Aquí aplicamos:
        1. Seguridad: Filtro por estación activa.
        2. Optimización: select_related y annotations para contadores.
        """
        return super().get_queryset().filter(
            ubicacion__estacion_id=self.estacion_activa_id
        ).select_related(
            'ubicacion', 
            'ubicacion__tipo_ubicacion'
        ).annotate(
            total_activos_calc=Count('activo', distinct=True),
            total_insumos_calc=Coalesce(Sum('loteinsumo__cantidad'), 0)
        )

    def get_context_data(self, **kwargs):
        """
        Override: Agrega datos extra al contexto (lista combinada de stock).
        """
        context = super().get_context_data(**kwargs)
        compartimento = self.object  # El objeto ya fue recuperado por get_object() usando get_queryset()

        # 1. Obtener listas detalladas (Optimizadas)
        activos_qs = Activo.objects.filter(compartimento=compartimento).select_related(
            'producto__producto_global', 
            'estado'
        )
        lotes_qs = LoteInsumo.objects.filter(compartimento=compartimento).select_related(
            'producto__producto_global'
        )

        # 2. Combinar y Ordenar (Python-side)
        stock_items_list = list(chain(activos_qs, lotes_qs))
        stock_items_list.sort(key=lambda x: x.producto.producto_global.nombre_oficial)

        # 3. Calcular totales finales usando los valores anotados en self.object
        resumen_activos = compartimento.total_activos_calc
        resumen_insumos = compartimento.total_insumos_calc
        
        context.update({
            'stock_items': stock_items_list,
            'resumen_activos': resumen_activos,
            'resumen_insumos': resumen_insumos,
            'resumen_total': resumen_activos + resumen_insumos,
            'today': timezone.now().date(),
        })
        return context




class CompartimentoEditView(BaseEstacionMixin, PermissionRequiredMixin, UpdateView):
    """
    Vista para editar un compartimento.
    Utiliza UpdateView para eliminar boilerplate, delegando 
    la gestión del formulario y el ciclo de vida HTTP a Django.
    """
    model = Compartimento
    form_class = CompartimentoEditForm
    template_name = 'gestion_inventario/pages/editar_compartimento.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_ubicaciones"
    
    # Definimos el nombre del parámetro en la URL (por defecto Django busca 'pk')
    pk_url_kwarg = 'compartimento_id' 
    
    # Definimos cómo se llamará el objeto en el template (por defecto es 'object')
    context_object_name = 'compartimento'

    def get_queryset(self):
        """
        Override: Filtra el QuerySet base para asegurar que solo se editen 
        objetos de la estación activa y optimiza la consulta.
        """
        return super().get_queryset().filter(
            ubicacion__estacion_id=self.estacion_activa_id
        ).select_related('ubicacion')

    def get_success_url(self):
        """
        Override: Define la redirección tras una edición exitosa.
        """
        return reverse('gestion_inventario:ruta_detalle_compartimento', kwargs={'compartimento_id': self.object.id})

    def form_valid(self, form):
        """
        Override: Hook para ejecutar lógica extra cuando el formulario es válido.
        """
        messages.success(self.request, f"El compartimento '{self.object.nombre}' se actualizó correctamente.")
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Override: Hook para ejecutar lógica extra cuando el formulario falla.
        """
        messages.error(self.request, "Hubo un error al actualizar el compartimento. Por favor, revisa los campos.")
        return super().form_invalid(form)




class CompartimentoDeleteView(BaseEstacionMixin, PermissionRequiredMixin, DeleteView):
    """
    Vista para eliminar un compartimento.
    Utiliza DeleteView genérica, encapsulando la lógica de negocio
    en get_object y form_valid para un manejo limpio de excepciones (ProtectedError).
    """
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_ubicaciones"
    template_name = 'gestion_inventario/pages/eliminar_compartimento.html'
    context_object_name = 'compartimento' # Para usar {{ compartimento }} en el template

    def get_object(self, queryset=None):
        """
        Override: Obtiene el objeto asegurando que pertenezca a la estación activa
        y optimizando la consulta con select_related.
        """
        compartimento_id = self.kwargs.get('compartimento_id')
        return get_object_or_404(
            Compartimento.objects.select_related('ubicacion'),
            id=compartimento_id,
            ubicacion__estacion_id=self.estacion_activa_id
        )

    def get_success_url(self):
        """
        Override: Calcula la URL de éxito dinámicamente (volver a la ubicación padre).
        """
        return reverse_lazy(
            'gestion_inventario:ruta_gestionar_ubicacion', 
            kwargs={'ubicacion_id': self.object.ubicacion.id}
        )

    def form_valid(self, form):
        """
        Override: Maneja la confirmación de eliminación (POST).
        Aquí capturamos ProtectedError para evitar crash si hay hijos.
        """
        try:
            # El método delete() de Model retorna una tupla, no lo necesitamos aquí
            self.object.delete()
            
            messages.success(self.request, f"El compartimento '{self.object.nombre}' ha sido eliminado exitosamente.")
            return HttpResponseRedirect(self.get_success_url())

        except ProtectedError:
            messages.error(
                self.request, 
                f"No se puede eliminar '{self.object.nombre}'. Asegúrese de que el compartimento esté vacío (sin Activos ni Lotes)."
            )
            # En caso de error, redirigimos al detalle del objeto que intentamos borrar
            return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=self.object.id)

        except Exception as e:
            messages.error(self.request, f"Ocurrió un error inesperado: {e}")
            return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=self.object.id)




class CatalogoGlobalListView(BaseEstacionMixin, PermissionRequiredMixin, ListView):
    """
    Muestra el Catálogo Maestro Global de Productos con filtros avanzados
    de búsqueda, marca, categoría y asignación.
    """
    model = ProductoGlobal
    template_name = 'gestion_inventario/pages/catalogo_global.html'
    context_object_name = 'productos'
    paginate_by = 12
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_catalogos"

    def get_queryset(self):
        """
        Construye el queryset aplicando filtros de búsqueda, categoría, marca y asignación.
        """
        # QuerySet Base Optimizado
        qs = super().get_queryset().select_related('marca', 'categoria').order_by('nombre_oficial')

        # Filtros Básico (GET params)
        search_query = self.request.GET.get('q')
        categoria_id = self.request.GET.get('categoria')
        marca_id = self.request.GET.get('marca')
        filtro_asignacion = self.request.GET.get('filtro', 'todos')

        # Filtro: Búsqueda
        if search_query:
            qs = qs.filter(
                Q(nombre_oficial__icontains=search_query) |
                Q(modelo__icontains=search_query) |
                Q(marca__nombre__icontains=search_query)
            )

        # Filtro: Categoría (Validación básica de dígito)
        if categoria_id and categoria_id.isdigit():
            qs = qs.filter(categoria_id=int(categoria_id))

        # Filtro: Marca
        if marca_id and marca_id.isdigit():
            qs = qs.filter(marca_id=int(marca_id))

        # Filtro: Asignación (Lógica de Negocio)
        # Obtenemos los IDs locales una sola vez para filtrar
        # Usamos self.estacion_activa_id del mixin
        if filtro_asignacion in ['asignados', 'no_asignados']:
            local_ids = Producto.objects.filter(
                estacion_id=self.estacion_activa_id
            ).values_list('producto_global_id', flat=True)

            if filtro_asignacion == 'no_asignados':
                qs = qs.exclude(id__in=local_ids)
            elif filtro_asignacion == 'asignados':
                qs = qs.filter(id__in=local_ids)

        return qs

    def get_context_data(self, **kwargs):
        """
        Agrega datos auxiliares al contexto: opciones para filtros y estado actual.
        """
        context = super().get_context_data(**kwargs)
        
        # Obtenemos el set de IDs locales para pintar la UI (ej: botón "Añadido")
        # Esto es ligero porque solo trae IDs, no objetos completos.
        context['productos_locales_set'] = set(
            Producto.objects.filter(
                estacion_id=self.estacion_activa_id
            ).values_list('producto_global_id', flat=True)
        )

        # Listas para los <select> de filtros
        context['all_categorias'] = Categoria.objects.order_by('nombre')
        context['all_marcas'] = Marca.objects.order_by('nombre')

        # Mantenemos el estado de los filtros en la UI
        context['current_search'] = self.request.GET.get('q', '')
        context['current_categoria_id'] = self.request.GET.get('categoria', '')
        context['current_marca_id'] = self.request.GET.get('marca', '')
        context['current_filtro'] = self.request.GET.get('filtro', 'todos')
        context['view_mode'] = self.request.GET.get('view', 'gallery')

        # Preservar parámetros GET en la paginación
        params = self.request.GET.copy()
        if 'page' in params:
            del params['page']
        context['query_params'] = params.urlencode()

        return context




class ProductoGlobalCrearView(BaseEstacionMixin, PermissionRequiredMixin, CreateView):
    """
    Vista para crear un Producto Global.
    Utiliza CreateView y extrae la lógica de negocio compleja 
    (creación dinámica de marcas) a un método helper encapsulado.
    """
    model = ProductoGlobal
    form_class = ProductoGlobalForm
    template_name = 'gestion_inventario/pages/crear_producto_global.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_crear_producto_global"
    success_url = reverse_lazy('gestion_inventario:ruta_catalogo_global')


    def _gestionar_creacion_marca(self, request):
        """
        Helper para detectar si se ingresó texto libre en 'marca' y crearla al vuelo.
        Retorna (POST_DATA modificado, None) o (None, ErrorMessage).
        """
        marca_input = request.POST.get('marca')
        
        # Si no hay input o es un ID numérico, no hacemos nada especial
        if not marca_input or marca_input.isdigit():
            return request.POST, None

        # Si llegamos aquí, es texto libre
        try:
            marca_obj, created = Marca.objects.get_or_create(
                nombre=marca_input.strip(), 
                defaults={'descripcion': ''}
            )
            
            if created:
                messages.info(request, f'Se ha creado la nueva marca "{marca_obj.nombre}".')
            
            # Modificamos el POST para inyectar el ID real
            post_data = request.POST.copy()
            post_data['marca'] = str(marca_obj.id)
            return post_data, None

        except IntegrityError:
            return None, f'Error: La marca "{marca_input}" no se pudo crear (posible duplicado).'
        except Exception as e:
            return None, f'Error inesperado creando marca: {str(e)}'


    def post(self, request, *args, **kwargs):
        """
        Interceptamos POST para procesar la marca antes de validar el formulario.
        """
        try:
            with transaction.atomic():
                # 1. Gestionar Marca Dinámica
                post_data_modificado, error_msg = self._gestionar_creacion_marca(request)
                
                if error_msg:
                    messages.error(request, error_msg)
                    # Renderizamos el form con los datos originales para no perder lo escrito
                    form = self.get_form()
                    return self.render_to_response(self.get_context_data(form=form))

                # 2. Re-instanciar el form con los datos (posiblemente) modificados
                form = self.get_form_class()(post_data_modificado, request.FILES)

                # 3. Validar y Guardar (Flow estándar de Django)
                if form.is_valid():
                    return self.form_valid(form)
                else:
                    return self.form_invalid(form)

        except Exception as e:
            messages.error(request, f"Error crítico: {e}")
            form = self.get_form()
            return self.render_to_response(self.get_context_data(form=form))


    def form_valid(self, form):
        messages.success(self.request, f'Producto Global "{form.instance.nombre_oficial}" creado exitosamente.')
        return super().form_valid(form)



class ProductoLocalListView(BaseEstacionMixin, PermissionRequiredMixin, ListView):
    """
    Vista del Catálogo Local de Productos.
    Implementa ListView genérica, centralizando la lógica de filtrado
    compleja en get_queryset y optimizando la carga de datos relacionados.
    """
    model = Producto
    template_name = 'gestion_inventario/pages/catalogo_local.html'
    context_object_name = 'productos'
    paginate_by = 12
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_catalogos"

    def get_queryset(self):
        """
        Construye el queryset filtrado por estación y parámetros GET.
        Aplica filtros de búsqueda, categoría, marca y atributos booleanos.
        """
        # 1. QuerySet Base: Filtrado por estación activa y optimizado
        qs = super().get_queryset().filter(
            estacion_id=self.estacion_activa_id
        ).select_related(
            'producto_global__marca', 
            'producto_global__categoria'
        )

        # 2. Captura de parámetros GET
        search_query = self.request.GET.get('q')
        categoria_id = self.request.GET.get('categoria')
        marca_id = self.request.GET.get('marca')
        es_serializado = self.request.GET.get('serializado')
        es_expirable = self.request.GET.get('expirable')
        sort_by = self.request.GET.get('sort', 'fecha_desc')

        # 3. Filtros Dinámicos
        if search_query:
            qs = qs.filter(
                Q(sku__icontains=search_query) |
                Q(producto_global__nombre_oficial__icontains=search_query) |
                Q(producto_global__modelo__icontains=search_query) |
                Q(producto_global__marca__nombre__icontains=search_query)
            )
        
        if categoria_id and categoria_id.isdigit():
            qs = qs.filter(producto_global__categoria_id=int(categoria_id))

        if marca_id and marca_id.isdigit():
            qs = qs.filter(producto_global__marca_id=int(marca_id))
            
        if es_serializado in ['si', 'no']:
            qs = qs.filter(es_serializado=(es_serializado == 'si'))
             
        if es_expirable in ['si', 'no']:
            qs = qs.filter(es_expirable=(es_expirable == 'si'))

        # 4. Ordenamiento
        ordering_map = {
            'fecha_asc': 'created_at',
            'costo_desc': ('-costo_compra', '-created_at'),
            'costo_asc': ('costo_compra', 'created_at'),
            'fecha_desc': '-created_at' # Default
        }
        
        ordering = ordering_map.get(sort_by, '-created_at')
        if isinstance(ordering, tuple):
            qs = qs.order_by(*ordering)
        else:
            qs = qs.order_by(ordering)

        return qs

    def get_context_data(self, **kwargs):
        """
        Prepara el contexto auxiliar: filtros, opciones de select y paginación.
        """
        context = super().get_context_data(**kwargs)
        
        # Obtenemos solo las marcas presentes en el catálogo local para el filtro
        # Esto es mucho más amigable que mostrar todas las marcas del sistema
        marcas_ids = self.object_list.exclude(
            producto_global__marca__isnull=True
        ).values_list(
            'producto_global__marca_id', flat=True
        ).distinct()
        
        context['all_marcas'] = Marca.objects.filter(id__in=marcas_ids).order_by('nombre')
        context['all_categorias'] = Categoria.objects.order_by('nombre')
        
        # Mantenemos el estado de la UI
        context.update({
            'current_search': self.request.GET.get('q', ''),
            'current_categoria_id': self.request.GET.get('categoria', ''),
            'current_marca_id': self.request.GET.get('marca', ''),
            'current_serializado': self.request.GET.get('serializado', ''),
            'current_expirable': self.request.GET.get('expirable', ''),
            'current_sort': self.request.GET.get('sort', 'fecha_desc'),
            'view_mode': self.request.GET.get('view', 'gallery'),
            'estacion': self.estacion_activa # Disponible gracias al Mixin
        })

        # Preservar filtros en paginación
        params = self.request.GET.copy()
        if 'page' in params:
            del params['page']
        context['query_params'] = params.urlencode()

        return context




class ProductoLocalEditView(BaseEstacionMixin, PermissionRequiredMixin, UpdateView):
    """
    Vista para editar un producto del catálogo local.
    Utiliza UpdateView y encapsula la lógica compleja de 
    recálculo de vida útil en un método transaccional dedicado.
    """
    model = Producto
    form_class = ProductoLocalEditForm
    template_name = 'gestion_inventario/pages/editar_producto_local.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_catalogo_local"
    context_object_name = 'producto'
    success_url = reverse_lazy('gestion_inventario:ruta_catalogo_local')

    def get_queryset(self):
        """
        Filtra para asegurar que solo se editen productos de la estación activa.
        """
        return super().get_queryset().filter(estacion_id=self.estacion_activa_id)

    def get_form_kwargs(self):
        """
        Pasa argumentos adicionales necesarios para el __init__ del formulario.
        """
        kwargs = super().get_form_kwargs()
        producto = self.object
        
        # Verificar dependencias (si tiene stock) para deshabilitar campos sensibles
        existe_inventario = (
            Activo.objects.filter(producto=producto).exists() or 
            LoteInsumo.objects.filter(producto=producto).exists()
        )

        kwargs.update({
            'estacion': self.estacion_activa, # Del mixin
            'disable_es_serializado': existe_inventario
        })
        return kwargs

    def get_context_data(self, **kwargs):
        """Añade la estación al contexto (usada en el template)."""
        context = super().get_context_data(**kwargs)
        context['estacion'] = self.estacion_activa
        return context

    def _recalcular_vida_util_activos(self, producto):
        """
        Método privado para actualizar la fecha de fin de vida útil 
        de todos los activos asociados.
        """
        activos = Activo.objects.filter(producto=producto)
        count = 0
        
        # Nota: No usamos update() masivo porque dependemos de la lógica 
        # en el método save() del modelo Activo para el cálculo preciso.
        for activo in activos:
            activo.save() # Dispara _calcular_fin_vida_util()
            count += 1
            
        return count

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save()
                
                # Lógica de Negocio: Recálculo de Vida Útil
                if form.has_changed() and 'vida_util_estacion_anos' in form.changed_data:
                    total_actualizados = self._recalcular_vida_util_activos(self.object)
                    
                    if total_actualizados > 0:
                        messages.info(
                            self.request, 
                            f"Se actualizó la vida útil de {total_actualizados} activos existentes."
                        )

                messages.success(
                    self.request, 
                    f'Producto "{self.object.producto_global.nombre_oficial}" actualizado correctamente.'
                )
                return super().form_valid(form)

        except IntegrityError:
            messages.error(self.request, 'Error: Ya existe otro producto en tu estación con ese SKU.')
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f'Ha ocurrido un error inesperado: {e}')
            return self.form_invalid(form)




class ProductoLocalDetalleView(BaseEstacionMixin, PermissionRequiredMixin, DetailView):
    """
    Muestra los detalles de un Producto (Local y Global) y 
    lista todo el stock existente (Activos o Lotes) de ese 
    producto en la estación.
    """
    model = Producto
    template_name = 'gestion_inventario/pages/detalle_producto_local.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_catalogos"
    context_object_name = 'producto'

    def get_queryset(self):
        """
        Obtiene el producto asegurando pertenencia a la estación y 
        precargando relaciones costosas.
        """
        return super().get_queryset().filter(
            estacion_id=self.estacion_activa_id
        ).select_related(
            'producto_global__marca', 
            'producto_global__categoria',
            'proveedor_preferido'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        producto = self.object
        
        # Parámetros GET
        self.sort_by = self.request.GET.get('sort', 'vencimiento_asc')
        self.estado_id = self.request.GET.get('estado')
        
        # Variables de Fecha para Annotations (DRY)
        today = timezone.now().date()
        warning_date = today + datetime.timedelta(days=90)
        
        # Definimos la lógica del Case/When una sola vez para reutilizar
        self.annotation_vencimiento = Case(
            When(vencimiento__isnull=True, then=Value('no_aplica')),
            When(vencimiento__lt=today, then=Value('vencido')),
            When(vencimiento__lt=warning_date, then=Value('proximo')),
            default=Value('ok'),
            output_field=CharField()
        )

        # Delegación de lógica según el tipo de producto (Strategy Pattern)
        if producto.es_serializado:
            context.update(self._get_context_activos(producto))
        else:
            context.update(self._get_context_lotes(producto))

        # Formulario de filtros y metadatos UI
        context['filter_form'] = ProductoStockDetalleFilterForm(self.request.GET)
        context['current_sort'] = self.sort_by
        context['current_estado'] = self.request.GET.get('estado', '')
        
        return context

    def _get_context_activos(self, producto):
        """Estrategia de obtención de datos para Activos (Serializados)."""
        base_qs = Activo.objects.filter(producto=producto).select_related(
            'compartimento__ubicacion', 'estado'
        )

        # 1. Resumen (antes de filtrar)
        summary_data = base_qs.values('estado__nombre').annotate(total=Count('id')).order_by('estado__nombre')
        stock_summary = {item['estado__nombre']: item['total'] for item in summary_data}
        stock_summary['total_general'] = base_qs.count()

        # 2. Filtrado
        if self.estado_id:
            base_qs = base_qs.filter(estado_id=self.estado_id)
        else:
            # Por defecto: Operativo y No Operativo (IDs 1 y 2 según tu lógica)
            base_qs = base_qs.filter(estado__tipo_estado__id__in=[1, 2])

        # 3. Anotación y Ordenamiento
        # Coalesce es clave aquí porque Activo usa dos campos de fecha posibles
        qs = base_qs.annotate(
            vencimiento=Coalesce('fecha_expiracion', 'fin_vida_util_calculada')
        ).annotate(
            estado_vencimiento=self.annotation_vencimiento
        )
        
        return {
            'stock_items': self._aplicar_ordenamiento(qs),
            'stock_summary': stock_summary
        }

    def _get_context_lotes(self, producto):
        """Estrategia de obtención de datos para Lotes (Fungibles)."""
        base_qs = LoteInsumo.objects.filter(producto=producto).select_related(
            'compartimento__ubicacion', 'estado'
        )

        # 1. Resumen (Solo lotes con cantidad > 0)
        qs_con_stock = base_qs.filter(cantidad__gt=0)
        summary_data = qs_con_stock.values('estado__nombre').annotate(total=Sum('cantidad')).order_by('estado__nombre')
        
        stock_summary = {item['estado__nombre']: item['total'] for item in summary_data}
        stock_summary['total_general'] = qs_con_stock.aggregate(total=Sum('cantidad'))['total'] or 0

        # 2. Filtrado
        if self.estado_id:
            base_qs = base_qs.filter(estado_id=self.estado_id)
        else:
            base_qs = base_qs.filter(estado__tipo_estado__id__in=[1, 2], cantidad__gt=0)

        # 3. Anotación y Ordenamiento
        qs = base_qs.annotate(
            vencimiento=F('fecha_expiracion') # Alias simple
        ).annotate(
            estado_vencimiento=self.annotation_vencimiento
        )

        return {
            'stock_items': self._aplicar_ordenamiento(qs),
            'stock_summary': stock_summary
        }

    def _aplicar_ordenamiento(self, queryset):
        """Helper común para ordenar querysets ya anotados."""
        if self.sort_by == 'vencimiento_asc':
            return queryset.order_by(F('vencimiento').asc(nulls_last=True))
        else:
            return queryset.order_by('-fecha_recepcion')




class ProveedorListView(BaseEstacionMixin, PermissionRequiredMixin, ListView):
    """
    Vista para listar Proveedores.
    Implementa ListView genérica, preservando la optimización de 
    Subquery para conteos y separando la lógica de filtrado compleja (OR lógico 
    entre contactos principales y personalizados).
    """
    model = Proveedor
    template_name = 'gestion_inventario/pages/lista_proveedores.html'
    context_object_name = 'proveedores'
    paginate_by = 15
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_proveedores"

    def get_queryset(self):
        """
        Construye el queryset.
        1. Anota el conteo de contactos sin overhead de JOINS (Subquery).
        2. Aplica filtros de búsqueda y ubicación (cruzando relaciones).
        """
        # --- 1. Optimización: Conteo vía Subquery ---
        # Calculamos el conteo en una subquery aislada para que los filtros posteriores
        # no afecten la agrupación ni generen filas duplicadas prematuramente.
        total_contactos_subquery = ContactoProveedor.objects.filter(
            proveedor_id=OuterRef('pk')
        ).values('proveedor_id').annotate(
            c=Count('pk')
        ).values('c')

        qs = super().get_queryset().select_related(
            'contacto_principal__comuna__region'
        ).annotate(
            contactos_count=Coalesce(
                Subquery(total_contactos_subquery, output_field=models.IntegerField()),
                0
            )
        ).order_by('nombre')

        # --- 2. Filtros (GET) ---
        search_query = self.request.GET.get('q')
        region_id = self.request.GET.get('region')
        comuna_id = self.request.GET.get('comuna')

        # Filtro: Búsqueda Texto
        if search_query:
            clean_rut = search_query.replace('-', '').replace('.', '')
            qs = qs.filter(
                Q(nombre__icontains=search_query) |
                Q(rut__icontains=clean_rut)
            )

        # Filtro: Ubicación (Lógica Compleja OR)
        location_filters = Q()

        if region_id and region_id.isdigit():
            # Busca en el contacto principal O en la lista de contactos adicionales
            location_filters.add(
                Q(contacto_principal__comuna__region_id=int(region_id)) |
                Q(contactos__comuna__region_id=int(region_id)),
                Q.AND
            )

        if comuna_id and comuna_id.isdigit():
            location_filters.add(
                Q(contacto_principal__comuna_id=int(comuna_id)) |
                Q(contactos__comuna_id=int(comuna_id)),
                Q.AND
            )
        
        if location_filters:
            # .distinct() es obligatorio aquí porque filtrar por 'contactos' (M2M/Reverse FK)
            # puede multiplicar las filas del proveedor.
            qs = qs.filter(location_filters).distinct()

        return qs

    def get_context_data(self, **kwargs):
        """
        Prepara los datos auxiliares para los selectores de filtro.
        """
        context = super().get_context_data(**kwargs)
        
        # Listas para filtros
        context['all_regiones'] = Region.objects.order_by('nombre')
        
        # Carga dinámica de comunas si hay región seleccionada
        region_id = self.request.GET.get('region')
        if region_id and region_id.isdigit():
            context['comunas_para_filtro'] = Comuna.objects.filter(
                region_id=int(region_id)
            ).order_by('nombre')
        else:
            context['comunas_para_filtro'] = Comuna.objects.none()

        # Estado de la UI
        context['current_search'] = self.request.GET.get('q', '')
        context['current_region_id'] = region_id or ''
        context['current_comuna_id'] = self.request.GET.get('comuna', '')

        # Preservar filtros en paginación
        params = self.request.GET.copy()
        if 'page' in params:
            del params['page']
        context['query_params'] = params.urlencode()
        
        return context




class ProveedorCrearView(BaseEstacionMixin, PermissionRequiredMixin, View):
    """
    Vista para crear un Proveedor y su Contacto Principal simultáneamente.
    Manejo de múltiples formularios con transacción atómica
    y uso estricto de mixins para contexto y seguridad.
    """
    template_name = 'gestion_inventario/pages/crear_proveedor.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_proveedores"
    success_url = reverse_lazy('gestion_inventario:ruta_lista_proveedores')

    def get(self, request, *args, **kwargs):
        """Inicializa los formularios vacíos."""
        context = {
            'proveedor_form': ProveedorForm(),
            'contacto_form': ContactoProveedorForm()
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Procesa ambos formularios. Si ambos son válidos, delega a forms_valid.
        """
        proveedor_form = ProveedorForm(request.POST)
        contacto_form = ContactoProveedorForm(request.POST)

        if proveedor_form.is_valid() and contacto_form.is_valid():
            return self.forms_valid(proveedor_form, contacto_form)
        else:
            return self.forms_invalid(proveedor_form, contacto_form)

    def forms_valid(self, proveedor_form, contacto_form):
        """
        Maneja la lógica transaccional de guardado cuando los datos son correctos.
        """
        try:
            with transaction.atomic():
                # 1. Guardar el Proveedor (sin contacto principal aún)
                proveedor = proveedor_form.save(commit=False)
                # self.estacion_activa viene garantizada por BaseEstacionMixin
                proveedor.estacion_creadora = self.estacion_activa 
                proveedor.save()

                # 2. Guardar el Contacto y vincularlo
                contacto = contacto_form.save(commit=False)
                contacto.proveedor = proveedor
                contacto.save()

                # 3. Cerrar el círculo: Asignar contacto principal
                proveedor.contacto_principal = contacto
                proveedor.save(update_fields=['contacto_principal'])

            messages.success(self.request, f'Proveedor "{proveedor.nombre}" creado exitosamente.')
            return redirect(self.success_url)

        except IntegrityError:
            # Error específico de base de datos (ej: RUT duplicado)
            messages.error(self.request, 'Error: Ya existe un proveedor registrado con ese RUT.')
            return self.forms_invalid(proveedor_form, contacto_form)
            
        except Exception as e:
            # Error genérico
            messages.error(self.request, f'Ha ocurrido un error inesperado: {e}')
            return self.forms_invalid(proveedor_form, contacto_form)

    def forms_invalid(self, proveedor_form, contacto_form):
        """
        Renderiza la plantilla con los errores de validación.
        """
        context = {
            'proveedor_form': proveedor_form,
            'contacto_form': contacto_form
        }
        return render(self.request, self.template_name, context)




class ProveedorDetalleView(BaseEstacionMixin, PermissionRequiredMixin, DetailView):
    """
    Vista de detalle de Proveedor.
    mplementa DetailView, optimizando la carga de relaciones (Globales y Locales)
    y limpiando la lógica de negocio en get_context_data.
    """
    model = Proveedor
    template_name = 'gestion_inventario/pages/detalle_proveedor.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_proveedores"
    context_object_name = 'proveedor'

    def get_queryset(self):
        """
        Obtiene el proveedor y precarga las relaciones 'globales' necesarias.
        """
        return super().get_queryset().select_related(
            'contacto_principal__comuna__region',
            'estacion_creadora'
        )

    def get_context_data(self, **kwargs):
        """
        Calcula y añade al contexto los contactos específicos (personalizados).
        """
        context = super().get_context_data(**kwargs)
        proveedor = self.object

        # 1. Buscar Contacto Personalizado de la Estación Actual
        # Usamos filter().first() para evitar try/except DoesNotExist.
        # Es más limpio: retorna el objeto o None.
        contacto_actual = ContactoProveedor.objects.filter(
            proveedor=proveedor,
            estacion_especifica=self.estacion_activa
        ).select_related(
            'comuna__region'
        ).first()

        # 2. Buscar "Otros" Contactos Personalizados
        # Excluimos el actual para no duplicarlo en la lista "otros".
        otros_contactos_qs = ContactoProveedor.objects.filter(
            proveedor=proveedor,
            estacion_especifica__isnull=False
        ).select_related(
            'estacion_especifica', 'comuna__region'
        )

        if contacto_actual:
            otros_contactos_qs = otros_contactos_qs.exclude(id=contacto_actual.id)

        # 3. Lógica de Permisos de UI (¿Es quien creó el proveedor?)
        # Comparamos IDs para ser eficientes y evitar consultas extra
        es_creador = (self.estacion_activa.id == proveedor.estacion_creadora_id)

        context.update({
            'contacto_principal': proveedor.contacto_principal,
            'contacto_estacion_actual': contacto_actual,
            'otros_contactos_personalizados': otros_contactos_qs,
            'es_estacion_creadora': es_creador,
        })

        return context




class ContactoPersonalizadoCrearView(BaseEstacionMixin, PermissionRequiredMixin, CreateView):
    """
    Vista para crear un Contacto Personalizado.
    Utiliza CreateView con chequeo de pre-condiciones en dispatch,
    propiedades cacheadas para optimización y manejo de integridad de datos.
    """
    model = ContactoProveedor
    form_class = ContactoProveedorForm
    template_name = 'gestion_inventario/pages/crear_contacto_personalizado.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_proveedores"

    @cached_property
    def proveedor(self):
        """
        Recupera el proveedor una sola vez por petición.
        """
        return get_object_or_404(Proveedor, pk=self.kwargs['proveedor_pk'])

    def dispatch(self, request, *args, **kwargs):
        """
        Validación de Regla de Negocio: Verificar unicidad antes de procesar.
        Obtenemos el ID directo de la session porque el Mixin aún no ha corrido.
        """
        # 1. Obtenemos el ID "crudo" de la sesión
        estacion_id = request.session.get('active_estacion_id')

        # Si hay ID, hacemos la validación de negocio
        if estacion_id:
            existe = ContactoProveedor.objects.filter(
                proveedor=self.proveedor,
                estacion_especifica_id=estacion_id 
            ).exists()

            if existe:
                messages.warning(
                    request, 
                    f"Tu estación ya tiene un contacto personalizado para {self.proveedor.nombre}."
                )
                return redirect('gestion_inventario:ruta_detalle_proveedor', pk=self.proveedor.pk)

        # 2. Llamamos a super(). Esto ejecutará BaseEstacionMixin.dispatch,
        # el cual validará si el ID es válido, si el usuario tiene permiso, etc.
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['proveedor'] = self.proveedor
        context['contacto_form'] = context.get('form')
        return context

    def form_valid(self, form):
        """
        Asigna las relaciones foráneas automáticamente.
        """
        form.instance.proveedor = self.proveedor
        form.instance.estacion_especifica = self.estacion_activa
        
        try:
            response = super().form_valid(form)
            messages.success(
                self.request, 
                f'Se ha creado el contacto "{self.object.nombre_contacto}" para tu estación.'
            )
            return response

        except IntegrityError:
            # Captura race-conditions si dos usuarios intentan crear al mismo tiempo
            messages.error(self.request, "Error: Ya existe un contacto personalizado para este proveedor.")
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Error inesperado: {e}")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse('gestion_inventario:ruta_detalle_proveedor', kwargs={'pk': self.proveedor.pk})




class ContactoPersonalizadoEditarView(BaseEstacionMixin, PermissionRequiredMixin, UpdateView):
    """
    Permite a una estación activa editar SU PROPIO ContactoProveedor
    específico (su 'ContactoPersonalizado').
    """
    model = ContactoProveedor
    form_class = ContactoProveedorForm
    template_name = 'gestion_inventario/pages/editar_contacto_personalizado.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_proveedores"
    context_object_name = 'contacto' # Accesible como {{ contacto }} en el HTML

    def get_queryset(self):
        """
        Filtra el queryset para que SOLO se puedan editar contactos de la estación activa.
        Django lanzará 404 automáticamente si se intenta editar otro ID.
        """
        return super().get_queryset().filter(
            estacion_especifica_id=self.estacion_activa_id
        ).select_related('proveedor', 'comuna__region')

    def get_initial(self):
        """
        Pre-pobla campos del formulario que no son del modelo (como 'region').
        """
        initial = super().get_initial()
        if self.object.comuna:
            initial['region'] = self.object.comuna.region_id
        return initial

    def get_context_data(self, **kwargs):
        """
        Añade datos extra y el alias del formulario.
        """
        context = super().get_context_data(**kwargs)
        # Tu template usa 'contacto_form' en lugar de 'form'
        context['contacto_form'] = context.get('form')
        context['proveedor'] = self.object.proveedor
        return context

    def form_valid(self, form):
        messages.success(
            self.request, 
            f'Se ha actualizado el contacto "{self.object.nombre_contacto}".'
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('gestion_inventario:ruta_detalle_proveedor', kwargs={'pk': self.object.proveedor_id})




class StockActualListView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista para mostrar, filtrar y buscar en el stock actual
    de Activos (serializados) y Lotes de Insumo (fungibles).
    """
    template_name = 'gestion_inventario/pages/stock_actual.html'
    login_url = '/acceso/login/' # Ajusta si es necesario
    paginate_by = 25
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_stock"

    def get(self, request, *args, **kwargs):
        context = {}

        # 1. Obtener la Estación Activa desde la SESIÓN
        estacion_id = request.session.get("active_estacion_id")
        
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa. Por favor, seleccione una.")
            # Redirige a la página principal del inventario (o al portal)
            return redirect('gestion_inventario:ruta_inicio') 

        try:
            # Obtenemos el objeto Estacion basado en el ID de la sesión
            estacion_usuario = Estacion.objects.get(id=estacion_id)
        except Estacion.DoesNotExist:
            messages.error(request, "La estación activa seleccionada no es válida o fue eliminada.")
            request.session["active_estacion_id"] = None # Limpiamos la sesión
            return redirect('gestion_inventario:ruta_inicio')
        

        # 2. Obtener parámetros de filtro de la URL (GET)
        query = request.GET.get('q', '')
        tipo_producto = request.GET.get('tipo', '')
        ubicacion_id = request.GET.get('ubicacion', '')
        estado_id = request.GET.get('estado', '')
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        sort_by = request.GET.get('sort', 'vencimiento_asc')

        today = timezone.now().date()
        warning_date = today + datetime.timedelta(days=90)

        # 3. Obtener querysets base, filtrados por la ESTACIÓN ACTIVA
        # Añadir anotaciones de vencimiento
        activos_qs = Activo.objects.filter(estacion=estacion_usuario).select_related(
            'producto__producto_global', 'compartimento__ubicacion', 'estado'
        ).annotate(
            vencimiento_final=Coalesce('fecha_expiracion', 'fin_vida_util_calculada'),
            estado_vencimiento=Case(
                When(vencimiento_final__isnull=True, then=Value('no_aplica')),
                When(vencimiento_final__lt=today, then=Value('vencido')),
                When(vencimiento_final__lt=warning_date, then=Value('proximo')),
                default=Value('ok'),
                output_field=CharField()
            )
        )
        
        lotes_qs = LoteInsumo.objects.filter(producto__estacion=estacion_usuario).select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).annotate(
            estado_vencimiento=Case(
                When(fecha_expiracion__isnull=True, then=Value('no_aplica')),
                When(fecha_expiracion__lt=today, then=Value('vencido')),
                When(fecha_expiracion__lt=warning_date, then=Value('proximo')),
                default=Value('ok'),
                output_field=CharField()
            )
        )

        # 4. Aplicar filtros de búsqueda (query 'q')
        if query:
            search_query_base = (
                Q(producto__producto_global__nombre_oficial__icontains=query) |
                Q(producto__sku__icontains=query) |
                Q(producto__producto_global__marca__nombre__icontains=query) |
                Q(producto__producto_global__modelo__icontains=query)
            )
            activos_qs = activos_qs.filter(
                search_query_base | 
                Q(codigo_activo__icontains=query) | 
                Q(numero_serie_fabricante__icontains=query)
            )
            lotes_qs = lotes_qs.filter(
                search_query_base | 
                Q(numero_lote_fabricante__icontains=query)
            )

        if fecha_desde:
            activos_qs = activos_qs.filter(fecha_recepcion__gte=fecha_desde)
            lotes_qs = lotes_qs.filter(fecha_recepcion__gte=fecha_desde)
        if fecha_hasta:
            activos_qs = activos_qs.filter(fecha_recepcion__lte=fecha_hasta)
            lotes_qs = lotes_qs.filter(fecha_recepcion__lte=fecha_hasta)

        # 5. Aplicar filtro de Estado (SOLO APLICA A Activo)
        if estado_id:
            activos_qs = activos_qs.filter(estado__id=estado_id)
            if tipo_producto != 'activo':
                lotes_qs = lotes_qs.none()

        # 6. Aplicar filtro de Ubicación
        if ubicacion_id:
            activos_qs = activos_qs.filter(compartimento__ubicacion__id=ubicacion_id)
            lotes_qs = lotes_qs.filter(compartimento__ubicacion__id=ubicacion_id)
        
        # 7. Combinar listas según el filtro 'tipo'
        stock_items_list = []
        if tipo_producto == 'activo':
            stock_items_list = list(activos_qs)
        elif tipo_producto == 'insumo':
            stock_items_list = list(lotes_qs)
        else:
            stock_items_list = list(chain(activos_qs, lotes_qs))

        # 8. Ordenar la lista combinada
        # Helper para obtener la clave de ordenamiento correcta
        def get_sort_key(item, sort_field):
            if sort_field == 'vencimiento':
                if hasattr(item, 'vencimiento_final'): # Es un Activo
                    return item.vencimiento_final
                elif hasattr(item, 'fecha_expiracion'): # Es un Lote
                    return item.fecha_expiracion
            elif sort_field == 'fecha':
                return getattr(item, 'fecha_recepcion', None)
            elif sort_field == 'nombre':
                return getattr(item.producto.producto_global, 'nombre_oficial', '')
            return None
        
        reverse_sort = sort_by.endswith('_desc') 
        sort_field = sort_by.replace('_desc', '').replace('_asc', '')

        if sort_field == 'vencimiento':
            # Para vencimiento ASC, los Nones (no vencen) van al final
            default_date = datetime.date.max
            stock_items_list.sort(key=lambda x: get_sort_key(x, 'vencimiento') or default_date, reverse=reverse_sort)
        
        elif sort_field == 'fecha':
            # Para fecha DESC (default original), los Nones van al final
            default_date = datetime.date.min if reverse_sort else datetime.date.max 
            stock_items_list.sort(key=lambda x: get_sort_key(x, 'fecha') or default_date, reverse=reverse_sort)
        
        elif sort_field == 'nombre':
            stock_items_list.sort(key=lambda x: get_sort_key(x, 'nombre'), reverse=reverse_sort)

        # 9. Paginación
        paginator = Paginator(stock_items_list, self.paginate_by)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        # 10. Preparar contexto para la plantilla
        context = {
            'page_obj': page_obj,
            'stock_items': page_obj.object_list, # Esta es la lista que itera tu plantilla
            'todas_las_ubicaciones': Ubicacion.objects.filter(estacion=estacion_usuario),
            'todos_los_estados': Estado.objects.all(),
            'current_q': query,
            'current_tipo': tipo_producto,
            'current_ubicacion': ubicacion_id,
            'current_estado': estado_id,
            'current_fecha_desde': fecha_desde,
            'current_fecha_hasta': fecha_hasta,
            'current_sort': sort_by,
        }
        
        return render(request, self.template_name, context)




class RecepcionStockView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    template_name = 'gestion_inventario/pages/recepcion_stock.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_recepcionar_stock"

    def get(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Seleccione una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        try:
            estacion = Estacion.objects.get(id=estacion_id)
        except Estacion.DoesNotExist:
            messages.error(request, "Estación no válida.")
            return redirect('gestion_inventario:ruta_inicio')

        cabecera_form = RecepcionCabeceraForm(estacion=estacion)
        # Pasamos la estación al formset para que filtre los selects
        detalle_formset = RecepcionDetalleFormSet(form_kwargs={'estacion': estacion}, prefix='detalles')

        # --- MEJORA: Crear el JSON con los datos del producto ---
        # (Esto es necesario para tu requisito de 'es_expirable')
        productos = Producto.objects.filter(estacion=estacion)
        product_data = {}
        for producto in productos:
            product_data[producto.id] = {
                'es_serializado': producto.es_serializado,
                'es_expirable': producto.es_expirable
            }
        # -----------------------------------------------------

        context = {
            'cabecera_form': cabecera_form,
            'detalle_formset': detalle_formset,
            'product_data_json': json.dumps(product_data)
        }
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Seleccione una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        try:
            estacion = Estacion.objects.get(id=estacion_id)
        except Estacion.DoesNotExist:
             messages.error(request, "Estación no válida.")
             return redirect('gestion_inventario:ruta_inicio')

        cabecera_form = RecepcionCabeceraForm(request.POST, estacion=estacion)
        detalle_formset = RecepcionDetalleFormSet(request.POST, form_kwargs={'estacion': estacion}, prefix='detalles')

        if cabecera_form.is_valid() and detalle_formset.is_valid():
            try:
                # Obtener estado DISPONIBLE
                estado_disponible_id = Estado.objects.get(nombre='DISPONIBLE', tipo_estado__nombre='OPERATIVO').id
                nuevos_activos_ids = []
                nuevos_lotes_ids = []

                # Usamos una transacción para asegurar que todo se guarde o nada
                with transaction.atomic():
                    proveedor = cabecera_form.cleaned_data['proveedor']
                    fecha_recepcion = cabecera_form.cleaned_data['fecha_recepcion']
                    notas_cabecera = cabecera_form.cleaned_data['notas']

                    for form in detalle_formset:
                        if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                            producto = form.cleaned_data['producto']
                            compartimento = form.cleaned_data['compartimento_destino']
                            costo = form.cleaned_data.get('costo_unitario') # Opcional

                            # Actualizar costo en ProductoLocal si se ingresó uno nuevo
                            if costo is not None and producto.costo_compra != costo:
                                producto.costo_compra = costo
                                producto.save(update_fields=['costo_compra'])

                            if producto.es_serializado:
                                # Crear un Activo
                                activo = Activo.objects.create(
                                    producto=producto,
                                    estacion=estacion,
                                    compartimento=compartimento,
                                    proveedor=proveedor, # Proveedor de la cabecera
                                    estado_id=estado_disponible_id,
                                    # codigo_activo=form.cleaned_data.get('codigo_activo'),
                                    numero_serie_fabricante=form.cleaned_data.get('numero_serie'),
                                    fecha_fabricacion=form.cleaned_data.get('fecha_fabricacion'),
                                    fecha_recepcion=fecha_recepcion, # Usamos fecha recepción como puesta en servicio inicial
                                    # fecha_expiracion=form.cleaned_data.get('fecha_expiracion_activo') # Si tuvieras expira en Activo
                                )
                                # Registrar Movimiento para el Activo
                                MovimientoInventario.objects.create(
                                    tipo_movimiento=TipoMovimiento.ENTRADA,
                                    usuario=request.user,
                                    estacion=estacion,
                                    proveedor_origen=proveedor,
                                    compartimento_destino=compartimento,
                                    activo=activo,
                                    cantidad_movida=1, # Siempre 1 para activos
                                    notas=notas_cabecera
                                )
                                nuevos_activos_ids.append(activo.id) # <-- Capturar ID
                            else:
                                # Crear o actualizar un LoteInsumo
                                # Aquí podrías buscar un lote existente con mismas características 
                                # (producto, compartimento, lote, vencimiento) y sumar cantidad,
                                # o crear siempre uno nuevo. Crearemos uno nuevo por simplicidad.
                                cantidad = form.cleaned_data['cantidad']
                                lote = LoteInsumo.objects.create(
                                    producto=producto,
                                    compartimento=compartimento,
                                    cantidad=cantidad,
                                    numero_lote_fabricante=form.cleaned_data.get('numero_lote'),
                                    fecha_expiracion=form.cleaned_data.get('fecha_vencimiento'),
                                    fecha_recepcion=fecha_recepcion
                                )
                                # Registrar Movimiento para el Lote
                                MovimientoInventario.objects.create(
                                    tipo_movimiento=TipoMovimiento.ENTRADA,
                                    usuario=request.user,
                                    estacion=estacion,
                                    proveedor_origen=proveedor,
                                    compartimento_destino=compartimento,
                                    lote_insumo=lote,
                                    cantidad_movida=cantidad,
                                    notas=notas_cabecera
                                )
                                nuevos_lotes_ids.append(lote.id) # <-- Capturar ID
                                
                messages.success(request, "Recepción de stock guardada correctamente.")
                
                # --- LÓGICA DE REDIRECCIÓN ---
                if nuevos_activos_ids or nuevos_lotes_ids:
                    # Si se crearon ítems, redirigir a la vista de impresión
                    query_params = []
                    if nuevos_activos_ids:
                        query_params.append(f"activos={','.join(map(str, nuevos_activos_ids))}")
                    if nuevos_lotes_ids:
                        query_params.append(f"lotes={','.join(map(str, nuevos_lotes_ids))}")
                    
                    return redirect(f"{reverse('gestion_inventario:ruta_imprimir_etiquetas')}?{'&'.join(query_params)}")
                else:
                    # Si no se creó nada (ej. solo forms borrados), ir al stock
                    return redirect('gestion_inventario:ruta_stock_actual')
                

            except Exception as e:
                # Si algo falla dentro de la transacción, se revierte todo
                messages.error(request, f"Error al guardar la recepción: {e}")

        else:
            # Si los formularios no son válidos, renderizar de nuevo con errores
            messages.warning(request, "Por favor, corrija los errores en el formulario.")
        
        context = {
            'cabecera_form': cabecera_form,
            'detalle_formset': detalle_formset,
            'product_data_json': self.get(request).context_data['product_data_json']
        }
        return render(request, self.template_name, context)




class AgregarStockACompartimentoView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista para añadir stock (Activos o Lotes) directamente
    a un compartimento específico.
    """
    template_name = 'gestion_inventario/pages/agregar_stock_compartimento.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_recepcionar_stock"
    model = Compartimento

    def get_context_data(self, request, compartimento_id, **kwargs):
        """Helper para construir el contexto básico."""
        estacion_id = request.session.get('active_estacion_id')
        
        compartimento = get_object_or_404(
            Compartimento.objects.select_related('ubicacion'),
            id=compartimento_id,
            ubicacion__estacion_id=estacion_id
        )

        context = {
            'compartimento': compartimento,
            'activo_form': kwargs.get(
                'activo_form', 
                ActivoSimpleCreateForm(
                    initial={'compartimento': compartimento}, 
                    estacion_id=estacion_id
                )
            ),
            'lote_form': kwargs.get(
                'lote_form', 
                LoteInsumoSimpleCreateForm(
                    initial={'compartimento': compartimento}, 
                    estacion_id=estacion_id
                )
            )
        }
        return context

    def get(self, request, compartimento_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        context = self.get_context_data(request, compartimento_id)
        return render(request, self.template_name, context)

    def post(self, request, compartimento_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        # Identificamos qué formulario se envió
        action = request.POST.get('action')
        
        # Pasamos el 'estacion_id' al constructor del form
        activo_form = ActivoSimpleCreateForm(request.POST, estacion_id=estacion_id)
        lote_form = LoteInsumoSimpleCreateForm(request.POST, estacion_id=estacion_id)
        
        if action == 'add_activo':
            if activo_form.is_valid():

                try:
                    # Buscamos el estado 'DISPONIBLE' (ID 1 según tu SQL)
                    estado_disponible = Estado.objects.get(nombre='DISPONIBLE')
                except Estado.DoesNotExist:
                    # Error crítico si el estado no existe en la BD
                    messages.error(request, "Error crítico: No se encontró el estado 'DISPONIBLE'. Contacte al administrador.")
                    context = self.get_context_data(request, compartimento_id, activo_form=activo_form)
                    context['active_tab'] = 'activo'
                    return render(request, self.template_name, context)
                
                # Hacemos commit=False para añadir la estación
                activo = activo_form.save(commit=False)
                # El modelo Activo REQUIERE una estacion_id
                activo.estacion_id = estacion_id 
                activo.estado = estado_disponible
                activo.save()
                
                messages.success(request, f"Activo '{activo.producto.producto_global.nombre_oficial}' añadido correctamente.")
                return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=compartimento_id)
            else:
                messages.error(request, "Error al añadir el Activo. Revisa los campos.")
                context = self.get_context_data(request, compartimento_id, activo_form=activo_form)
                context['active_tab'] = 'activo' # Para reabrir la pestaña correcta
                return render(request, self.template_name, context)

        elif action == 'add_insumo':
            if lote_form.is_valid():
                # El modelo LoteInsumo no tiene 'estacion_id', se guarda directo
                lote = lote_form.save()
                messages.success(request, f"Lote de '{lote.producto.producto_global.nombre_oficial}' (x{lote.cantidad}) añadido correctamente.")
                return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=compartimento_id)
            else:
                messages.error(request, "Error al añadir el Lote. Revisa los campos.")
                context = self.get_context_data(request, compartimento_id, lote_form=lote_form)
                context['active_tab'] = 'insumo' # Para reabrir la pestaña correcta
                return render(request, self.template_name, context)

        # Si 'action' no es válido, redirigir
        return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=compartimento_id)




def get_or_create_anulado_compartment(estacion: Estacion) -> Compartimento:
    """
    Busca o crea la ubicación y compartimento 'limbo' (ADMINISTRATIVA)
    para los registros anulados de una estación.
    """
    
    # 1. Buscar el TipoUbicacion "ADMINISTRATIVA"
    # (Usamos get_or_create por robustez, en caso de que se borre)
    tipo_admin, _ = TipoUbicacion.objects.get_or_create(nombre='ADMINISTRATIVA')

    # 2. Buscar o crear la Ubicación "Registros Administrativos"
    ubicacion_admin, _ = Ubicacion.objects.get_or_create(
        nombre="Registros Administrativos",
        estacion=estacion,
        tipo_ubicacion=tipo_admin,
        defaults={
            'descripcion': 'Ubicación simbólica para registros anulados por error.'
        }
    )

    # 3. Buscar o crear el Compartimento "Stock Anulado"
    compartimento_anulado, _ = Compartimento.objects.get_or_create(
        nombre="Stock Anulado",
        ubicacion=ubicacion_admin,
        defaults={
            'descripcion': 'Existencias (activos/lotes) que fueron anuladas por error de ingreso.'
        }
    )
    return compartimento_anulado




class AnularExistenciaView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista para anular un registro de existencia (Activo o LoteInsumo)
    que fue ingresado por error.
    """
    template_name = 'gestion_inventario/pages/anular_existencia.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_bajas_stock"

    def _get_item_and_check_permission(self, estacion_id, tipo_item, item_id):
        """
        Función helper para obtener el Activo o Lote y verificar pertenencia.
        """
        item = None
        if tipo_item == 'activo':
            item = get_object_or_404(
                Activo.objects.select_related('producto__producto_global', 'estado', 'compartimento__ubicacion'),
                id=item_id, 
                estacion_id=estacion_id
            )
        elif tipo_item == 'lote':
            item = get_object_or_404(
                LoteInsumo.objects.select_related('producto__producto_global', 'estado', 'compartimento__ubicacion'),
                id=item_id, 
                compartimento__ubicacion__estacion_id=estacion_id
            )
        return item

    def get(self, request, tipo_item, item_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        item = self._get_item_and_check_permission(estacion_id, tipo_item, item_id)
        if not item:
            messages.error(request, "El tipo de ítem especificado no es válido.")
            return redirect('gestion_inventario:ruta_stock_actual')
        
        if item.estado.nombre == 'ANULADO POR ERROR':
            messages.warning(request, "Esta existencia ya se encuentra anulada.")
            return redirect('gestion_inventario:ruta_stock_actual')

        context = {
            'item': item,
            'tipo_item': tipo_item
        }
        return render(request, self.template_name, context)

    def post(self, request, tipo_item, item_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        try:
            estacion_obj = Estacion.objects.get(id=estacion_id)
        except Estacion.DoesNotExist:
            messages.error(request, "Estación activa no encontrada.")
            return redirect('gestion_inventario:ruta_inicio')

        item = self._get_item_and_check_permission(estacion_id, tipo_item, item_id)
        if not item:
            messages.error(request, "El tipo de ítem especificado no es válido.")
            return redirect('gestion_inventario:ruta_stock_actual')

        try:
            # Obtenemos los objetos necesarios para la anulación
            estado_anulado = Estado.objects.get(nombre='ANULADO POR ERROR')
            compartimento_anulado_limbo = get_or_create_anulado_compartment(estacion_obj)
            
            # Guardamos el compartimento original para el Movimiento
            compartimento_original = item.compartimento

        except Estado.DoesNotExist:
            messages.error(request, "Error crítico: No se encontró el estado 'ANULADO POR ERROR'. Contacte al administrador.")
            return redirect('gestion_inventario:ruta_stock_actual')
        except Exception as e:
            messages.error(request, f"Error de configuración al buscar compartimento 'Stock Anulado': {e}")
            return redirect('gestion_inventario:ruta_stock_actual')

        try:
            with transaction.atomic():
                cantidad_a_mover = 0 # Para el movimiento
                
                # 1. Actualizar el ítem
                item.estado = estado_anulado
                item.compartimento = compartimento_anulado_limbo # <-- ¡El cambio clave!
                
                if tipo_item == 'lote':
                    cantidad_a_mover = item.cantidad * -1 # Negativo para ajuste
                    item.cantidad = 0
                else: # tipo_item == 'activo'
                    cantidad_a_mover = -1

                item.save()
                
                # 2. Crear el MovimientoInventario (como discutimos)
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.AJUSTE,
                    usuario=request.user,
                    estacion=estacion_obj,
                    compartimento_origen=compartimento_original, # De dónde salió
                    compartimento_destino=compartimento_anulado_limbo, # A dónde fue
                    activo=item if tipo_item == 'activo' else None,
                    lote_insumo=item if tipo_item == 'lote' else None,
                    cantidad_movida=cantidad_a_mover,
                    notas=f"Registro anulado por error de ingreso. Movido desde '{compartimento_original.nombre}'."
                )

            messages.success(request, f"La existencia '{item.producto.producto_global.nombre_oficial}' ha sido anulada y movida a 'Registros Administrativos'.")
            return redirect('gestion_inventario:ruta_stock_actual')

        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado al anular: {e}")
            return redirect('gestion_inventario:ruta_stock_actual')




class AjustarStockLoteView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista para ajustar la cantidad de un LoteInsumo y crear
    un MovimientoInventario de tipo AJUSTE.
    """
    template_name = 'gestion_inventario/pages/ajustar_stock_lote.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_stock_interno"

    def _get_lote_and_check_permission(self, estacion_id, lote_id):
        """ Helper para obtener el Lote y verificar permisos """
        lote = get_object_or_404(
            LoteInsumo.objects.select_related(
                'producto__producto_global', 
                'compartimento__ubicacion',
                'estado'
            ),
            id=lote_id, 
            compartimento__ubicacion__estacion_id=estacion_id
        )
        
        if lote.estado.nombre == 'ANULADO POR ERROR':
            messages.error(self.request, "No se puede ajustar un lote que ha sido anulado.")
            return None
        
        return lote

    def get(self, request, lote_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        lote = self._get_lote_and_check_permission(estacion_id, lote_id)
        if not lote:
            return redirect('gestion_inventario:ruta_stock_actual')
        
        form = LoteAjusteForm(initial={'nueva_cantidad_fisica': lote.cantidad})
        context = {'lote': lote, 'form': form}
        return render(request, self.template_name, context)

    def post(self, request, lote_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        lote = self._get_lote_and_check_permission(estacion_id, lote_id)
        if not lote:
            return redirect('gestion_inventario:ruta_stock_actual')

        form = LoteAjusteForm(request.POST)

        if form.is_valid():
            nueva_cantidad = form.cleaned_data['nueva_cantidad_fisica']
            notas = form.cleaned_data['notas']
            cantidad_actual = lote.cantidad
            
            # Cálculo de la diferencia
            cantidad_movida = nueva_cantidad - cantidad_actual # (Ej: 48 - 50 = -2)
            
            if cantidad_movida == 0:
                messages.warning(request, "No se realizó ningún cambio (la cantidad es la misma).")
                return redirect('gestion_inventario:ruta_stock_actual')

            try:
                with transaction.atomic():
                    # 1. Actualizar la cantidad del lote
                    lote.cantidad = nueva_cantidad
                    lote.save(update_fields=['cantidad', 'updated_at'])

                    # 2. Crear el registro de Movimiento (la auditoría)
                    MovimientoInventario.objects.create(
                        tipo_movimiento=TipoMovimiento.AJUSTE,
                        usuario=request.user,
                        estacion_id=estacion_id,
                        compartimento_origen=lote.compartimento, # Lugar del ajuste
                        lote_insumo=lote,
                        cantidad_movida=cantidad_movida, # Guardamos la diferencia (ej: -2)
                        notas=notas # Guardamos el motivo
                    )
                
                messages.success(request, f"Stock del lote {lote.codigo_lote} ajustado a {nueva_cantidad}.")
                return redirect('gestion_inventario:ruta_stock_actual')
                
            except Exception as e:
                messages.error(request, f"Error al guardar el ajuste: {e}")
        
        context = {'lote': lote, 'form': form}
        return render(request, self.template_name, context)




class BajaExistenciaView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista para Dar de Baja una existencia (Activo o LoteInsumo),
    cambiando su estado y generando un movimiento de SALIDA.
    """
    template_name = 'gestion_inventario/pages/dar_de_baja_existencia.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_bajas_stock"

    def _get_item_and_check_permission(self, estacion_id, tipo_item, item_id):
        """ Helper para obtener el ítem y verificar estado """
        item = None
        if tipo_item == 'activo':
            item = get_object_or_404(
                Activo.objects.select_related('producto__producto_global', 'estado', 'compartimento__ubicacion'),
                id=item_id, 
                estacion_id=estacion_id
            )
        elif tipo_item == 'lote':
            item = get_object_or_404(
                LoteInsumo.objects.select_related('producto__producto_global', 'estado', 'compartimento__ubicacion'),
                id=item_id, 
                compartimento__ubicacion__estacion_id=estacion_id
            )
        
        if item and (item.estado.nombre == 'ANULADO POR ERROR' or item.estado.nombre == 'DE BAJA'):
            messages.warning(self.request, "Esta existencia ya no está operativa y no se puede dar de baja.")
            return None
            
        return item

    def get(self, request, tipo_item, item_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        item = self._get_item_and_check_permission(estacion_id, tipo_item, item_id)
        if not item:
            return redirect('gestion_inventario:ruta_stock_actual')
        
        form = BajaExistenciaForm()
        context = {
            'item': item,
            'tipo_item': tipo_item,
            'form': form
        }
        return render(request, self.template_name, context)

    def post(self, request, tipo_item, item_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        item = self._get_item_and_check_permission(estacion_id, tipo_item, item_id)
        if not item:
            return redirect('gestion_inventario:ruta_stock_actual')

        form = BajaExistenciaForm(request.POST)

        if form.is_valid():
            notas = form.cleaned_data['notas']
            
            try:
                estado_de_baja = Estado.objects.get(nombre='DE BAJA')
            except Estado.DoesNotExist:
                messages.error(request, "Error crítico: No se encontró el estado 'DE BAJA'. Contacte al administrador.")
                return redirect('gestion_inventario:ruta_stock_actual')

            try:
                with transaction.atomic():
                    cantidad_a_mover = 0 # Para el movimiento
                    
                    # 1. Actualizar el ítem
                    item.estado = estado_de_baja
                    
                    if tipo_item == 'lote':
                        # Para lotes, registramos la cantidad restante y la ponemos a 0
                        cantidad_a_mover = item.cantidad * -1 # Negativo para salida
                        item.cantidad = 0
                    else: # tipo_item == 'activo'
                        cantidad_a_mover = -1

                    item.save()
                    
                    # 2. Crear el MovimientoInventario de SALIDA
                    MovimientoInventario.objects.create(
                        tipo_movimiento=TipoMovimiento.SALIDA,
                        usuario=request.user,
                        estacion_id=estacion_id,
                        compartimento_origen=item.compartimento, # De dónde salió
                        activo=item if tipo_item == 'activo' else None,
                        lote_insumo=item if tipo_item == 'lote' else None,
                        cantidad_movida=cantidad_a_mover,
                        notas=notas # El motivo de la baja
                    )

                messages.success(request, f"La existencia '{item.producto.producto_global.nombre_oficial}' ha sido dada de baja.")
                return redirect('gestion_inventario:ruta_stock_actual')

            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado al dar de baja: {e}")
                return redirect('gestion_inventario:ruta_stock_actual')

        # Si el formulario (notas) no es válido
        context = {
            'item': item,
            'tipo_item': tipo_item,
            'form': form
        }
        return render(request, self.template_name, context)




def get_or_create_extraviado_compartment(estacion: Estacion) -> Compartimento:
    """
    Busca o crea la ubicación (ADMINISTRATIVA) y el compartimento 'limbo' 
    para los registros extraviados de una estación.
    """
    tipo_admin, _ = TipoUbicacion.objects.get_or_create(nombre='ADMINISTRATIVA')
    
    ubicacion_admin, _ = Ubicacion.objects.get_or_create(
        nombre="Registros Administrativos",
        estacion=estacion,
        tipo_ubicacion=tipo_admin,
        defaults={'descripcion': 'Ubicación simbólica para registros anulados o dados de baja.'}
    )

    # Creamos un compartimento separado para extraviados
    compartimento_extraviado, _ = Compartimento.objects.get_or_create(
        nombre="Stock Extraviado",
        ubicacion=ubicacion_admin,
        defaults={'descripcion': 'Existencias que fueron reportadas como extraviadas.'}
    )
    return compartimento_extraviado




class ExtraviadoExistenciaView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista para reportar una existencia como Extraviada (Activo o LoteInsumo),
    cambiando su estado, moviéndola al limbo y generando un movimiento de SALIDA.
    """
    template_name = 'gestion_inventario/pages/extraviado_existencia.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_bajas_stock"

    def _get_item_and_check_permission(self, estacion_id, tipo_item, item_id):
        """ Helper para obtener el ítem y verificar estado """
        item = None
        if tipo_item == 'activo':
            item = get_object_or_404(
                Activo.objects.select_related('producto__producto_global', 'estado', 'compartimento__ubicacion'),
                id=item_id, 
                estacion_id=estacion_id
            )
        elif tipo_item == 'lote':
            item = get_object_or_404(
                LoteInsumo.objects.select_related('producto__producto_global', 'estado', 'compartimento__ubicacion'),
                id=item_id, 
                compartimento__ubicacion__estacion_id=estacion_id
            )
        
        # Comprobamos todos los estados no operativos
        if item and item.estado.nombre in ['ANULADO POR ERROR', 'DE BAJA', 'EXTRAVIADO']:
            messages.warning(self.request, "Esta existencia ya no está operativa y no se puede reportar como extraviada.")
            return None
            
        return item

    def get(self, request, tipo_item, item_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        item = self._get_item_and_check_permission(estacion_id, tipo_item, item_id)
        if not item:
            return redirect('gestion_inventario:ruta_stock_actual')
        
        form = ExtraviadoExistenciaForm()
        context = {
            'item': item,
            'tipo_item': tipo_item,
            'form': form
        }
        return render(request, self.template_name, context)

    def post(self, request, tipo_item, item_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        try:
            estacion_obj = Estacion.objects.get(id=estacion_id)
        except Estacion.DoesNotExist:
            messages.error(request, "Estación activa no encontrada.")
            return redirect('gestion_inventario:ruta_inicio')

        item = self._get_item_and_check_permission(estacion_id, tipo_item, item_id)
        if not item:
            return redirect('gestion_inventario:ruta_stock_actual')

        form = ExtraviadoExistenciaForm(request.POST)

        if form.is_valid():
            notas = form.cleaned_data['notas']
            
            try:
                estado_extraviado = Estado.objects.get(nombre='EXTRAVIADO')
                # Usamos el nuevo helper
                compartimento_limbo = get_or_create_extraviado_compartment(estacion_obj)
                compartimento_original = item.compartimento
            except Estado.DoesNotExist:
                messages.error(request, "Error crítico: No se encontró el estado 'EXTRAVIADO'. Contacte al administrador.")
                return redirect('gestion_inventario:ruta_stock_actual')
            except Exception as e:
                messages.error(request, f"Error de configuración al buscar compartimento 'Stock Extraviado': {e}")
                return redirect('gestion_inventario:ruta_stock_actual')

            try:
                with transaction.atomic():
                    cantidad_a_mover = 0
                    
                    # 1. Actualizar el ítem
                    item.estado = estado_extraviado
                    item.compartimento = compartimento_limbo # Mover al limbo
                    
                    if tipo_item == 'lote':
                        cantidad_a_mover = item.cantidad * -1
                        item.cantidad = 0
                    else: # tipo_item == 'activo'
                        cantidad_a_mover = -1

                    item.save()
                    
                    # 2. Crear el MovimientoInventario de SALIDA (tu suposición era correcta)
                    MovimientoInventario.objects.create(
                        tipo_movimiento=TipoMovimiento.SALIDA,
                        usuario=request.user,
                        estacion_id=estacion_id,
                        compartimento_origen=compartimento_original,
                        compartimento_destino=compartimento_limbo, # Destino administrativo
                        activo=item if tipo_item == 'activo' else None,
                        lote_insumo=item if tipo_item == 'lote' else None,
                        cantidad_movida=cantidad_a_mover,
                        notas=f"Reportado como extraviado. {notas}" # Motivo del extravío
                    )

                messages.success(request, f"La existencia '{item.producto.producto_global.nombre_oficial}' ha sido reportada como extraviada.")
                return redirect('gestion_inventario:ruta_stock_actual')

            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")
                return redirect('gestion_inventario:ruta_stock_actual')

        # Si el formulario (notas) no es válido
        context = {
            'item': item,
            'tipo_item': tipo_item,
            'form': form
        }
        return render(request, self.template_name, context)




class ConsumirStockLoteView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista para consumir una cantidad de un LoteInsumo y crear
    un MovimientoInventario de tipo SALIDA.
    """
    template_name = 'gestion_inventario/pages/consumir_stock_lote.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_stock_interno"

    def _get_lote_and_check_permission(self, estacion_id, lote_id):
        """ Helper para obtener el Lote y verificar permisos de consumo """
        lote = get_object_or_404(
            LoteInsumo.objects.select_related(
                'producto__producto_global', 
                'compartimento__ubicacion',
                'estado'
            ),
            id=lote_id, 
            compartimento__ubicacion__estacion_id=estacion_id
        )
        
        # Solo se puede consumir de lotes 'Disponibles' o 'Asignados'
        if lote.estado.nombre not in ['DISPONIBLE', 'ASIGNADO']:
            messages.error(self.request, f"No se puede consumir de un lote que está '{lote.estado.nombre}'.")
            return None
        
        if lote.cantidad <= 0:
            messages.warning(self.request, "Este lote ya no tiene stock para consumir.")
            return None
        
        return lote

    def get(self, request, lote_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        lote = self._get_lote_and_check_permission(estacion_id, lote_id)
        if not lote:
            return redirect('gestion_inventario:ruta_stock_actual')
        
        # Pasamos el lote al form para la validación
        form = LoteConsumirForm(lote=lote, initial={'cantidad_a_consumir': 1})
        context = {'lote': lote, 'form': form}
        return render(request, self.template_name, context)

    def post(self, request, lote_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        lote = self._get_lote_and_check_permission(estacion_id, lote_id)
        if not lote:
            return redirect('gestion_inventario:ruta_stock_actual')

        form = LoteConsumirForm(request.POST, lote=lote) # Pasar el lote

        if form.is_valid():
            cantidad_consumida = form.cleaned_data['cantidad_a_consumir']
            notas = form.cleaned_data['notas']
            
            try:
                with transaction.atomic():
                    # 1. Actualizar la cantidad del lote
                    nueva_cantidad = lote.cantidad - cantidad_consumida
                    lote.cantidad = nueva_cantidad
                    lote.save(update_fields=['cantidad', 'updated_at'])

                    # 2. Crear el registro de Movimiento (SALIDA)
                    MovimientoInventario.objects.create(
                        tipo_movimiento=TipoMovimiento.SALIDA,
                        usuario=request.user,
                        estacion_id=estacion_id,
                        compartimento_origen=lote.compartimento, # Lugar del consumo
                        lote_insumo=lote,
                        cantidad_movida=cantidad_consumida * -1, # Negativo
                        notas=notas
                    )
                
                messages.success(request, f"Se consumieron {cantidad_consumida} unidades del lote {lote.codigo_lote}.")
                return redirect('gestion_inventario:ruta_stock_actual')
                
            except Exception as e:
                messages.error(request, f"Error al guardar el consumo: {e}")
        
        context = {'lote': lote, 'form': form}
        return render(request, self.template_name, context)




class TransferenciaExistenciaView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Mueve una existencia (Activo o Lote) de un compartimento a otro
    dentro de la misma estación, generando un movimiento de TRANSFERENCIA_INTERNA.
    """
    template_name = 'gestion_inventario/pages/transferir_existencia.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_stock_interno"

    def _get_item_and_check_permission(self, estacion_id, tipo_item, item_id):
        """ Helper para obtener el ítem y verificar estado """
        item = None
        if tipo_item == 'activo':
            item = get_object_or_404(
                Activo.objects.select_related('producto__producto_global', 'estado', 'compartimento__ubicacion'),
                id=item_id, 
                estacion_id=estacion_id
            )
        elif tipo_item == 'lote':
            item = get_object_or_404(
                LoteInsumo.objects.select_related('producto__producto_global', 'estado', 'compartimento__ubicacion'),
                id=item_id, 
                compartimento__ubicacion__estacion_id=estacion_id
            )
        
        if item and item.estado.nombre not in ['DISPONIBLE', 'ASIGNADO']:
            messages.error(self.request, f"No se puede mover un ítem con estado '{item.estado.nombre}'.")
            return None
            
        return item

    def get(self, request, tipo_item, item_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        estacion_obj = Estacion.objects.get(id=estacion_id)
        item = self._get_item_and_check_permission(estacion_id, tipo_item, item_id)
        if not item:
            return redirect('gestion_inventario:ruta_stock_actual')
        
        # Pasamos el item y la estacion al formulario para que filtre el queryset
        form = TransferenciaForm(item=item, estacion=estacion_obj)
        
        context = {
            'item': item,
            'tipo_item': tipo_item,
            'form': form,
            'es_lote': (tipo_item == 'lote') # Para la plantilla
        }
        return render(request, self.template_name, context)

    def post(self, request, tipo_item, item_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        estacion_obj = Estacion.objects.get(id=estacion_id)
        item_origen = self._get_item_and_check_permission(estacion_id, tipo_item, item_id)
        if not item_origen:
            return redirect('gestion_inventario:ruta_stock_actual')

        form = TransferenciaForm(request.POST, item=item_origen, estacion=estacion_obj)

        if form.is_valid():
            compartimento_destino = form.cleaned_data['compartimento_destino']
            compartimento_origen = item_origen.compartimento
            notas = form.cleaned_data['notas']
            
            try:
                with transaction.atomic():
                    
                    if tipo_item == 'activo':
                        # --- LÓGICA PARA ACTIVOS (SIMPLE) ---
                        item_origen.compartimento = compartimento_destino
                        item_origen.save(update_fields=['compartimento', 'updated_at'])
                        
                        MovimientoInventario.objects.create(
                            tipo_movimiento=TipoMovimiento.TRANSFERENCIA_INTERNA,
                            usuario=request.user,
                            estacion=estacion_obj,
                            compartimento_origen=compartimento_origen,
                            compartimento_destino=compartimento_destino,
                            activo=item_origen,
                            cantidad_movida=1, # Siempre 1 para activos
                            notas=notas
                        )
                        msg_item_nombre = item_origen.codigo_activo
                    
                    else:
                        # --- LÓGICA PARA LOTES (COMPLEJA) ---
                        cantidad_a_mover = form.cleaned_data['cantidad']
                        
                        # 1. Buscar o crear un lote idéntico en el destino
                        # Un lote es "idéntico" si comparte:
                        # producto, lote_fabricante, fecha_expiracion y estado
                        lote_destino, created = LoteInsumo.objects.get_or_create(
                            producto=item_origen.producto,
                            compartimento=compartimento_destino,
                            numero_lote_fabricante=item_origen.numero_lote_fabricante,
                            fecha_expiracion=item_origen.fecha_expiracion,
                            estado=item_origen.estado, # Mover a un lote en el mismo estado
                            defaults={
                                'cantidad': 0,
                                'fecha_recepcion': item_origen.fecha_recepcion 
                            }
                        )
                        
                        # 2. Mover la cantidad
                        lote_destino.cantidad += cantidad_a_mover
                        item_origen.cantidad -= cantidad_a_mover
                        
                        lote_destino.save()
                        item_origen.save() # Guardamos el origen (con cantidad reducida)

                        # 3. Crear el movimiento (lo vinculamos al Lote de Origen)
                        MovimientoInventario.objects.create(
                            tipo_movimiento=TipoMovimiento.TRANSFERENCIA_INTERNA,
                            usuario=request.user,
                            estacion=estacion_obj,
                            compartimento_origen=compartimento_origen,
                            compartimento_destino=compartimento_destino,
                            lote_insumo=item_origen, # Vinculado al lote de origen
                            cantidad_movida=cantidad_a_mover, # Cantidad que se movió
                            notas=f"Transferidos {cantidad_a_mover} de {item_origen.codigo_lote} a {lote_destino.codigo_lote}. {notas}"
                        )
                        msg_item_nombre = f"{cantidad_a_mover} unidades de {item_origen.codigo_lote}"

                messages.success(request, f"Se transfirió {msg_item_nombre} a '{compartimento_destino.nombre}'.")
                return redirect('gestion_inventario:ruta_stock_actual')
                
            except Exception as e:
                messages.error(request, f"Error al procesar la transferencia: {e}")
        
        context = {
            'item': item_origen,
            'tipo_item': tipo_item,
            'form': form,
            'es_lote': (tipo_item == 'lote')
        }
        return render(request, self.template_name, context)




class CrearPrestamoView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista para crear un Préstamo (Cabecera y Detalles)
    usando un flujo de "scan-first".
    """
    template_name = 'gestion_inventario/pages/crear_prestamo.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_prestamos"

    def get(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Seleccione una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        estacion = Estacion.objects.get(id=estacion_id)

        # El GET solo necesita el formulario de cabecera
        cabecera_form = PrestamoCabeceraForm(estacion=estacion)

        context = {
            'cabecera_form': cabecera_form,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Seleccione una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        estacion = Estacion.objects.get(id=estacion_id)
        
        cabecera_form = PrestamoCabeceraForm(request.POST, estacion=estacion)
        
        # --- Lógica de POST Rediseñada ---
        # 1. Obtener la lista de ítems escaneados del input oculto
        items_json_str = request.POST.get('items_json')
        items_list = []
        if items_json_str:
            try:
                items_list = json.loads(items_json_str)
            except json.JSONDecodeError:
                messages.error(request, "Error al procesar la lista de ítems escaneados.")
        
        if not items_list:
            messages.error(request, "Debe escanear al menos un ítem para el préstamo.")
            # Forzamos que el formulario de cabecera no sea válido para re-renderizar
            cabecera_form.add_error(None, "No se escanearon ítems.")

        if cabecera_form.is_valid() and items_list:
            try:
                # Obtenemos los objetos de estado y tipo de movimiento una sola vez
                estado_prestamo = Estado.objects.get(nombre='EN PRÉSTAMO EXTERNO')
                estado_disponible = Estado.objects.get(nombre='DISPONIBLE')
                tipo_mov_prestamo = TipoMovimiento.PRESTAMO
                
                with transaction.atomic():
                    # --- 1. Guardar Destinatario (si es nuevo) ---
                    destinatario = cabecera_form.cleaned_data.get('destinatario')
                    if not destinatario:
                        nuevo_nombre = cabecera_form.cleaned_data.get('nuevo_destinatario_nombre')
                        nuevo_contacto = cabecera_form.cleaned_data.get('nuevo_destinatario_contacto')
                        destinatario, _ = Destinatario.objects.get_or_create(
                            estacion=estacion,
                            nombre_entidad=nuevo_nombre,
                            defaults={'telefono_contacto': nuevo_contacto, 'creado_por': request.user}
                        )

                    # --- 2. Guardar Cabecera de Préstamo ---
                    prestamo = cabecera_form.save(commit=False)
                    prestamo.estacion = estacion
                    prestamo.usuario_responsable = request.user
                    prestamo.destinatario = destinatario
                    prestamo.save()

                    # --- 3. Procesar Lista de Ítems (del JSON) ---
                    for item_data in items_list:
                        producto_nombre = item_data['nombre']
                        notas_prestamo = cabecera_form.cleaned_data['notas_prestamo']
                        
                        if item_data['tipo'] == 'activo':
                            # Re-validar el Activo en el momento del POST (seguridad)
                            activo = Activo.objects.select_for_update().get(
                                id=item_data['id'], 
                                estado=estado_disponible
                            )
                            
                            PrestamoDetalle.objects.create(prestamo=prestamo, activo=activo, cantidad_prestada=1)
                            activo.estado = estado_prestamo
                            activo.save(update_fields=['estado', 'updated_at'])
                            
                            MovimientoInventario.objects.create(
                                tipo_movimiento=tipo_mov_prestamo,
                                usuario=request.user,
                                estacion=estacion,
                                compartimento_origen=activo.compartimento,
                                activo=activo,
                                cantidad_movida=-1,
                                notas=f"Préstamo a {destinatario.nombre_entidad}. {notas_prestamo}"
                            )
                        
                        elif item_data['tipo'] == 'lote':
                            cantidad = int(item_data['cantidad_prestada'])
                            
                            # Re-validar el Lote en el momento del POST (seguridad)
                            lote = LoteInsumo.objects.select_for_update().get(
                                id=item_data['id'],
                                estado=estado_disponible,
                                cantidad__gte=cantidad # Asegurarse que el stock aún existe
                            )
                            
                            PrestamoDetalle.objects.create(prestamo=prestamo, lote=lote, cantidad_prestada=cantidad)
                            lote.cantidad -= cantidad
                            lote.save(update_fields=['cantidad', 'updated_at'])
                            
                            MovimientoInventario.objects.create(
                                tipo_movimiento=tipo_mov_prestamo,
                                usuario=request.user,
                                estacion=estacion,
                                compartimento_origen=lote.compartimento,
                                lote_insumo=lote,
                                cantidad_movida=cantidad * -1,
                                notas=f"Préstamo a {destinatario.nombre_entidad}. {notas_prestamo}"
                            )

                messages.success(request, f"Préstamo #{prestamo.id} creado exitosamente.")
                # TODO: Redirigir a la futura página de historial de préstamos
                return redirect('gestion_inventario:ruta_historial_prestamos') 

            except (Estado.DoesNotExist, TipoMovimiento.DoesNotExist):
                messages.error(request, "Error crítico de configuración: Faltan Estados o Tipos de Movimiento.")
            except (Activo.DoesNotExist, LoteInsumo.DoesNotExist):
                messages.error(request, "Error de concurrencia: Uno de los ítems escaneados ya no está disponible. Revise la lista y vuelva a intentarlo.")
            except Exception as e:
                messages.error(request, f"Error inesperado al guardar el préstamo: {e}")

        else:
            messages.warning(request, "Por favor, corrija los errores en el formulario.")
        
        context = {
            'cabecera_form': cabecera_form,
            # No pasamos 'items_list' de vuelta porque el JS lo maneja,
            # pero sí es útil para depurar si falla el POST
            'items_json_error': request.POST.get('items_json', '[]') 
        }
        return render(request, self.template_name, context)




class BuscarItemPrestamoJson(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    API endpoint (solo GET) para buscar un ítem por su código
    y verificar si está disponible para préstamo.
    """
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_prestamos"

    def get(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        codigo = kwargs.get('codigo')

        if not estacion_id or not codigo:
            return JsonResponse({"error": "Faltan datos (estación o código)."}, status=400)

        # 1. Buscar en Activos
        try:
            # Buscamos por el código exacto (case-insensitive)
            activo = Activo.objects.select_related('producto__producto_global', 'estado')\
                .get(codigo_activo__iexact=codigo, estacion_id=estacion_id)
            
            # Verificamos que esté 'DISPONIBLE'
            if activo.estado.nombre != 'DISPONIBLE':
                return JsonResponse({"error": f"Activo no disponible (Estado: {activo.estado.nombre})."}, status=400)

            return JsonResponse({
                "tipo": "activo",
                "id": activo.id,
                "codigo": activo.codigo_activo,
                "nombre": activo.producto.producto_global.nombre_oficial
            })
        except Activo.DoesNotExist:
            pass # No era un activo, buscar en lotes

        # 2. Buscar en Lotes
        try:
            lote = LoteInsumo.objects.select_related('producto__producto_global', 'estado')\
                .get(codigo_lote__iexact=codigo, compartimento__ubicacion__estacion_id=estacion_id)

            if lote.estado.nombre != 'DISPONIBLE':
                 return JsonResponse({"error": f"Lote no disponible (Estado: {lote.estado.nombre})."}, status=400)
            
            if lote.cantidad <= 0:
                return JsonResponse({"error": f"Lote {lote.codigo_lote} no tiene stock (Cantidad: 0)."}, status=400)

            return JsonResponse({
                "tipo": "lote",
                "id": lote.id,
                "codigo": lote.codigo_lote,
                "nombre": lote.producto.producto_global.nombre_oficial,
                "max_qty": lote.cantidad
            })
        except LoteInsumo.DoesNotExist:
            pass # No se encontró

        return JsonResponse({"error": f"Código '{codigo}' no encontrado o no disponible en esta estación."}, status=404)




class HistorialPrestamosView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista (basada en View) para mostrar el historial de préstamos externos
    de la estación activa del usuario.
    """
    template_name = 'gestion_inventario/pages/historial_prestamos.html'
    paginate_by = 25
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_prestamos"

    def get(self, request, *args, **kwargs):
        # 1. Obtener la estación activa del usuario (vía Membresia)
        try:
            membresia_activa = Membresia.objects.select_related('estacion').get(
                usuario=request.user, 
                estado=Membresia.Estado.ACTIVO
            )
            estacion_usuario = membresia_activa.estacion
        except Membresia.DoesNotExist:
            messages.error(request, "No tienes una membresía activa asignada.")
            return redirect('portal:home') # Redirige al portal

        # 2. Queryset base (optimizada)
        base_queryset = Prestamo.objects.filter(
            estacion=estacion_usuario
        ).select_related(
            'destinatario', 'usuario_responsable'
        ).order_by('-fecha_prestamo')

        # 3. Instanciar y procesar el formulario de filtro
        filter_form = PrestamoFilterForm(request.GET, estacion=estacion_usuario)

        if filter_form.is_valid():
            cleaned_data = filter_form.cleaned_data
            
            if cleaned_data.get('destinatario'):
                base_queryset = base_queryset.filter(
                    destinatario=cleaned_data['destinatario']
                )
            
            if cleaned_data.get('estado'):
                base_queryset = base_queryset.filter(
                    estado=cleaned_data['estado']
                )
            
            if cleaned_data.get('start_date'):
                base_queryset = base_queryset.filter(
                    fecha_prestamo__gte=cleaned_data['start_date']
                )

            if cleaned_data.get('end_date'):
                # Ajustamos la fecha de fin para incluir el día completo
                end_date = cleaned_data['end_date'] + datetime.timedelta(days=1)
                base_queryset = base_queryset.filter(
                    fecha_prestamo__lt=end_date
                )
        
        # 4. Paginación manual
        paginator = Paginator(base_queryset, self.paginate_by)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.get_page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.get_page(1)
        except EmptyPage:
            page_obj = paginator.get_page(paginator.num_pages)

        # 5. Construir el contexto
        context = {
            'page_obj': page_obj,
            'is_paginated': paginator.num_pages > 1,
            'filter_form': filter_form,
            'params': request.GET.urlencode() # Para mantener filtros en paginación
        }
        
        return render(request, self.template_name, context)




class GestionarDevolucionView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Vista (basada en View) para gestionar la devolución de un préstamo.
    Muestra los detalles del préstamo y procesa el registro de devoluciones.
    """
    template_name = 'gestion_inventario/pages/gestionar_devolucion.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_prestamos"

    def get_estacion_activa(self):
        """Helper para obtener la estación activa del usuario."""
        try:
            membresia_activa = Membresia.objects.select_related('estacion').get(
                usuario=self.request.user, 
                estado=Membresia.Estado.ACTIVO
            )
            return membresia_activa.estacion
        except Membresia.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        """Muestra los detalles del préstamo y sus ítems."""
        estacion = self.get_estacion_activa()
        if not estacion:
            messages.error(request, "No tienes una membresía activa asignada.")
            return redirect('portal:home')

        prestamo_id = kwargs.get('prestamo_id')
        prestamo = get_object_or_404(
            Prestamo.objects.select_related('destinatario', 'usuario_responsable'), 
            id=prestamo_id, 
            estacion=estacion
        )

        items_prestados = prestamo.items_prestados.select_related(
            'activo__producto__producto_global', 
            'lote__producto__producto_global'
        ).order_by('id')

        for item in items_prestados:
            item.cantidad_pendiente = item.cantidad_prestada - item.cantidad_devuelta

        context = {
            'prestamo': prestamo,
            'items_prestados': items_prestados
        }
        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """Procesa el formulario de registro de devoluciones."""
        estacion = self.get_estacion_activa()
        if not estacion:
            messages.error(request, "Acción no permitida.")
            return redirect('portal:home')

        prestamo_id = kwargs.get('prestamo_id')
        prestamo = get_object_or_404(Prestamo, id=prestamo_id, estacion=estacion)
        
        # No procesar si ya está completado
        if prestamo.estado == Prestamo.EstadoPrestamo.COMPLETADO:
            messages.warning(request, "Este préstamo ya ha sido completado.")
            return redirect('gestion_inventario:ruta_gestionar_devolucion', prestamo_id=prestamo.id)

        items_prestados = prestamo.items_prestados.select_related('activo', 'lote').all()
        
        try:
            # Obtenemos los estados que necesitaremos para la lógica
            estado_disponible = Estado.objects.get(nombre='DISPONIBLE')
            estado_prestamo = Estado.objects.get(nombre='EN PRÉSTAMO EXTERNO')
        except Estado.DoesNotExist as e:
            messages.error(request, f"Error de configuración: No se encontró el estado '{e}'. Contacte al administrador.")
            return redirect('gestion_inventario:ruta_gestionar_devolucion', prestamo_id=prestamo.id)

        items_procesados_con_exito = 0
        errores_validacion = False

        detalles_a_actualizar = []
        movimientos_a_crear = []
        stock_a_actualizar = [] # Guardamos (item, tipo_item)

        # 1. Fase de Validación
        for detalle in items_prestados:
            cantidad_pendiente = detalle.cantidad_prestada - detalle.cantidad_devuelta
            if cantidad_pendiente <= 0:
                continue

            try:
                if detalle.activo:
                    # Para Activos, es un checkbox (valor '1' si se marca)
                    input_name = f'cantidad-devolver-{detalle.id}'
                    cantidad_a_devolver = int(request.POST.get(input_name, 0))
                else:
                    # Para Lotes, es un campo numérico
                    input_name = f'cantidad-devolver-{detalle.id}'
                    cantidad_a_devolver = int(request.POST.get(input_name, 0))
            
            except (ValueError, TypeError):
                messages.error(request, f"Se recibió un valor inválido para el ítem {detalle.codigo_item}.")
                errores_validacion = True
                continue # Saltar al siguiente ítem

            if cantidad_a_devolver < 0:
                messages.error(request, f"La cantidad a devolver no puede ser negativa ({detalle.codigo_item}).")
                errores_validacion = True
            elif cantidad_a_devolver > cantidad_pendiente:
                messages.error(request, f"No puede devolver {cantidad_a_devolver} para el ítem {detalle.codigo_item}. Máximo pendiente: {cantidad_pendiente}.")
                errores_validacion = True
            
            if cantidad_a_devolver > 0 and not errores_validacion:
                detalles_a_actualizar.append((detalle, cantidad_a_devolver))

        if errores_validacion:
            # Si hubo algún error, no procesamos nada
            return redirect('gestion_inventario:ruta_gestionar_devolucion', prestamo_id=prestamo.id)
        
        if not detalles_a_actualizar:
            messages.warning(request, "No se ingresaron cantidades para devolver.")
            return redirect('gestion_inventario:ruta_gestionar_devolucion', prestamo_id=prestamo.id)

        # 2. Fase de Procesamiento (dentro del @transaction.atomic)
        total_items_completados = 0
        for detalle in items_prestados:
            if (detalle.cantidad_prestada - detalle.cantidad_devuelta) == 0:
                total_items_completados += 1

        for detalle, cantidad_devuelta in detalles_a_actualizar:
            # 1. Actualizar el detalle del préstamo
            detalle.cantidad_devuelta += cantidad_devuelta
            
            # 2. Actualizar Stock
            if detalle.activo:
                activo = detalle.activo
                activo.estado = estado_disponible
                stock_a_actualizar.append(activo)
                
                movimiento = MovimientoInventario(
                    tipo_movimiento=TipoMovimiento.DEVOLUCION,
                    fecha_hora=timezone.now(),
                    usuario=request.user,
                    estacion=estacion,
                    activo=activo,
                    cantidad_movida=1, # Siempre 1 para activos
                    compartimento_destino=activo.compartimento, # Vuelve a su "hogar"
                    notas=f"Devolución Préstamo Folio #{prestamo.id}"
                )
                movimientos_a_crear.append(movimiento)

            elif detalle.lote:
                lote = detalle.lote
                lote.cantidad += cantidad_devuelta # Añadimos el stock de vuelta al lote original
                stock_a_actualizar.append(lote)

                movimiento = MovimientoInventario(
                    tipo_movimiento=TipoMovimiento.DEVOLUCION,
                    fecha_hora=timezone.now(),
                    usuario=request.user,
                    estacion=estacion,
                    lote_insumo=lote,
                    cantidad_movida=cantidad_devuelta, # Positivo
                    compartimento_destino=lote.compartimento, # Vuelve a su lote "hogar"
                    notas=f"Devolución Préstamo Folio #{prestamo.id}"
                )
                movimientos_a_crear.append(movimiento)
            
            if detalle.cantidad_devuelta == detalle.cantidad_prestada:
                total_items_completados += 1
            
            detalle.save()
            items_procesados_con_exito += 1

        # 3. Actualizar Estado del Préstamo
        if total_items_completados == items_prestados.count():
            prestamo.estado = Prestamo.EstadoPrestamo.COMPLETADO
        elif items_procesados_con_exito > 0:
            prestamo.estado = Prestamo.EstadoPrestamo.DEVUELTO_PARCIAL
        
        prestamo.save()

        # 4. Guardar cambios de stock y movimientos (Bulk)
        # (Nota: bulk_update es más eficiente si ya existían, pero save() es más simple y activa signals)
        for item in stock_a_actualizar:
            item.save()
        
        MovimientoInventario.objects.bulk_create(movimientos_a_crear)

        messages.success(request, f"Se registraron {items_procesados_con_exito} devoluciones correctamente.")
        return redirect('gestion_inventario:ruta_gestionar_devolucion', prestamo_id=prestamo.id)




class DestinatarioListView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Lista todos los destinatarios (para préstamos) de la estación activa.
    Obtiene la estación desde la sesión.
    """
    template_name = 'gestion_inventario/pages/lista_destinatarios.html'
    paginate_by = 25
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_prestamos"

    def get(self, request, *args, **kwargs):
        # --- CORRECCIÓN ---
        # Obtener la estación activa desde la SESIÓN
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Error: No se ha seleccionado una estación activa.")
            return redirect('portal:ruta_inicio')
        # Filtra por la estación de la sesión
        base_queryset = Destinatario.objects.filter(estacion_id=estacion_id).order_by('nombre_entidad')
        # --- FIN CORRECCIÓN ---

        filter_form = DestinatarioFilterForm(request.GET)

        if filter_form.is_valid():
            q = filter_form.cleaned_data.get('q')
            if q:
                base_queryset = base_queryset.filter(
                    Q(nombre_entidad__icontains=q) |
                    Q(rut_entidad__icontains=q) |
                    Q(nombre_contacto__icontains=q)
                )

        # Paginación
        paginator = Paginator(base_queryset, self.paginate_by)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'is_paginated': paginator.num_pages > 1,
            'filter_form': filter_form,
            'params': request.GET.urlencode()
        }
        return render(request, self.template_name, context)




class DestinatarioCreateView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Crea un nuevo destinatario.
    Asigna la estación activa desde la SESIÓN.
    """
    template_name = 'gestion_inventario/pages/form_destinatario.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_prestamos"

    def get(self, request, *args, **kwargs):
        form = DestinatarioForm()
        context = {
            'form': form,
            'titulo': 'Crear Nuevo Destinatario'
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # --- CORRECCIÓN ---
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Acción no permitida. No hay estación activa.")
            return redirect('portal:ruta_inicio')
        # --- FIN CORRECCIÓN ---
        
        form = DestinatarioForm(request.POST)
        if form.is_valid():
            try:
                destinatario = form.save(commit=False)
                # --- CORRECCIÓN ---
                # Asigna el ID de la estación desde la sesión
                destinatario.estacion_id = estacion_id
                # --- FIN CORRECCIÓN ---
                destinatario.creado_por = request.user
                destinatario.save()
                messages.success(request, f"Destinatario '{destinatario.nombre_entidad}' creado con éxito.")
                return redirect('gestion_inventario:ruta_lista_destinatarios')
            except IntegrityError:
                messages.error(request, f"Ya existe un destinatario con el nombre '{form.cleaned_data['nombre_entidad']}' en esta estación.")
                form.add_error('nombre_entidad', 'Este nombre ya está en uso.')
        
        context = {
            'form': form,
            'titulo': 'Crear Nuevo Destinatario'
        }
        return render(request, self.template_name, context)




class DestinatarioEditView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Edita un destinatario existente.
    Verifica la pertenencia usando la estación de la SESIÓN.
    """
    template_name = 'gestion_inventario/pages/form_destinatario.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_prestamos"
    model = Destinatario

    def get(self, request, *args, **kwargs):
        # --- CORRECCIÓN ---
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Acción no permitida.")
            return redirect('portal:ruta_inicio')
        
        destinatario_id = kwargs.get('destinatario_id')
        # get_object_or_404 asegura que solo editen los de su estación (usando el ID de sesión)
        destinatario = get_object_or_404(Destinatario, id=destinatario_id, estacion_id=estacion_id)
        # --- FIN CORRECCIÓN ---
        
        form = DestinatarioForm(instance=destinatario)
        context = {
            'form': form,
            'titulo': f"Editar Destinatario: {destinatario.nombre_entidad}",
            'destinatario': destinatario
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # --- CORRECCIÓN ---
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Acción no permitida.")
            return redirect('portal:home')
        
        destinatario_id = kwargs.get('destinatario_id')
        # V-lida de nuevo en el POST por seguridad
        destinatario = get_object_or_404(Destinatario, id=destinatario_id, estacion_id=estacion_id)
        # --- FIN CORRECCIÓN ---
        
        form = DestinatarioForm(request.POST, instance=destinatario)
        
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"Destinatario '{destinatario.nombre_entidad}' actualizado con éxito.")
                return redirect('gestion_inventario:ruta_lista_destinatarios')
            except IntegrityError:
                messages.error(request, f"Ya existe otro destinatario con el nombre '{form.cleaned_data['nombre_entidad']}'.")
                form.add_error('nombre_entidad', 'Este nombre ya está en uso.')
        
        context = {
            'form': form,
            'titulo': f"Editar Destinatario: {destinatario.nombre_entidad}",
            'destinatario': destinatario
        }
        return render(request, self.template_name, context)




class MovimientoInventarioListView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Muestra una lista paginada y filtrable de todos los 
    movimientos de inventario de la estación activa.
    """
    template_name = 'gestion_inventario/pages/historial_movimientos.html'
    login_url = '/acceso/login/'
    paginate_by = 50 # 50 movimientos por página
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_historial_movimientos"

    def get(self, request):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        try:
            estacion = Estacion.objects.get(id=estacion_id)
        except Estacion.DoesNotExist:
            messages.error(request, "Estación activa no encontrada.")
            return redirect('gestion_inventario:ruta_inicio')

        # Consulta base (optimizada con select_related)
        movimientos_list = MovimientoInventario.objects.filter(
            estacion=estacion
        ).select_related(
            'usuario', 
            'proveedor_origen', 
            'compartimento_origen__ubicacion', 
            'compartimento_destino__ubicacion', 
            'activo__producto__producto_global', 
            'lote_insumo__producto__producto_global'
        ).order_by('-fecha_hora') # El 'ordering' de tu Meta

        # Inicializar formulario de filtros (pasamos la estación)
        filter_form = MovimientoFilterForm(request.GET, estacion=estacion)
        
        # Aplicar filtros si el formulario es válido (o si hay datos GET)
        if request.GET:
            # Filtro de Búsqueda (q)
            q = request.GET.get('q')
            if q:
                movimientos_list = movimientos_list.filter(
                    Q(activo__producto__producto_global__nombre_oficial__icontains=q) |
                    Q(lote_insumo__producto__producto_global__nombre_oficial__icontains=q) |
                    Q(activo__codigo_activo__icontains=q) |
                    Q(lote_insumo__codigo_lote__icontains=q) |
                    Q(notas__icontains=q)
                ).distinct()

            # Filtro por Tipo de Movimiento
            tipo = request.GET.get('tipo_movimiento')
            if tipo:
                movimientos_list = movimientos_list.filter(tipo_movimiento=tipo)

            # Filtro por Usuario
            usuario_id = request.GET.get('usuario')
            if usuario_id:
                movimientos_list = movimientos_list.filter(usuario_id=usuario_id)

            # Filtro por Fecha
            fecha_inicio = request.GET.get('fecha_inicio')
            if fecha_inicio:
                movimientos_list = movimientos_list.filter(fecha_hora__gte=fecha_inicio)
            
            fecha_fin = request.GET.get('fecha_fin')
            if fecha_fin:
                movimientos_list = movimientos_list.filter(fecha_hora__lte=fecha_fin)

        # Paginación
        paginator = Paginator(movimientos_list, self.paginate_by)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'filter_form': filter_form,
            'movimientos': page_obj,
            'page_obj': page_obj, # Para la plantilla de paginación
        }
        return render(request, self.template_name, context)




class GenerarQRView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Esta vista no renderiza HTML.
    Genera una imagen QR basada en el 'codigo' proporcionado
    y la devuelve como una respuesta de imagen PNG.
    """

    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_stock"
    
    def get(self, request, *args, **kwargs):
        # 1. Obtenemos el código de la URL
        codigo = kwargs.get('codigo')
        if not codigo:
            # Si no hay código, devolvemos un error
            return HttpResponse("Código no proporcionado.", status=400)

        # 2. Configurar y generar el QR en memoria
        qr = qrcode.QRCode(
            version=1, # Tamaño simple
            error_correction=qrcode.constants.ERROR_CORRECT_L, # Nivel de corrección bajo (QR más simple)
            box_size=10, # Tamaño de cada "pixel" del QR
            border=4,  # Borde blanco
        )
        
        # 3. Añadir el dato (el ID, ej: "E1-ACT-00123")
        qr.add_data(codigo)
        qr.make(fit=True)

        # 4. Crear la imagen PNG
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 5. Guardar la imagen en un buffer de memoria (un "archivo falso")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        
        # 6. Devolver la imagen como una respuesta HTTP
        # Limpiamos el buffer y devolvemos su contenido
        buffer.seek(0)
        return HttpResponse(buffer.getvalue(), content_type="image/png")




class ImprimirEtiquetasView(LoginRequiredMixin, ModuleAccessMixin, PermissionRequiredMixin, View):
    """
    Muestra una página diseñada para imprimir etiquetas QR
    para Activos y Lotes.
    
    Maneja dos modos:
    1. Específico: Recibe IDs por GET (ej: ?activos=1,2&lotes=3)
    2. Masivo: Muestra filtros para seleccionar qué imprimir
    """
    template_name = 'gestion_inventario/pages/imprimir_etiquetas.html'
    login_url = '/acceso/login/'
    permission_required = "gestion_usuarios.accion_gestion_inventario_imprimir_etiquetas_qr"

    def get_context_data(self, request, estacion_id):
        """Prepara el contexto de la vista (filtros y querysets)"""
        
        # --- Obtener IDs de la URL (Modo Específico) ---
        activos_ids_str = request.GET.get('activos')
        lotes_ids_str = request.GET.get('lotes')
        
        impresion_directa = bool(activos_ids_str or lotes_ids_str)
        
        activos_queryset = Activo.objects.none()
        lotes_queryset = LoteInsumo.objects.none()
        
        if impresion_directa:
            # MODO 1: IMPRESIÓN ESPECÍFICA (Post-Recepción o Individual)
            activos_ids = []
            if activos_ids_str:
                activos_ids = [int(id) for id in activos_ids_str.split(',') if id.isdigit()]
            
            lotes_ids = []
            if lotes_ids_str:
                lotes_ids = [int(id) for id in lotes_ids_str.split(',') if id.isdigit()]

            activos_queryset = Activo.objects.filter(
                estacion_id=estacion_id,
                id__in=activos_ids
            )
            lotes_queryset = LoteInsumo.objects.filter(
                compartimento__ubicacion__estacion_id=estacion_id,
                id__in=lotes_ids
            )
            
            filter_form = None

        else:
            # MODO 2: IMPRESIÓN MASIVA (Con Filtros)
            estacion_obj = Estacion.objects.get(id=estacion_id)
            filter_form = EtiquetaFilterForm(request.GET, estacion=estacion_obj)
            
            # Query base (solo ítems operativos)
            activos_queryset = Activo.objects.filter(
                estacion_id=estacion_id
            ).exclude(estado__nombre__in=['ANULADO POR ERROR', 'DE BAJA', 'EXTRAVIADO'])
            
            lotes_queryset = LoteInsumo.objects.filter(
                compartimento__ubicacion__estacion_id=estacion_id,
                cantidad__gt=0 # Solo lotes con stock
            ).exclude(estado__nombre__in=['ANULADO POR ERROR', 'DE BAJA', 'EXTRAVIADO'])

            # Aplicar filtros
            if filter_form.is_valid():
                ubicacion = filter_form.cleaned_data.get('ubicacion')
                if ubicacion:
                    activos_queryset = activos_queryset.filter(compartimento__ubicacion=ubicacion)
                    lotes_queryset = lotes_queryset.filter(compartimento__ubicacion=ubicacion)

        # Optimizar querysets
        activos_queryset = activos_queryset.select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).order_by('codigo_activo')
        
        lotes_queryset = lotes_queryset.select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).order_by('codigo_lote')
        
        return {
            'activos': activos_queryset,
            'lotes': lotes_queryset,
            'filter_form': filter_form,
            'impresion_directa': impresion_directa,
            'total_items': len(activos_queryset) + len(lotes_queryset)
        }

    def get(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Estación no seleccionada.")
            return redirect('gestion_inventario:ruta_inicio')
        
        context = self.get_context_data(request, estacion_id)
        return render(request, self.template_name, context)