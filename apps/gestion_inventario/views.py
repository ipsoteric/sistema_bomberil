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
from django.views.generic import TemplateView, DeleteView, UpdateView, ListView, DetailView, CreateView, FormView
from django.views.generic.detail import SingleObjectMixin
from django.http import HttpResponseRedirect, Http404, HttpResponseBadRequest, FileResponse
from django.db import models
from django.db.models import Count, Sum, Q, Subquery, OuterRef, ProtectedError, Value, Case, When, CharField, F, Max
from django.db.models.functions import Coalesce
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models.functions import Coalesce
from dateutil.relativedelta import relativedelta
from django.db.models.functions import Coalesce, Abs
from django.utils.functional import cached_property

from core.settings import (
    INVENTARIO_UBICACION_AREA_NOMBRE as AREA_NOMBRE, 
    INVENTARIO_UBICACION_VEHICULO_NOMBRE as VEHICULO_NOMBRE, 
)

from apps.common.mixins import BaseEstacionMixin, AuditoriaMixin, CustomPermissionRequiredMixin
from .mixins import UbicacionMixin, InventoryStateValidatorMixin, StationInventoryObjectMixin
from .utils import get_or_create_anulado_compartment, get_or_create_extraviado_compartment
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
    TipoMovimiento,
    RegistroUsoActivo
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
    RegistroUsoForm,
    TransferenciaForm,
    PrestamoCabeceraForm,
    PrestamoDetalleFormSet,
    PrestamoFilterForm,
    DestinatarioFilterForm,
    DestinatarioForm,
    EtiquetaFilterForm
    )
from apps.gestion_mantenimiento.models import PlanActivoConfig, OrdenMantenimiento, RegistroMantenimiento


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
        # A) ACTIVOS: Usamos Count (1 registro = 1 unidad)
        kpis_activos = activos_qs.aggregate(
            operativos=Count('id', filter=Q(estado__tipo_estado__nombre='OPERATIVO')),
            no_operativos=Count('id', filter=Q(estado__tipo_estado__nombre='NO OPERATIVO')),
            prestamo=Count('id', filter=Q(estado__nombre='EN PRÉSTAMO EXTERNO')),
            vencen=Count('id', filter=Q(fecha_expiracion__range=[hoy, fecha_limite_vencimiento]) | Q(fin_vida_util_calculada__range=[hoy, fecha_limite_vencimiento]))
        )

        # B) LOTES: Usamos Sum('cantidad') y Coalesce para evitar None
        kpis_lotes = lotes_qs.aggregate(
            operativos=Coalesce(Sum('cantidad', filter=Q(estado__tipo_estado__nombre='OPERATIVO')), 0),
            no_operativos=Coalesce(Sum('cantidad', filter=Q(estado__tipo_estado__nombre='NO OPERATIVO')), 0),
            prestamo=Coalesce(Sum('cantidad', filter=Q(estado__nombre='EN PRÉSTAMO EXTERNO')), 0),
            vencen=Coalesce(Sum('cantidad', filter=Q(fecha_expiracion__range=[hoy, fecha_limite_vencimiento])), 0)
        )

        # KPI: Stock Bajo
        # Obtenemos TODOS los productos de la estación que tengan configuración de stock crítico (> 0)
        # Y realizamos el cálculo en una sola consulta potente.
        productos_en_alerta = Producto.objects.filter(
            estacion_id=self.estacion_activa_id,
            stock_critico__gt=0 # Solo los que tienen la regla activada
        ).annotate(
            # 1. Contar Activos Operativos (Serializados)
            cant_activos=Count(
                'activo', 
                filter=Q(activo__estado__tipo_estado__nombre='OPERATIVO')
            ),
            
            # 2. Sumar Lotes Operativos (Insumos) - Usamos Coalesce para evitar None
            cant_lotes=Coalesce(
                Sum('loteinsumo__cantidad', 
                    filter=Q(loteinsumo__estado__tipo_estado__nombre='OPERATIVO')
                ), 
                0
            )
        ).annotate(
            # 3. Sumar ambos mundos (Un producto es activo O lote, el otro será 0, la suma funciona)
            stock_actual=F('cant_activos') + F('cant_lotes')
        ).filter(
            # 4. El Filtro Final: ¿Es el actual menor o igual al crítico?
            stock_actual__lte=F('stock_critico')
        ).select_related('producto_global')

        # Inyectamos la lista y el conteo
        context['alerta_stock_critico_lista'] = productos_en_alerta[:5] # Top 5 para el widget
        context['kpi_stock_critico_count'] = productos_en_alerta.count() # Número total para el badge rojo

        # 3. Suma de Totales (Ahora sí sumará 4 + 40)
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




class AreaListaView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
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




class AreaCrearView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
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
        try:
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

            # --- AUDITORÍA ---
            self.auditar(
                verbo="creó el almacén/área",
                objetivo=ubicacion,
                objetivo_repr=ubicacion.nombre,
                detalles={'nombre': ubicacion.nombre}
            )
            # Enviar mensaje de éxito
            messages.success(self.request, f'Almacén/ubicación "{ubicacion.nombre.title()}" creado exitosamente.')
            return redirect(self.get_success_url(ubicacion.id))
        
        except Exception as e:
            messages.error(self.request, f"Error crítico al crear el almacén: {str(e)}")
            return self.form_invalid(form)
    

    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error al crear el almacén. Por favor revisa los datos.") # <--- AGREGAR
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)




class UbicacionDetalleView(BaseEstacionMixin, CustomPermissionRequiredMixin, UbicacionMixin, View):
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




class UbicacionDeleteView(BaseEstacionMixin, CustomPermissionRequiredMixin, UbicacionMixin, AuditoriaMixin, View):
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
            with transaction.atomic():
                # 1. Obtener todos los compartimentos de esta ubicación
                compartimentos = ubicacion.compartimento_set.all()

                # 2. VALIDACIÓN DE EXISTENCIAS (Inventario Físico)
                # Debemos asegurar que NO haya stock físico antes de borrar nada.
                tiene_cosas = False
                for comp in compartimentos:
                    # Verificamos si hay Activos (serializados) o Lotes (fungibles) [cite: 32]
                    if hasattr(comp, 'activo_set') and comp.activo_set.exists():
                        tiene_cosas = True
                        break
                    if hasattr(comp, 'loteinsumo_set') and comp.loteinsumo_set.exists():
                        tiene_cosas = True
                        break
                
                if tiene_cosas:
                    messages.error(request, f"No se puede eliminar '{ubicacion_nombre}' porque contiene existencias físicas en sus compartimentos. Mueva o dé de baja los ítems primero.")
                    return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion.id)

                # 3. GESTIÓN DEL COMPARTIMENTO "GENERAL"
                # Filtramos compartimentos que NO sean 'General' (case insensitive)
                compartimentos_usuario = compartimentos.exclude(nombre__iexact="General")

                if compartimentos_usuario.exists():
                    # Si hay compartimentos creados por el usuario (ej: "Estante 1"), 
                    # forzamos a que el usuario los borre manualmente por seguridad.
                    messages.error(request, f"La ubicación tiene compartimentos personalizados (distintos a 'General'). Elimínelos primero.")
                    return redirect(self.redirect_url, ubicacion_id=ubicacion.id)
                
                # 4. LIMPIEZA AUTOMÁTICA
                # Si llegamos aquí, sabemos que:
                # a) No hay stock físico.
                # b) No hay compartimentos de usuario.
                # c) Solo queda el compartimento "General" (o ninguno).
                
                # Borramos 'General' si existe para liberar el ProtectedError
                compartimentos.filter(nombre__iexact="General").delete()


                # 5. ELIMINACIÓN FINAL DE LA UBICACIÓN
                ubicacion.delete()

                # --- AUDITORÍA ---
                # Pasamos 'objetivo=None' porque ya no existe en BD, 
                # pero usamos 'detalles' para persistir el nombre.
                self.auditar(
                    verbo=f"eliminó permanentemente el/la {tipo_nombre.lower()}",
                    objetivo=None, 
                    objetivo_repr=ubicacion_nombre,
                    detalles={'nombre_rol_eliminado': ubicacion_nombre}
                )

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
            return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion.id)
        
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")
            return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion.id)




class AreaEditarView(BaseEstacionMixin, CustomPermissionRequiredMixin, UbicacionMixin, AuditoriaMixin, View):
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
        try:
            self.object = form.save()

            self.auditar(
                    verbo="modificó la información del almacén",
                    objetivo=self.object,
                    objetivo_repr=self.object.nombre,
                    detalles={'campos_modificados': form.changed_data}
                )

            messages.success(self.request, 'Almacén actualizado correctamente.')
            return redirect(self.get_success_url())
        
        except Exception as e:
            messages.error(self.request, f"Error al actualizar el almacén: {str(e)}")
            return self.form_invalid(form)


    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error al actualizar el almacén. Revisa los campos.")
        context = self.get_context_data(form=form)
        return render(self.request, self.template_name, context)




class VehiculoListaView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
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




class VehiculoCrearView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
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

                # --- AUDITORÍA ---
                self.auditar(
                    verbo="creó el vehículo",
                    objetivo=ubicacion_obj,
                    objetivo_repr=ubicacion_obj.nombre,
                    detalles={'nombre': ubicacion_obj.nombre}
                )
            
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




class VehiculoEditarView(BaseEstacionMixin, CustomPermissionRequiredMixin, UbicacionMixin, AuditoriaMixin, View):
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
                ubicacion_obj = form_ubicacion.save()
                
                # Guardamos el formulario de Detalles (sin commit)
                detalles_obj = form_detalles.save(commit=False)
                # Asignamos la relación OneToOne a la Ubicacion (self.object)
                detalles_obj.ubicacion = self.object 
                detalles_obj.save()

                # --- AUDITORÍA ---
                self.auditar(
                    verbo="modificó la información del vehículo",
                    objetivo=ubicacion_obj,
                    objetivo_repr=ubicacion_obj.nombre,
                    detalles={'nombre': ubicacion_obj.nombre}
                )
            
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




class CompartimentoListaView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
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
        ).exclude(
            # EXCLUSIÓN CLAVE: Quitamos los compartimentos "limbo"
            ubicacion__tipo_ubicacion__nombre='ADMINISTRATIVA'
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
        ).exclude(
            tipo_ubicacion__nombre='ADMINISTRATIVA'
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




class CompartimentoCrearView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, CreateView):
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
        try:
            form.instance.ubicacion = self.ubicacion
            # Guardamos manualmente para controlar la excepción
            self.object = form.save()
    
            # --- AUDITORÍA ---
            self.auditar(
                verbo="creó el compartimento",
                objetivo=form.instance,
                objetivo_repr=form.instance.nombre,
                detalles={'nombre': form.instance.nombre}
            )
            messages.success(
                self.request, 
                f'Compartimento "{self.object.nombre}" creado exitosamente en {self.ubicacion.nombre}.'
            )
            return redirect(self.get_success_url())
        
        except Exception as e:
            messages.error(self.request, f"Error al crear el compartimento: {str(e)}")
            return self.form_invalid(form)
    

    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error en el formulario. Por favor, revisa los datos ingresados.")
        return super().form_invalid(form)


    def get_success_url(self):
        """
        Override: Redirige a la gestión de la ubicación padre.
        """
        return reverse('gestion_inventario:ruta_gestionar_ubicacion', kwargs={'ubicacion_id': self.ubicacion.id})




class CompartimentoDetalleView(BaseEstacionMixin, CustomPermissionRequiredMixin, DetailView):
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




class CompartimentoEditView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, UpdateView):
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
        try:
            self.object = form.save()
            # --- AUDITORÍA ---
            self.auditar(
                verbo="modificó la información del compartimento",
                objetivo=self.object,
                objetivo_repr=self.object.nombre,
                detalles={'nombre': self.object.nombre}
            )
            messages.success(self.request, f"El compartimento '{self.object.nombre}' se actualizó correctamente.")
            return redirect(self.get_success_url())
        
        except Exception as e:
            messages.error(self.request, f"Error al guardar cambios: {str(e)}")
            return self.form_invalid(form)


    def form_invalid(self, form):
        """
        Override: Hook para ejecutar lógica extra cuando el formulario falla.
        """
        messages.error(self.request, "Hubo un error al actualizar el compartimento. Por favor, revisa los campos.")
        return super().form_invalid(form)




class CompartimentoDeleteView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, DeleteView):
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
            nombre_compartimento = self.object.nombre
            # El método delete() de Model retorna una tupla, no lo necesitamos aquí
            self.object.delete()

            # --- AUDITORÍA ---
            # Pasamos 'objetivo=None' porque ya no existe en BD, 
            # pero usamos 'detalles' para persistir el nombre.
            self.auditar(
                verbo="eliminó permanentemente el compartimento",
                objetivo=None, 
                objetivo_repr=nombre_compartimento,
                detalles={'nombre_rol_eliminado': nombre_compartimento}
            )
            
            messages.success(self.request, f"El compartimento '{nombre_compartimento}' ha sido eliminado exitosamente.")
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




class CatalogoGlobalListView(BaseEstacionMixin, CustomPermissionRequiredMixin, ListView):
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




class ProductoGlobalCrearView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, CreateView):
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
                # --- AUDITORÍA ---
                self.auditar(
                    verbo="creó la marca",
                    objetivo=marca_obj,
                    objetivo_repr=marca_obj.nombre,
                )
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
        # 1. Ejecutamos super().form_valid(form) primero.
        # Esto guarda el objeto en la BD y asigna self.object
        response = super().form_valid(form)
        # --- AUDITORÍA ---
        self.auditar(
            verbo="registró el producto global",
            objetivo=self.object,
            objetivo_repr=self.object.nombre_oficial,
            detalles={
                'marca': str(self.object.marca),
                'categoria': str(self.object.categoria),
                'modelo': self.object.modelo
            }
        )
        messages.success(self.request, f'Producto Global "{self.object.nombre_oficial}" creado exitosamente.')
        return response
    

    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error al crear el producto global. Revisa los datos ingresados.")
        return super().form_invalid(form)



class ProductoLocalListView(BaseEstacionMixin, CustomPermissionRequiredMixin, ListView):
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




class ProductoLocalEditView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, UpdateView):
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

                # --- AUDITORÍA ---
                self.auditar(
                    verbo="modificó la información del producto",
                    objetivo=self.object,
                    objetivo_repr=self.object.producto_global.nombre_oficial,
                    detalles={'nombre': self.object.producto_global.nombre_oficial}
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
        
    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error en el formulario. Por favor, revisa los datos ingresados.")
        return super().form_invalid(form)




class ProductoLocalDetalleView(BaseEstacionMixin, CustomPermissionRequiredMixin, DetailView):
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




class ProveedorListView(BaseEstacionMixin, CustomPermissionRequiredMixin, ListView):
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




class ProveedorCrearView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
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

                # --- AUDITORÍA ---
                self.auditar(
                    verbo="registró al proveedor",
                    objetivo=proveedor,
                    objetivo_repr=proveedor.nombre,
                    detalles={
                        'rut': proveedor.rut,
                        'contacto_inicial': contacto.nombre_contacto
                    }
                )

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
        messages.error(self.request, "Hubo un error al registrar el proveedor. Por favor, revisa los campos marcados en rojo.")

        context = {
            'proveedor_form': proveedor_form,
            'contacto_form': contacto_form
        }
        return render(self.request, self.template_name, context)




class ProveedorDetalleView(BaseEstacionMixin, CustomPermissionRequiredMixin, DetailView):
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




class ContactoPersonalizadoCrearView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, CreateView):
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

            # --- AUDITORÍA ---
            self.auditar(
                verbo="agregó un contacto personalizado para el proveedor",
                objetivo=self.proveedor,
                objetivo_repr=self.proveedor.nombre,
                detalles={
                    'nombre_contacto_nuevo': self.object.nombre_contacto,
                    'telefono': self.object.telefono
                }
            )

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
        
    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error en el formulario. Por favor, revisa los datos ingresados.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('gestion_inventario:ruta_detalle_proveedor', kwargs={'pk': self.proveedor.pk})




class ContactoPersonalizadoEditarView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, UpdateView):
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
        try:
            self.object = form.save()
            # --- AUDITORÍA ---
            if form.changed_data:
                self.auditar(
                    verbo="actualizó el contacto personalizado del proveedor",
                    objetivo=self.object.proveedor,
                    detalles={
                        'nombre_contacto': self.object.nombre_contacto,
                        'campos_modificados': form.changed_data
                    }
                )
            messages.success(
                self.request, 
                f'Se ha actualizado el contacto "{self.object.nombre_contacto}".'
            )
            # Nota: Usamos redirect explícito en lugar de super().form_valid() para controlar el flujo
            # aunque super().form_valid() también redirige, aquí ya guardamos manualmente arriba.
            return redirect(self.get_success_url())
        
        except Exception as e:
            messages.error(self.request, f"Error al actualizar el contacto: {str(e)}")
            return self.form_invalid(form)


    def get_success_url(self):
        return reverse('gestion_inventario:ruta_detalle_proveedor', kwargs={'pk': self.object.proveedor_id})




class StockActualListView(BaseEstacionMixin, CustomPermissionRequiredMixin, TemplateView):
    """
    Vista unificada del stock actual (Activos + Lotes).
    Utiliza TemplateView como orquestador, delegando la complejidad
    de consultas híbridas, filtrado y ordenamiento en memoria a métodos especializados.
    """
    template_name = 'gestion_inventario/pages/stock_actual.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_stock"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Captura de parámetros (limpieza)
        params = self.request.GET
        self.query = params.get('q', '')
        self.tipo_producto = params.get('tipo', '')
        self.ubicacion_id = params.get('ubicacion', '')
        self.estado_id = params.get('estado', '')
        self.fecha_desde = params.get('fecha_desde', '')
        self.fecha_hasta = params.get('fecha_hasta', '')
        self.mostrar_anulados = params.get('mostrar_anulados') == 'on'
        self.sort_by = params.get('sort', 'fecha_desc')

        # 2. Configuración de fechas para annotations
        today = timezone.now().date()
        warning_date = today + datetime.timedelta(days=90)
        
        self.vencimiento_annotation = Case(
            When(vencimiento_final__isnull=True, then=Value('no_aplica')),
            When(vencimiento_final__lt=today, then=Value('vencido')),
            When(vencimiento_final__lt=warning_date, then=Value('proximo')),
            default=Value('ok'),
            output_field=CharField()
        )

        # 3. Obtención de QuerySets
        activos_qs = self._get_activos_queryset()
        lotes_qs = self._get_lotes_queryset()

        # 4. Combinación y Ordenamiento (Strategy)
        stock_list = self._combinar_y_ordenar(activos_qs, lotes_qs)

        # 5. Paginación Manual (Necesaria porque es una lista, no un queryset)
        paginator = Paginator(stock_list, self.paginate_by)
        page_number = params.get('page')
        
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        # 6. Contexto Final
        context.update({
            'page_obj': page_obj,
            'stock_items': page_obj.object_list,
            'todas_las_ubicaciones': Ubicacion.objects.filter(estacion=self.estacion_activa),
            'todos_los_estados': Estado.objects.all(),
            # Mantener estado de filtros en UI
            'current_q': self.query,
            'current_tipo': self.tipo_producto,
            'current_ubicacion': self.ubicacion_id,
            'current_estado': self.estado_id,
            'current_fecha_desde': self.fecha_desde,
            'current_fecha_hasta': self.fecha_hasta,
            'current_mostrar_anulados': self.mostrar_anulados,
            'current_sort': self.sort_by,
        })
        return context


    def _get_activos_queryset(self):
        """Construye y filtra el queryset de Activos."""
        if self.tipo_producto == 'insumo':
            return Activo.objects.none()

        qs = Activo.objects.filter(estacion=self.estacion_activa).select_related(
            'producto__producto_global', 'compartimento__ubicacion', 'estado'
        ).annotate(
            vencimiento_final=Coalesce('fecha_expiracion', 'fin_vida_util_calculada'),
            estado_vencimiento=self.vencimiento_annotation
        )

        if not self.mostrar_anulados:
            qs = qs.exclude(estado__nombre='ANULADO POR ERROR')

        # Filtro específico de Activos (búsqueda)
        if self.query:
            qs = qs.filter(
                self._get_base_search_q() | 
                Q(codigo_activo__icontains=self.query) | 
                Q(numero_serie_fabricante__icontains=self.query)
            )
        
        # Filtro específico de Activos (Estado)
        if self.estado_id:
            qs = qs.filter(estado__id=self.estado_id)

        return self._aplicar_filtros_comunes(qs)


    def _get_lotes_queryset(self):
        """Construye y filtra el queryset de Lotes."""
        if self.tipo_producto == 'activo':
            return LoteInsumo.objects.none()
            
        # Si hay filtro de estado específico (que no sea operativo/disponible), 
        # los lotes suelen filtrarse diferente o excluirse si no aplica.
        # Asumiremos la lógica original: si hay estado_id y no es activo, lotes vacíos
        if self.estado_id and self.tipo_producto != 'activo':
             # Aquí mantengo tu lógica original: el filtro de estado parecía solo para activos
             # Si quisieras filtrar lotes por estado, lo añadirías aquí.
             # Por ahora, retornamos vacío para ser fiel a tu código previo si hay estado_id
             return LoteInsumo.objects.none()

        qs = LoteInsumo.objects.filter(producto__estacion=self.estacion_activa).select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).annotate(
            # Alias para unificar nombre de campo con Activo
            vencimiento_final=F('fecha_expiracion'), 
            estado_vencimiento=Case(
                When(fecha_expiracion__isnull=True, then=Value('no_aplica')),
                When(fecha_expiracion__lt=timezone.now().date(), then=Value('vencido')),
                # ... repetimos lógica o la ajustamos si es idéntica
                default=Value('ok'),
                output_field=CharField()
            )
        )

        if not self.mostrar_anulados:
            qs = qs.exclude(estado__nombre='ANULADO POR ERROR')

        if self.query:
            qs = qs.filter(
                self._get_base_search_q() | 
                Q(numero_lote_fabricante__icontains=self.query)
            )

        return self._aplicar_filtros_comunes(qs)


    def _get_base_search_q(self):
        """Retorna el objeto Q base para búsqueda en ProductoGlobal (común)."""
        return (
            Q(producto__producto_global__nombre_oficial__icontains=self.query) |
            Q(producto__sku__icontains=self.query) |
            Q(producto__producto_global__marca__nombre__icontains=self.query) |
            Q(producto__producto_global__modelo__icontains=self.query)
        )


    def _aplicar_filtros_comunes(self, qs):
        """Aplica filtros compartidos (Ubicación, Fechas)."""
        if self.ubicacion_id:
            qs = qs.filter(compartimento__ubicacion__id=self.ubicacion_id)
        
        if self.fecha_desde:
            qs = qs.filter(fecha_recepcion__gte=self.fecha_desde)
        
        if self.fecha_hasta:
            qs = qs.filter(fecha_recepcion__lte=self.fecha_hasta)
            
        return qs


    def _combinar_y_ordenar(self, activos, lotes):
        """
        Combina querysets, INYECTA ALERTA DE STOCK CRÍTICO y ordena con desempate.
        """
        # 1. Convertir a listas para iterar
        # (Esto dispara las queries de Activos y Lotes, trayendo los datos)
        activos_list = list(activos)
        lotes_list = list(lotes)
        
        full_list = activos_list + lotes_list

        # --- OPTIMIZACIÓN STOCK CRÍTICO ---
        if full_list:
            # 2. Obtenemos el SET de IDs de productos que están críticos
            ids_criticos = self._get_productos_criticos_ids()
            
            # 3. Inyectamos la bandera en cada objeto en memoria
            for item in full_list:
                # CAMBIO 4: Lógica de Alerta "Inteligente"
                # Solo marcamos alerta si es crítico Y NO está anulado
                es_anulado = getattr(item.estado, 'nombre', '') == 'ANULADO POR ERROR'
                
                if not es_anulado and item.producto_id in ids_criticos:
                    item.alerta_stock_critico = True
                else:
                    item.alerta_stock_critico = False
        
        # 4. Ordenamiento (Tu lógica original intacta)
        reverse = self.sort_by.endswith('_desc')
        key_name = self.sort_by.replace('_desc', '').replace('_asc', '')

        # Helpers para fechas seguras
        min_date = datetime.date.min
        max_date = datetime.date.max
        min_dt = timezone.make_aware(datetime.datetime.min)

        sort_strategies = {
            'vencimiento': lambda x: (
                getattr(x, 'vencimiento_final', max_date) or max_date, 
                x.created_at or min_dt # Desempate por creación
            ),
            'fecha': lambda x: (
                getattr(x, 'fecha_recepcion', min_date) or min_date, 
                x.created_at or min_dt # Desempate por creación (Clave para tu requerimiento)
            ),
            'nombre': lambda x: (
                getattr(x.producto.producto_global, 'nombre_oficial', ''), 
                x.created_at or min_dt
            ),
        }

        strategy = sort_strategies.get(key_name)
        if strategy:
            full_list.sort(key=strategy, reverse=reverse)

        return full_list
    

    def _get_productos_criticos_ids(self):
        """
        Retorna un SET con los IDs de productos que están bajo stock crítico.
        Realiza una única consulta agregada potente.
        """
        # Usamos la misma lógica potente que hicimos para el Dashboard
        # pero solo devolvemos los IDs para ser eficientes.
        
        criticos_qs = Producto.objects.filter(
            estacion=self.estacion_activa,
            stock_critico__gt=0
        ).annotate(
            cant_activos=Count(
                'activo', 
                filter=Q(activo__estado__tipo_estado__nombre='OPERATIVO')
            ),
            cant_lotes=Coalesce(
                Sum('loteinsumo__cantidad', 
                    filter=Q(loteinsumo__estado__tipo_estado__nombre='OPERATIVO')
                ), 
                0
            )
        ).annotate(
            stock_total=F('cant_activos') + F('cant_lotes')
        ).filter(
            stock_total__lte=F('stock_critico')
        ).values_list('id', flat=True) # <--- Solo traemos los IDs

        return set(criticos_qs) # Convertimos a set para búsqueda rápida




class RecepcionStockView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista transaccional compleja para recepción de stock.
    Descompone la lógica monolítica en métodos de servicio privados,
    maneja formsets dinámicos y encapsula la creación polimórfica (Activo/Lote).
    """
    template_name = 'gestion_inventario/pages/recepcion_stock.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_recepcionar_stock"


    def get(self, request, *args, **kwargs):
        cabecera_form = RecepcionCabeceraForm(estacion=self.estacion_activa)
        detalle_formset = RecepcionDetalleFormSet(
            form_kwargs={'estacion': self.estacion_activa}, 
            prefix='detalles'
        )
        
        context = {
            'cabecera_form': cabecera_form,
            'detalle_formset': detalle_formset,
            'product_data_json': self._get_product_data_json(),
            'ubicaciones_data_json': self._get_ubicaciones_data_json()
        }
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        cabecera_form = RecepcionCabeceraForm(request.POST, estacion=self.estacion_activa)
        detalle_formset = RecepcionDetalleFormSet(
            request.POST, 
            form_kwargs={'estacion': self.estacion_activa}, 
            prefix='detalles'
        )

        if cabecera_form.is_valid() and detalle_formset.is_valid():
            try:
                # Delegamos la lógica transaccional a un método dedicado
                redirect_url = self._procesar_recepcion(cabecera_form, detalle_formset)
                return HttpResponseRedirect(redirect_url)

            except Exception as e:
                messages.error(request, f"Error crítico al guardar la recepción: {e}")
                # Fallthrough para renderizar el formulario con el error
        else:
            messages.warning(request, "Por favor, corrija los errores en el formulario.")

        context = {
            'cabecera_form': cabecera_form,
            'detalle_formset': detalle_formset,
            'product_data_json': self._get_product_data_json(),
            'ubicaciones_data_json': self._get_ubicaciones_data_json()
        }
        return render(request, self.template_name, context)


    @transaction.atomic
    def _procesar_recepcion(self, cabecera_form, detalle_formset):
        """
        Método transaccional que orquesta la creación de Activos/Lotes y Movimientos.
        Retorna la URL de redirección final.
        """
        proveedor = cabecera_form.cleaned_data['proveedor']
        fecha_recepcion = cabecera_form.cleaned_data['fecha_recepcion']
        notas = cabecera_form.cleaned_data['notas']
        
        # Obtener estado UNA SOLA VEZ para toda la transacción
        estado_disponible = Estado.objects.get(nombre='DISPONIBLE', tipo_estado__nombre='OPERATIVO')

        nuevos_ids = {'activos': [], 'lotes': []}
        cantidad_total_items = 0 # Suma total de unidades físicas
        compartimentos_destino_set = set() # Para capturar destinos únicos

        for form in detalle_formset:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            data = form.cleaned_data
            producto = data['producto']

            # Capturar nombre del compartimento destino para el log
            if data.get('compartimento_destino'):
                compartimentos_destino_set.add(data['compartimento_destino'].nombre)
            
            # Actualización de costos (Side-effect intencional)
            costo = data.get('costo_unitario')
            if costo is not None and producto.costo_compra != costo:
                producto.costo_compra = costo
                producto.save(update_fields=['costo_compra'])

            # Dispatch polimórfico
            if producto.es_serializado:
                item_id = self._crear_activo(data, proveedor, fecha_recepcion, notas, estado_disponible)
                nuevos_ids['activos'].append(item_id)
                cantidad_total_items += 1
            else:
                item_id = self._crear_lote(data, proveedor, fecha_recepcion, notas, estado_disponible)
                nuevos_ids['lotes'].append(item_id)
                cantidad_total_items += data['cantidad']

        # --- CONSTRUCCIÓN DE VERBO DETALLADO ---
        cant_activos = len(nuevos_ids['activos'])
        cant_insumos = cantidad_total_items - cant_activos
        
        partes_msg = []
        if cant_activos > 0:
            partes_msg.append(f"{cant_activos} Activo{'s' if cant_activos != 1 else ''}")
        if cant_insumos > 0:
            partes_msg.append(f"{cant_insumos} unidad{'es' if cant_insumos != 1 else ''} de Insumo{'s' if cant_insumos != 1 else ''}")
        
        detalle_texto = " y ".join(partes_msg) if partes_msg else "carga de inventario"
        
        # Texto de destinos (Ej: " en Pañol 1, Bodega B")
        lista_destinos = list(compartimentos_destino_set)
        texto_destinos = ""
        if lista_destinos:
            # Limitamos a mostrar 2 nombres para no saturar el feed si son muchos
            if len(lista_destinos) > 2:
                texto_destinos = f" en {', '.join(lista_destinos[:2])} y otros"
            else:
                texto_destinos = f" en {', '.join(lista_destinos)}"

        verbo_final = f"recepcionó {detalle_texto}{texto_destinos} desde el proveedor"

        # --- AUDITORÍA CONSOLIDADA ---
        self.auditar(
            verbo=verbo_final,
            objetivo=proveedor, 
            detalles={
                'total_unidades': cantidad_total_items,
                'desglose': {'activos': cant_activos, 'insumos': cant_insumos},
                'destinos': lista_destinos,
                # FIX: Serialización explícita de UUIDs a string
                'nuevos_activos_ids': [str(uid) for uid in nuevos_ids['activos']],
                'nuevos_lotes_ids': [str(uid) for uid in nuevos_ids['lotes']],
                'nota_recepcion': notas
            }
        )

        messages.success(self.request, "Recepción de stock guardada correctamente.")
        return self._construir_url_redireccion(nuevos_ids)


    def _crear_activo(self, data, proveedor, fecha, notas, estado):
        """Helper para crear un Activo y su movimiento."""
        activo = Activo.objects.create(
            producto=data['producto'],
            estacion=self.estacion_activa,
            compartimento=data['compartimento_destino'],
            proveedor=proveedor,
            estado=estado,
            numero_serie_fabricante=data.get('numero_serie'),
            fecha_fabricacion=data.get('fecha_fabricacion'),
            fecha_recepcion=fecha
        )
        
        MovimientoInventario.objects.create(
            tipo_movimiento=TipoMovimiento.ENTRADA,
            usuario=self.request.user,
            estacion=self.estacion_activa,
            proveedor_origen=proveedor,
            compartimento_destino=data['compartimento_destino'],
            activo=activo,
            cantidad_movida=1,
            notas=notas
        )
        return activo.id


    def _crear_lote(self, data, proveedor, fecha, notas, estado):
        """Helper para crear un Lote y su movimiento."""
        lote = LoteInsumo.objects.create(
            producto=data['producto'],
            compartimento=data['compartimento_destino'],
            cantidad=data['cantidad'],
            numero_lote_fabricante=data.get('numero_lote'),
            fecha_expiracion=data.get('fecha_vencimiento'),
            fecha_recepcion=fecha,
            estado=estado
        )

        MovimientoInventario.objects.create(
            tipo_movimiento=TipoMovimiento.ENTRADA,
            usuario=self.request.user,
            estacion=self.estacion_activa,
            proveedor_origen=proveedor,
            compartimento_destino=data['compartimento_destino'],
            lote_insumo=lote,
            cantidad_movida=data['cantidad'],
            notas=notas
        )
        return lote.id


    def _construir_url_redireccion(self, ids_dict):
        """Construye la URL final (Impresión o Stock) según resultados."""
        if not ids_dict['activos'] and not ids_dict['lotes']:
             return reverse('gestion_inventario:ruta_stock_actual')

        base_url = reverse('gestion_inventario:ruta_imprimir_etiquetas')
        params = []
        if ids_dict['activos']:
            params.append(f"activos={','.join(map(str, ids_dict['activos']))}")
        if ids_dict['lotes']:
            params.append(f"lotes={','.join(map(str, ids_dict['lotes']))}")
        
        return f"{base_url}?{'&'.join(params)}"


    def _get_product_data_json(self):
        """
        Método auxiliar para obtener los datos del producto.
        Reutilizable en GET y POST sin causar errores de recursión.
        """
        # Optimizamos usando .values() para no instanciar objetos pesados
        productos = Producto.objects.filter(estacion=self.estacion_activa).values(
            'id', 'es_serializado', 'es_expirable'
        )
        # Convertimos a diccionario {id: data}
        data = {p['id']: {'es_serializado': p['es_serializado'], 'es_expirable': p['es_expirable']} for p in productos}
        return json.dumps(data)
    

    def _get_ubicaciones_data_json(self):
        """
        Genera una estructura JSON con Ubicaciones y sus Compartimentos,
        EXCLUYENDO las ubicaciones de tipo 'ADMINISTRATIVA' (el limbo).
        """
        # 1. Filtramos ubicaciones que NO sean administrativas
        ubicaciones = Ubicacion.objects.filter(
            estacion=self.estacion_activa
        ).exclude(
            tipo_ubicacion__nombre='ADMINISTRATIVA'
        ).prefetch_related('compartimento_set')

        data = {}
        for ubi in ubicaciones:
            # 2. Convertimos los compartimentos manualmente para asegurar que el ID sea string
            compartimentos_list = []
            for comp in ubi.compartimento_set.all():
                compartimentos_list.append({
                    'id': str(comp.id),
                    'nombre': comp.nombre
                })
            
            # 3. Usamos el ID de ubicación como string para la clave
            data[str(ubi.id)] = {
                'nombre': ubi.nombre,
                'compartimentos': compartimentos_list
            }
        
        return json.dumps(data)




class AgregarStockACompartimentoView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para ingreso rápido de stock en compartimento.
    Gestiona transacciones atómicas, cumple reglas de negocio
    (creación de movimientos) y maneja estados de UI (tabs) ante errores.
    """
    template_name = 'gestion_inventario/pages/agregar_stock_compartimento.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_recepcionar_stock"

    def get_compartimento(self, compartimento_id):
        return get_object_or_404(
            Compartimento.objects.select_related('ubicacion'),
            id=compartimento_id,
            ubicacion__estacion_id=self.estacion_activa_id
        )

    def get(self, request, compartimento_id):
        context = {
            'compartimento': self.get_compartimento(compartimento_id),
            'activo_form': ActivoSimpleCreateForm(estacion_id=self.estacion_activa_id),
            'lote_form': LoteInsumoSimpleCreateForm(estacion_id=self.estacion_activa_id),
            'active_tab': 'activo'
        }
        return render(request, self.template_name, context)

    def post(self, request, compartimento_id):
        compartimento = self.get_compartimento(compartimento_id)
        action = request.POST.get('action')

        data = request.POST.copy()
        data['compartimento'] = compartimento.id
        
        # Ahora inicializamos los forms con 'data' (que ya trae el ID del compartimento)
        activo_form = ActivoSimpleCreateForm(data, estacion_id=self.estacion_activa_id)
        lote_form = LoteInsumoSimpleCreateForm(data, estacion_id=self.estacion_activa_id)

        try:
            if action == 'add_activo':
                if activo_form.is_valid():
                    self._procesar_activo(activo_form, compartimento)
                    return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=compartimento.id)
                else:
                    messages.error(request, f"Error al crear Activo: {activo_form.errors}")
                    active_tab = 'activo'

            elif action == 'add_insumo':
                if lote_form.is_valid():
                    self._procesar_lote(lote_form, compartimento)
                    return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=compartimento.id)
                else:
                    messages.error(request, f"Error al crear Lote: {lote_form.errors}")
                    active_tab = 'insumo'
            else:
                messages.error(request, "Acción desconocida.")
                active_tab = 'activo'

        except Exception as e:
            messages.error(request, f"Error al guardar: {e}")
            active_tab = 'activo' if action == 'add_activo' else 'insumo'

        # Renderizar con errores
        context = {
            'compartimento': compartimento,
            'activo_form': activo_form,
            'lote_form': lote_form,
            'active_tab': active_tab
        }
        return render(request, self.template_name, context)

    @transaction.atomic
    def _procesar_activo(self, form, compartimento):
        # 1. Crear Activo (Sin asignar código manual)
        activo = form.save(commit=False)
        activo.estacion = self.estacion_activa
        activo.compartimento = compartimento
        activo.estado = Estado.objects.get(nombre='DISPONIBLE')
        
        # OJO: No tocamos activo.codigo_activo. 
        # Al ser nuevo, el modelo lo generará en el save().
        activo.save()

        # 2. Crear Movimiento
        MovimientoInventario.objects.create(
            tipo_movimiento=TipoMovimiento.ENTRADA,
            usuario=self.request.user,
            estacion=self.estacion_activa,
            compartimento_destino=compartimento,
            activo=activo,
            cantidad_movida=1,
            notas="Ingreso rápido directo."
        )

        # --- AUDITORÍA ---
        self.auditar(
            verbo=f"realizó ingreso rápido de activo en {compartimento.ubicacion.nombre}->{compartimento.nombre} de",
            objetivo=activo,
            objetivo_repr=f"{activo.producto.producto_global.nombre_oficial} ({activo.codigo_activo})",
            detalles={
                'compartimento': compartimento.nombre,
                'codigo': activo.codigo_activo
            }
        )
        
        messages.success(self.request, f"Activo '{activo.producto.producto_global.nombre_oficial}' añadido.")

    @transaction.atomic
    def _procesar_lote(self, form, compartimento):
        # 1. Crear Lote
        lote = form.save(commit=False)
        lote.compartimento = compartimento
        lote.estado = Estado.objects.get(nombre='DISPONIBLE')
        lote.save()

        # 2. Crear Movimiento
        MovimientoInventario.objects.create(
            tipo_movimiento=TipoMovimiento.ENTRADA,
            usuario=self.request.user,
            estacion=self.estacion_activa,
            compartimento_destino=compartimento,
            lote_insumo=lote,
            cantidad_movida=lote.cantidad,
            notas=f"Ingreso rápido lote: {lote.numero_lote_fabricante or 'S/N'}"
        )

        # --- AUDITORÍA ---
        self.auditar(
            verbo=f"realizó ingreso rápido de lote/insumo en {compartimento.ubicacion.nombre}->{compartimento.nombre} de",
            objetivo=lote,
            objetivo_repr=f"{lote.producto.producto_global.nombre_oficial} ({lote.codigo_lote})",
            detalles={
                'compartimento': compartimento.nombre,
                'cantidad': lote.cantidad,
                'producto': lote.producto.producto_global.nombre_oficial
            }
        )

        messages.success(self.request, f"Lote añadido: {lote.cantidad} u.")




class DetalleExistenciaView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
    """
    Vista Maestra: Hoja de Vida de la Existencia.
    Muestra trazabilidad total: Ubicación, Movimientos, Uso y Mantenimiento.
    """
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_stock"
    template_name = 'gestion_inventario/pages/detalle_existencia.html'

    def get(self, request, tipo_item, item_id):
        context = {}
        
        # 1. Determinar y obtener el objeto (Polimorfismo)
        if tipo_item == 'activo':
            item = get_object_or_404(
                Activo.objects.select_related(
                    'producto__producto_global', 
                    'compartimento__ubicacion', 
                    'estado',
                    'proveedor'
                ),
                id=item_id,
                estacion=self.estacion_activa
            )
            # Cargar contexto profundo para Activos
            context.update(self._get_contexto_activo(item))
            context['es_activo'] = True

        elif tipo_item == 'lote':
            item = get_object_or_404(
                LoteInsumo.objects.select_related(
                    'producto__producto_global', 
                    'compartimento__ubicacion', 
                    'estado'
                ),
                id=item_id,
                compartimento__ubicacion__estacion=self.estacion_activa
            )
            # Cargar contexto simple para Lotes
            context['es_activo'] = False
        
        else:
            raise Http404("Tipo de ítem no válido")

        # 2. Contexto Común (Historial de Movimientos)
        # Traemos los últimos 50 movimientos para la bitácora
        movimientos = MovimientoInventario.objects.filter(
            estacion=self.estacion_activa
        ).filter(
            Q(activo=item) if tipo_item == 'activo' else Q(lote_insumo=item)
        ).select_related(
            'usuario', 'compartimento_origen', 'compartimento_destino'
        ).order_by('-fecha_hora')[:50]

        context['item'] = item
        context['tipo_item'] = tipo_item # 'activo' o 'lote' para URLs
        context['historial_movimientos'] = movimientos
        
        return render(request, self.template_name, context)

    def _get_contexto_activo(self, activo):
        """
        Recopila toda la data compleja exclusiva de Activos Serializados.
        """
        data = {}

        # A. HISTORIAL DE USO (RegistroUsoActivo)
        # Obtenemos estadísticas básicas
        uso_stats = RegistroUsoActivo.objects.filter(activo=activo).aggregate(
            total_horas=Sum('horas_registradas'),
            ultimo_uso=Max('fecha_uso'),
            total_registros=Count('id')
        )
        data['uso_stats'] = uso_stats
        
        # Últimos 5 registros de uso para el widget
        data['ultimos_usos'] = RegistroUsoActivo.objects.filter(activo=activo)\
            .select_related('usuario_registra').order_by('-fecha_uso')[:5]

        # B. MANTENIMIENTO: HISTORIAL (Bitácora)
        # Registros cerrados de mantenimiento
        data['historial_mantencion'] = RegistroMantenimiento.objects.filter(activo=activo)\
            .select_related('usuario_ejecutor', 'orden_mantenimiento')\
            .order_by('-fecha_ejecucion')[:10]

        # C. MANTENIMIENTO: ÓRDENES EN CURSO (Lo que está pasando ahora)
        data['ordenes_activas'] = OrdenMantenimiento.objects.filter(
            activos_afectados=activo,
            estado__in=['PENDIENTE', 'EN_CURSO']
        ).order_by('fecha_programada')

        # D. PLANES DE MANTENIMIENTO (El Futuro)
        # Qué planes aplican a este activo y cuándo tocan
        planes_config = PlanActivoConfig.objects.filter(
            activo=activo, 
            plan__activo_en_sistema=True
        ).select_related('plan')
        
        data['planes_asociados'] = planes_config

        return data




class AnularExistenciaView(BaseEstacionMixin, CustomPermissionRequiredMixin, StationInventoryObjectMixin, InventoryStateValidatorMixin, AuditoriaMixin, View):
    """
    Vista para anular existencia.
    Usa StationInventoryObjectMixin para cargar el ítem y
    InventoryStateValidatorMixin para validar reglas de negocio.
    """
    template_name = 'gestion_inventario/pages/anular_existencia.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_bajas_stock"

    def dispatch(self, request, *args, **kwargs):
        self.item = self.get_inventory_item()

        if not self.item:
            # Si no hay item (o no hay sesión), dejamos pasar para que los mixins de seguridad redirijan
            # o lanzamos 404. En este flujo, BaseEstacionMixin atrapará la falta de sesión.
            return super().dispatch(request, *args, **kwargs)
        
        # 2. Validamos el estado (Regla de Negocio)
        # Solo dejamos pasar si está 'DISPONIBLE'
        if not self.validate_state(self.item, ['DISPONIBLE']):
            return redirect('gestion_inventario:ruta_stock_actual')

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # El mixin ya inyecta 'item' y 'tipo_item' en get_context_data si usáramos TemplateView.
        # Como heredamos de View, debemos construir el contexto, pero es trivial.
        context = {
            'item': self.item,
            'tipo_item': self.tipo_item
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        try:
            estado_anulado = Estado.objects.get(nombre='ANULADO POR ERROR')
            compartimento_destino = get_or_create_anulado_compartment(self.estacion_activa)
            compartimento_origen = self.item.compartimento
            codigo_item = self.item.codigo_activo if self.tipo_item == 'activo' else self.item.codigo_lote

            with transaction.atomic():
                # 1. Actualizar Item
                cantidad_movimiento = 0
                if self.tipo_item == 'lote':
                    cantidad_movimiento = self.item.cantidad * -1
                    self.item.cantidad = 0
                else:
                    cantidad_movimiento = -1
                
                self.item.estado = estado_anulado
                self.item.compartimento = compartimento_destino
                self.item.save()

                # 2. Auditoría
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.AJUSTE,
                    usuario=request.user,
                    estacion=self.estacion_activa,
                    compartimento_origen=compartimento_origen,
                    compartimento_destino=compartimento_destino,
                    activo=self.item if self.tipo_item == 'activo' else None,
                    lote_insumo=self.item if self.tipo_item == 'lote' else None,
                    cantidad_movida=cantidad_movimiento,
                    notas="Anulación por error de ingreso."
                )

                # --- AUDITORÍA CRÍTICA ---
                # Usamos el objetivo_repr explícito para que el log diga "Activo XYZ" 
                # aunque el objeto ahora esté en estado "Anulado".
                self.auditar(
                    verbo="Anuló el registro de existencia (Error de Ingreso)",
                    objetivo=self.item,
                    objetivo_repr=f"{self.item.producto.producto_global.nombre_oficial} ({codigo_item})",
                    detalles={
                        'ubicacion_previa': compartimento_origen.nombre,
                        'motivo': 'Corrección administrativa / Error de digitación'
                    }
                )

            messages.success(
                request, 
                f"'{self.item.producto.producto_global.nombre_oficial}' anulado correctamente."
            )
            return redirect('gestion_inventario:ruta_stock_actual')

        except Exception as e:
            messages.error(request, f"Error al anular: {e}")
            return redirect('gestion_inventario:ruta_stock_actual')




class AjustarStockLoteView(BaseEstacionMixin, CustomPermissionRequiredMixin, InventoryStateValidatorMixin, SingleObjectMixin, AuditoriaMixin, FormView):
    """
    Vista para ajuste manual de stock de lotes (inventario cíclico).
    Combina FormView (para el formulario de ajuste) con 
    SingleObjectMixin (para recuperar el Lote de forma segura) y valida estados.
    """
    model = LoteInsumo
    form_class = LoteAjusteForm
    template_name = 'gestion_inventario/pages/ajustar_stock_lote.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_stock_interno"
    pk_url_kwarg = 'lote_id'
    context_object_name = 'lote'

    def get_queryset(self):
        """Filtra el lote por la estación activa y precarga relaciones."""
        # --- CORRECCIÓN DE SEGURIDAD MRO ---
        # Intentamos obtener el ID del atributo (si el mixin ya corrió)
        estacion_id = getattr(self, 'estacion_activa_id', None)
        
        # Si no, lo sacamos directo de la sesión (si el mixin aún no corre)
        if not estacion_id:
            estacion_id = self.request.session.get('active_estacion_id')

        # Si no hay sesión, devolvemos vacío (get_object lanzará 404 y luego el mixin redirigirá)
        if not estacion_id:
            return super().get_queryset().none()
        
        return super().get_queryset().filter(
            compartimento__ubicacion__estacion_id=estacion_id
        ).select_related(
            'producto__producto_global', 
            'compartimento__ubicacion',
            'estado'
        )
    
    def dispatch(self, request, *args, **kwargs):
        """
        Validación Temprana: Cargamos el objeto y verificamos su estado 
        antes de procesar GET o POST.
        """
        # 1. Recuperar el objeto (SingleObjectMixin usa get_queryset)
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(request, "Lote no encontrado en tu estación.")
            return redirect('gestion_inventario:ruta_stock_actual')

        # 2. USAR EL MIXIN PARA VALIDAR EL ESTADO
        # Regla: Solo 'DISPONIBLE' permite ajustes de conteo.
        if not self.validate_state(self.object, ['DISPONIBLE']):
            return redirect('gestion_inventario:ruta_stock_actual')

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # No necesitamos recargar self.object, ya lo hizo dispatch.
        # Pero SingleObjectMixin espera que lo llamemos o accedamos a self.object.
        # Aquí ya self.object existe.
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Igual que en get, self.object ya existe gracias a dispatch.
        return super().post(request, *args, **kwargs)

    def get_initial(self):
        """Pre-llena el formulario con la cantidad actual."""
        return {'nueva_cantidad_fisica': self.object.cantidad}

    def form_valid(self, form):
        nueva_cantidad = form.cleaned_data['nueva_cantidad_fisica']
        notas = form.cleaned_data['notas']
        cantidad_previa = self.object.cantidad
        diferencia = nueva_cantidad - cantidad_previa

        if diferencia == 0:
            messages.warning(self.request, "No se realizó ningún cambio.")
            return redirect(self.get_success_url())

        try:
            with transaction.atomic():
                # 1. Actualizar Lote
                self.object.cantidad = nueva_cantidad
                self.object.save(update_fields=['cantidad', 'updated_at'])

                # 2. Auditoría
                # Aquí usamos self.estacion_activa de forma segura porque
                # form_valid corre DESPUÉS de dispatch, por lo tanto BaseEstacionMixin ya se ejecutó.
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.AJUSTE,
                    usuario=self.request.user,
                    estacion=self.estacion_activa, 
                    compartimento_origen=self.object.compartimento,
                    lote_insumo=self.object,
                    cantidad_movida=diferencia,
                    notas=notas
                )

                # --- AUDITORÍA ---
                # Verbo dinámico para indicar si subió o bajó
                tipo_ajuste = "aumentó" if diferencia > 0 else "disminuyó"
                
                self.auditar(
                    verbo=f"ajustó manualmente el stock ({tipo_ajuste}) de",
                    objetivo=self.object,
                    objetivo_repr=f"{self.object.producto.producto_global.nombre_oficial} ({self.object.codigo_lote})",
                    detalles={
                        'cantidad_previa': cantidad_previa,
                        'cantidad_nueva': nueva_cantidad,
                        'diferencia': diferencia,
                        'motivo': notas
                    }
                )
            
            messages.success(
                self.request, 
                f"Stock ajustado: {cantidad_previa} -> {nueva_cantidad}."
            )
            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f"Error crítico: {e}")
            return self.form_invalid(form)
        
    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error en el formulario. Por favor, revisa los datos ingresados.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('gestion_inventario:ruta_stock_actual')




class BajaExistenciaView(BaseEstacionMixin, CustomPermissionRequiredMixin, StationInventoryObjectMixin, InventoryStateValidatorMixin, AuditoriaMixin, FormView):
    """
    Vista para Dar de Baja una existencia.
    Utiliza StationInventoryObjectMixin para la carga segura del ítem,
    InventoryStateValidatorMixin para reglas de negocio y transacciones atómicas.
    """
    template_name = 'gestion_inventario/pages/dar_de_baja_existencia.html'
    form_class = BajaExistenciaForm
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_bajas_stock"
    success_url = reverse_lazy('gestion_inventario:ruta_stock_actual')

    def dispatch(self, request, *args, **kwargs):
        # 1. Carga Explícita del Ítem (Mixin)
        # Si no hay estación, retorna None y deja que BaseEstacionMixin maneje el redirect.
        self.item = self.get_inventory_item()
        
        if not self.item:
            return super().dispatch(request, *args, **kwargs)
        
        # 2. Validación de Reglas de Negocio (Estado)
        # Solo se puede dar de baja lo que está en la estación (operativo o en taller).
        # No se puede dar de baja lo prestado (debe devolverse primero) ni lo extraviado.
        estados_permitidos = ['DISPONIBLE', 'PENDIENTE REVISIÓN', 'EN REPARACIÓN']
        
        if not self.validate_state(self.item, estados_permitidos):
            return redirect(self.success_url)
            
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        notas = form.cleaned_data['notas']
        
        try:
            estado_baja = Estado.objects.get(nombre='DE BAJA')

            # Preparamos datos para el log antes de guardar
            nombre_item = self.item.producto.producto_global.nombre_oficial
            codigo_item = self.item.codigo_activo if self.tipo_item == 'activo' else self.item.codigo_lote
            
            with transaction.atomic():
                # 1. Actualizar Estado y Cantidad
                cantidad_movimiento = 0
                
                if self.tipo_item == 'lote':
                    cantidad_movimiento = self.item.cantidad * -1 # Salida total
                    self.item.cantidad = 0
                else:
                    cantidad_movimiento = -1
                
                self.item.estado = estado_baja
                self.item.save()

                # 2. Auditoría (Movimiento)
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.SALIDA,
                    usuario=self.request.user,
                    # Usamos self.estacion_activa con seguridad (el mixin ya corrió)
                    estacion=self.estacion_activa, 
                    compartimento_origen=self.item.compartimento,
                    activo=self.item if self.tipo_item == 'activo' else None,
                    lote_insumo=self.item if self.tipo_item == 'lote' else None,
                    cantidad_movida=cantidad_movimiento,
                    notas=f"Baja: {notas}"
                )

                # --- AUDITORÍA DETALLADA ---
                self.auditar(
                    verbo="dio de baja del inventario operativo a",
                    objetivo=self.item,
                    # Forzamos el formato "Nombre (Código)" para máxima claridad en el feed
                    objetivo_repr=f"{nombre_item} ({codigo_item})",
                    detalles={
                        'motivo_declarado': notas,
                        'tipo_existencia': self.tipo_item
                    }
                )

            messages.success(
                self.request, 
                f"'{nombre_item}' dado de baja correctamente."
            )
            return super().form_valid(form)

        except Estado.DoesNotExist:
            messages.error(self.request, "Error crítico: Estado 'DE BAJA' no encontrado.")
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Error al procesar la baja: {e}")
            return self.form_invalid(form)
        
    def form_invalid(self, form):
        messages.error(self.request, "No se pudo procesar la baja. Revisa los campos del formulario.")
        return super().form_invalid(form)




class ExtraviadoExistenciaView(BaseEstacionMixin, CustomPermissionRequiredMixin, StationInventoryObjectMixin, InventoryStateValidatorMixin, AuditoriaMixin, FormView):
    """
    Vista para reportar una existencia como extraviada.
    Utiliza composición de mixins para manejo seguro de items,
    reglas de negocio y formularios.
    AHORA SÓLO FUNCIONA PARA EXISTENCIAS DE TIPO ACTIVO
    """
    template_name = 'gestion_inventario/pages/extraviado_existencia.html'
    form_class = ExtraviadoExistenciaForm
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_bajas_stock"
    success_url = reverse_lazy('gestion_inventario:ruta_stock_actual')

    def dispatch(self, request, *args, **kwargs):
        self.item = self.get_inventory_item()
        
        if not self.item:
            # Si falla la carga (o no hay sesión), el mixin o la redirección manual actúan
            return super().dispatch(request, *args, **kwargs) # Dejar que el flujo siga (posiblemente a 404 o redirect)
        
        # 1. RESTRICCIÓN: Solo Activos pueden usar esta vista específica
        if self.tipo_item == 'lote':
            messages.warning(request, "Para reportar pérdidas en Lotes/Insumos, utilice la opción 'Ajustar Stock'.")
            return redirect('gestion_inventario:ruta_stock_actual')

        # 2. Validar Estado (Regla de Negocio)
        estados_permitidos = ['DISPONIBLE', 'PENDIENTE REVISIÓN', 'EN REPARACIÓN', 'EN PRÉSTAMO EXTERNO']
        if not self.validate_state(self.item, estados_permitidos):
            return redirect(self.success_url)

        return super().dispatch(request, *args, **kwargs)

    # NOTA: Eliminamos _get_item_seguro y get_context_data.
    # StationInventoryObjectMixin ya provee get_context_data inyectando 'item' y 'tipo_item'.

    def form_valid(self, form):
        notas = form.cleaned_data['notas']
        try:
            estado_extraviado = Estado.objects.get(nombre='EXTRAVIADO')
            compartimento_limbo = get_or_create_extraviado_compartment(self.estacion_activa)

            # Preparar datos para el log
            nombre_item = self.item.producto.producto_global.nombre_oficial
            codigo_item = self.item.codigo_activo

            # Guardamos estado previo para lógica condicional
            estaba_prestado = (self.item.estado.nombre == 'EN PRÉSTAMO EXTERNO')

            with transaction.atomic():
                # --- A. LÓGICA DE MOVIMIENTO DE STOCK ---
                # Si estaba prestado, ya "salió" del almacén físico. No restamos de nuevo.
                # Si estaba disponible, sí restamos.
                cantidad_movimiento = 0 if estaba_prestado else -1
                
                # Actualizar Activo
                self.item.estado = estado_extraviado
                self.item.compartimento = compartimento_limbo
                self.item.save()

                # --- B. AUDITORÍA (MOVIMIENTO) ---
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.SALIDA,
                    usuario=self.request.user,
                    estacion=self.estacion_activa,
                    compartimento_origen=None if estaba_prestado else self.item.compartimento, # Si estaba prestado, no sale de un compartimento físico real
                    compartimento_destino=compartimento_limbo,
                    activo=self.item if self.tipo_item == 'activo' else None,
                    lote_insumo=self.item if self.tipo_item == 'lote' else None,
                    cantidad_movida=cantidad_movimiento,
                    notas=f"Extravío reportado: {notas}"
                )

                # 3. GESTIÓN DE PRÉSTAMOS PENDIENTES
                # Si el ítem estaba prestado, debemos 'saldar' la deuda en el préstamo
                # para que no quede abierto eternamente.
                if estaba_prestado:
                    self._registrar_perdida_en_prestamo(self.item)

                # --- REGISTRO DE ACTIVIDAD (Feed) ---
                self.auditar(
                    verbo="reportó como extraviado a",
                    objetivo=self.item,
                    objetivo_repr=f"{nombre_item} ({codigo_item})",
                    detalles={'motivo': notas, 'estaba_prestado': estaba_prestado}
                )

            messages.success(
                self.request, 
                f"'({codigo_item}) {nombre_item}' reportado como extraviado."
            )
            return super().form_valid(form)

        except Estado.DoesNotExist:
            messages.error(self.request, "Error crítico: Estado 'EXTRAVIADO' no encontrado.")
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Error inesperado: {e}")
            return self.form_invalid(form)
        

    def form_invalid(self, form):
        messages.error(self.request, "No se pudo procesar el reporte de extravío. Revisa los campos del formulario.")
        return super().form_invalid(form)
    

    def _registrar_perdida_en_prestamo(self, activo):
        """
        Busca el préstamo activo y marca la cantidad como EXTRAVIADA, no devuelta.
        """
        detalles = PrestamoDetalle.objects.filter(
            activo=activo,
            prestamo__estado__in=[Prestamo.EstadoPrestamo.PENDIENTE, Prestamo.EstadoPrestamo.DEVUELTO_PARCIAL]
        )

        for detalle in detalles:
            # Marcamos como extraviado en lugar de devuelto
            detalle.cantidad_extraviada = 1 
            detalle.save()
            
            # Verificamos si esto cierra el préstamo
            self._verificar_cierre_prestamo(detalle.prestamo)
    

    def _verificar_cierre_prestamo(self, prestamo):
        """Lógica reutilizable para cerrar préstamos."""
        # Un ítem está saldado si (devuelto + extraviado) >= prestado
        todos_saldados = all(d.esta_saldado for d in prestamo.items_prestados.all())
        
        if todos_saldados:
            prestamo.estado = Prestamo.EstadoPrestamo.COMPLETADO
            prestamo.save(update_fields=['estado', 'updated_at'])




class ConsumirStockLoteView(BaseEstacionMixin, CustomPermissionRequiredMixin, InventoryStateValidatorMixin, SingleObjectMixin, AuditoriaMixin, FormView):
    """
    Vista para registrar consumo de stock (Salida por uso interno).
    Utiliza FormView, valida reglas de negocio (estados permitidos)
    y gestiona transacciones atómicas.
    """
    model = LoteInsumo
    form_class = LoteConsumirForm
    template_name = 'gestion_inventario/pages/consumir_stock_lote.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_stock_interno"
    pk_url_kwarg = 'lote_id'
    context_object_name = 'lote'
    success_url = reverse_lazy('gestion_inventario:ruta_stock_actual')

    def get_queryset(self):
        """Filtra el lote por la estación activa de forma segura."""
        # Obtener ID de estación de la sesión para evitar error MRO antes del mixin
        estacion_id = self.request.session.get('active_estacion_id')
        if not estacion_id:
            return super().get_queryset().none()

        return super().get_queryset().filter(
            compartimento__ubicacion__estacion_id=estacion_id
        ).select_related(
            'producto__producto_global', 
            'compartimento__ubicacion',
            'estado'
        )

    def dispatch(self, request, *args, **kwargs):
        # 1. Cargar Objeto
        try:
            self.object = self.get_object()
        except Http404:
            messages.error(request, "Lote no encontrado o no pertenece a tu estación.")
            return redirect(self.success_url)

        # 2. Validar Estado (Regla de Negocio)
        if not self.validate_state(self.object, ['DISPONIBLE', 'EN PRÉSTAMO EXTERNO']):
            return redirect(self.success_url)

        # 3. Validar Stock > 0
        if self.object.cantidad <= 0:
            messages.warning(request, "Este lote no tiene stock disponible para consumir.")
            return redirect(self.success_url)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """Pasa el objeto lote al formulario (necesario para validaciones custom)."""
        kwargs = super().get_form_kwargs()
        kwargs['lote'] = self.object
        return kwargs
    
    def get_initial(self):
        return {'cantidad_a_consumir': 1}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lote'] = self.object
        return context

    def form_valid(self, form):
        cantidad_consumida = form.cleaned_data['cantidad_a_consumir']
        notas = form.cleaned_data['notas']
        
        try:
            with transaction.atomic():
                # 1. Actualizar Lote
                self.object.cantidad -= cantidad_consumida
                self.object.save(update_fields=['cantidad', 'updated_at'])

                # 2. Auditoría (Salida)
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.SALIDA,
                    usuario=self.request.user,
                    estacion_id=self.request.session.get('active_estacion_id'),
                    compartimento_origen=self.object.compartimento,
                    lote_insumo=self.object,
                    cantidad_movida=cantidad_consumida * -1, # Negativo
                    notas=notas
                )

                # --- AUDITORÍA ---
                self.auditar(
                    verbo=f"registró el consumo interno de {cantidad_consumida} unidad(es) de",
                    objetivo=self.object,
                    # Usamos nombre + código para máxima claridad
                    objetivo_repr=f"{self.object.producto.producto_global.nombre_oficial} ({self.object.codigo_lote})",
                    detalles={
                        'cantidad_consumida': cantidad_consumida,
                        'cantidad_restante': self.object.cantidad,
                        'motivo_uso': notas
                    }
                )
            
            messages.success(
                self.request, 
                f"Se consumieron {cantidad_consumida} unidades del lote {self.object.codigo_lote}."
            )
            return super().form_valid(form)
            
        except Exception as e:
            messages.error(self.request, f"Error al guardar el consumo: {e}")
            return self.form_invalid(form)
        
    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error en el formulario. Por favor, revisa los datos ingresados.")
        return super().form_invalid(form)




class RegistrarUsoActivoView(BaseEstacionMixin, CustomPermissionRequiredMixin, StationInventoryObjectMixin, InventoryStateValidatorMixin, AuditoriaMixin, FormView):
    """
    Vista para registrar horas de uso en un Activo Serializado.
    Incrementa el contador total del activo y genera un registro en la bitácora.
    """
    template_name = 'gestion_inventario/pages/registrar_uso_activo.html'
    form_class = RegistroUsoForm
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_stock_interno"
    
    def get_success_url(self):
        # Redirige a la hoja de vida del activo (Detalle Existencia)
        return reverse('gestion_inventario:ruta_detalle_existencia', kwargs={'tipo_item': 'activo', 'item_id': self.item.id})

    def dispatch(self, request, *args, **kwargs):
        # 1. Carga Segura del Ítem (Mixin StationInventoryObjectMixin)
        self.item = self.get_inventory_item()
        
        if not self.item:
            return super().dispatch(request, *args, **kwargs) # Flujo de error estándar (404/Redirect)

        # 2. Validación de Tipo: Solo Activos
        if self.tipo_item != 'activo':
            messages.warning(request, "El registro de horas de uso solo aplica a Activos Serializados, no a Lotes.")
            return redirect('gestion_inventario:ruta_stock_actual')

        # 3. Validación de Estado (Mixin InventoryStateValidatorMixin)
        # Se permite registrar uso si está operativo, prestado o asignado.
        estados_permitidos = ['DISPONIBLE', 'ASIGNADO', 'EN PRÉSTAMO EXTERNO', 'PENDIENTE REVISIÓN']
        if not self.validate_state(self.item, estados_permitidos):
            return redirect('gestion_inventario:ruta_stock_actual')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # self.item es inyectado por el StationInventoryObjectMixin, 
        # pero lo aseguramos explícitamente si el template lo requiere aparte.
        context['activo'] = self.item 
        return context

    def form_valid(self, form):
        horas = form.cleaned_data['horas']
        fecha_uso = form.cleaned_data['fecha_uso']
        notas = form.cleaned_data['notas']

        try:
            with transaction.atomic():
                # 1. Crear el registro en la bitácora histórica
                RegistroUsoActivo.objects.create(
                    activo=self.item,
                    usuario_registra=self.request.user,
                    fecha_uso=fecha_uso,
                    horas_registradas=horas,
                    notas=notas
                )

                # 2. Actualizar el acumulador en el Activo
                # Usamos F() expressions para evitar condiciones de carrera (race conditions)
                self.item.horas_uso_totales = F('horas_uso_totales') + horas
                self.item.save(update_fields=['horas_uso_totales', 'updated_at'])

                # Recargamos el objeto para tener el valor numérico actualizado para el log
                self.item.refresh_from_db()

                # --- AUDITORÍA ---
                self.auditar(
                    verbo=f"registró {horas} horas de uso para",
                    objetivo=self.item,
                    objetivo_repr=f"{self.item.producto.producto_global.nombre_oficial} ({self.item.codigo_activo})",
                    detalles={
                        'horas_agregadas': float(horas),
                        'total_acumulado': float(self.item.horas_uso_totales),
                        'fecha_uso': fecha_uso.strftime('%Y-%m-%d %H:%M'),
                        'notas': notas
                    }
                )

            messages.success(
                self.request, 
                f"Se registraron {horas} horas correctamente. Total acumulado: {self.item.horas_uso_totales} hrs."
            )
            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f"Error al guardar el registro de uso: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Datos inválidos. Por favor revise el formulario.")
        return super().form_invalid(form)




class TransferenciaExistenciaView(BaseEstacionMixin, CustomPermissionRequiredMixin, StationInventoryObjectMixin, InventoryStateValidatorMixin, AuditoriaMixin, FormView):
    """
    Vista para transferir existencias.
    Utiliza composición de Mixins para delegar la recuperación del ítem,
    la validación de reglas de negocio y la seguridad de sesión.
    """
    template_name = 'gestion_inventario/pages/transferir_existencia.html'
    form_class = TransferenciaForm
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_stock_interno"
    success_url = reverse_lazy('gestion_inventario:ruta_stock_actual')


    def dispatch(self, request, *args, **kwargs):
        # 1. Carga Explícita del Ítem (Mixin)
        self.item = self.get_inventory_item()
        
        if not self.item:
            return super().dispatch(request, *args, **kwargs) # Dejar que BaseEstacionMixin o 404 actúen

        # 2. Validar Estado (Regla de Negocio)
        # Solo se mueven ítems operativos (disponibles o asignados).
        if not self.validate_state(self.item, ['DISPONIBLE', 'ASIGNADO']):
            return redirect(self.success_url)

        return super().dispatch(request, *args, **kwargs)


    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['item'] = self.item
        # self.estacion_activa está garantizada por BaseEstacionMixin
        kwargs['estacion'] = self.estacion_activa 
        return kwargs


    def form_valid(self, form):
        compartimento_destino = form.cleaned_data['compartimento_destino']
        compartimento_origen = self.item.compartimento
        notas = form.cleaned_data['notas']
        
        try:
            nombre_item = self.item.producto.producto_global.nombre_oficial
            codigo_item = self.item.codigo_activo if self.tipo_item == 'activo' else self.item.codigo_lote
            cantidad_movida = 0 # Para el log y auditoría

            with transaction.atomic():
                if self.tipo_item == 'activo':
                    # --- LÓGICA ACTIVOS ---
                    self.item.compartimento = compartimento_destino
                    self.item.save(update_fields=['compartimento', 'updated_at'])
                    
                    msg_item = self.item.codigo_activo
                    cantidad_movida = 1
                    lote_ref = None
                    activo_ref = self.item

                else:
                    # --- LÓGICA LOTES (MERGE/SPLIT) ---
                    cantidad_a_mover = form.cleaned_data['cantidad']
                    
                    # Buscar/Crear lote destino (Merge)
                    lote_destino, created = LoteInsumo.objects.get_or_create(
                        producto=self.item.producto,
                        compartimento=compartimento_destino,
                        numero_lote_fabricante=self.item.numero_lote_fabricante,
                        fecha_expiracion=self.item.fecha_expiracion,
                        estado=self.item.estado,
                        defaults={
                            'cantidad': 0,
                            'fecha_recepcion': self.item.fecha_recepcion 
                        }
                    )
                    
                    lote_destino.cantidad += cantidad_a_mover
                    self.item.cantidad -= cantidad_a_mover
                    
                    lote_destino.save()
                    self.item.save()

                    msg_item = f"{cantidad_a_mover} u. de {self.item.codigo_lote}"
                    cantidad_movida = cantidad_a_mover
                    lote_ref = self.item # Vinculamos al origen
                    activo_ref = None

                # Auditoría Común
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.TRANSFERENCIA_INTERNA,
                    usuario=self.request.user,
                    estacion=self.estacion_activa,
                    compartimento_origen=compartimento_origen,
                    compartimento_destino=compartimento_destino,
                    activo=activo_ref,
                    lote_insumo=lote_ref,
                    cantidad_movida=cantidad_movida,
                    notas=notas
                )

                # --- REGISTRO DE ACTIVIDAD (Feed) ---
                # Construimos un verbo claro: "transfirió 5 u. a Bodega X"
                detalle_cantidad = f"{cantidad_movida} u." if self.tipo_item == 'lote' else ""
                
                self.auditar(
                    verbo=f"transfirió {detalle_cantidad} internamente hacia '{compartimento_destino.nombre}'",
                    objetivo=self.item,
                    objetivo_repr=f"{nombre_item} ({codigo_item})",
                    detalles={
                        'origen': compartimento_origen.nombre,
                        'destino': compartimento_destino.nombre,
                        'cantidad': cantidad_movida,
                        'nota': notas
                    }
                )

            messages.success(self.request, f"Se transfirió {msg_item} a '{compartimento_destino.nombre}'.")
            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f"Error crítico al transferir: {e}")
            return self.form_invalid(form)
        

    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error en el formulario. Por favor, revisa los datos ingresados.")
        return super().form_invalid(form)
    

    def get_context_data(self, **kwargs):
        """
        Reincorporamos get_context_data para inyectar los datos del selector en cascada.
        """
        context = super().get_context_data(**kwargs)
        context['ubicaciones_data_json'] = self._get_ubicaciones_data_json()
        return context


    def _get_ubicaciones_data_json(self):
        """
        Genera JSON {UbicacionID: {nombre, compartimentos: [...]}}
        Excluyendo 'ADMINISTRATIVA'.
        """
        ubicaciones = Ubicacion.objects.filter(
            estacion=self.estacion_activa
        ).exclude(
            tipo_ubicacion__nombre='ADMINISTRATIVA'
        ).prefetch_related('compartimento_set')

        data = {}
        for ubi in ubicaciones:
            compartimentos_list = []
            for comp in ubi.compartimento_set.all():
                compartimentos_list.append({
                    'id': str(comp.id),
                    'nombre': comp.nombre
                })
            
            data[str(ubi.id)] = {
                'nombre': ubi.nombre,
                'compartimentos': compartimentos_list
            }
        return json.dumps(data)




class CrearPrestamoView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para crear un Préstamo (Cabecera y Detalles).
    Manejo híbrido de Formulario + JSON, con lógica transaccional
    desacoplada y validación de concurrencia robusta.
    """
    template_name = 'gestion_inventario/pages/crear_prestamo.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_prestamos"


    def get(self, request, *args, **kwargs):
        context = {
            'cabecera_form': PrestamoCabeceraForm(estacion=self.estacion_activa),
        }
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        cabecera_form = PrestamoCabeceraForm(request.POST, estacion=self.estacion_activa)
        items_json_str = request.POST.get('items_json')
        
        # 1. Validación Inicial de JSON
        items_list = []
        if items_json_str:
            try:
                items_list = json.loads(items_json_str)
            except json.JSONDecodeError:
                messages.error(request, "Error: Los datos de los ítems están corruptos.")
        
        if not items_list:
            cabecera_form.add_error(None, "Debe escanear al menos un ítem.")

        # 2. Proceso Transaccional si todo es válido
        if cabecera_form.is_valid() and items_list:
            try:
                prestamo_id = self._procesar_transaccion_prestamo(cabecera_form, items_list)
                messages.success(request, f"Préstamo #{prestamo_id} creado exitosamente.")
                return redirect('gestion_inventario:ruta_historial_prestamos')

            except (Activo.DoesNotExist, LoteInsumo.DoesNotExist):
                messages.error(request, "Error de concurrencia: Un ítem ya no está disponible.")
            except Exception as e:
                messages.error(request, f"Error inesperado: {e}")
        else:
            messages.warning(request, "Por favor, corrija los errores del formulario.")

        # Fallback: Renderizar con errores
        context = {
            'cabecera_form': cabecera_form,
            'items_json_error': items_json_str # Para que el JS intente recuperar el estado
        }
        return render(request, self.template_name, context)


    @transaction.atomic
    def _procesar_transaccion_prestamo(self, form, items_list):
        """Orquesta la creación del préstamo, detalles y movimientos."""
        
        # A. Preparar Datos Base
        destinatario = self._get_or_create_destinatario(form)
        estado_prestamo = Estado.objects.get(nombre='EN PRÉSTAMO EXTERNO')
        estado_disponible = Estado.objects.get(nombre='DISPONIBLE')
        
        # B. Crear Cabecera
        prestamo = form.save(commit=False)
        prestamo.estacion = self.estacion_activa
        prestamo.usuario_responsable = self.request.user
        prestamo.destinatario = destinatario
        prestamo.save()

        # C. Procesar Ítems
        notas = form.cleaned_data['notas_prestamo']

        total_items_fisicos = 0
        conteo_activos = 0
        conteo_insumos = 0
        
        for item_data in items_list:
            if item_data['tipo'] == 'activo':
                self._procesar_item_activo(prestamo, item_data, notas, estado_disponible, estado_prestamo, destinatario)
                total_items_fisicos += 1
                conteo_activos += 1
            elif item_data['tipo'] == 'lote':
                self._procesar_item_lote(prestamo, item_data, notas, estado_disponible, destinatario)
                cantidad = int(item_data['cantidad_prestada'])
                total_items_fisicos += cantidad
                conteo_insumos += cantidad

        # --- AUDITORÍA (Registro Consolidado) ---
        partes_msg = []
        if conteo_activos > 0:
            partes_msg.append(f"{conteo_activos} Activo{'s' if conteo_activos != 1 else ''}")
        if conteo_insumos > 0:
            partes_msg.append(f"{conteo_insumos} unidad{'es' if conteo_insumos != 1 else ''} de Insumo{'s' if conteo_insumos != 1 else ''}")
        
        detalle_texto = " y ".join(partes_msg)
        
        self.auditar(
            verbo=f"registró el préstamo de {detalle_texto} a",
            objetivo=destinatario, # El objetivo lógico es quien recibe
            objetivo_repr=destinatario.nombre_entidad,
            detalles={
                'id_prestamo': prestamo.id,
                'responsable_interno': self.request.user.get_full_name,
                'total_items': total_items_fisicos,
                'desglose': {'activos': conteo_activos, 'insumos': conteo_insumos},
                'nota': notas
            }
        )
        
        return prestamo.id


    def _get_or_create_destinatario(self, form):
        """Busca o crea el destinatario según los datos del form."""
        destinatario = form.cleaned_data.get('destinatario')
        if not destinatario:
            destinatario, created = Destinatario.objects.get_or_create(
                estacion=self.estacion_activa,
                nombre_entidad=form.cleaned_data.get('nuevo_destinatario_nombre'),
                defaults={
                    'telefono_contacto': form.cleaned_data.get('nuevo_destinatario_contacto'),
                    'creado_por': self.request.user
                }
            )

            # --- AUDITORÍA (Creación implícita) ---
            if created:
                self.auditar(
                    verbo="registró como nuevo destinatario a",
                    objetivo=destinatario,
                    detalles={
                        'nombre': destinatario.nombre_entidad,
                        'telefono': destinatario.telefono_contacto
                    }
                )
                
        return destinatario


    def _procesar_item_activo(self, prestamo, data, notas, estado_disp, estado_prest, destinatario):
        """Procesa un activo individual."""
        # select_for_update bloquea la fila para evitar race conditions
        activo = Activo.objects.select_for_update().get(id=data['id'], estado=estado_disp)
        
        PrestamoDetalle.objects.create(prestamo=prestamo, activo=activo, cantidad_prestada=1)
        
        activo.estado = estado_prest
        activo.save(update_fields=['estado', 'updated_at'])
        
        self._crear_movimiento(activo.compartimento, activo, None, -1, destinatario, notas)

    def _procesar_item_lote(self, prestamo, data, notas, estado_disp, destinatario):
        """Procesa un lote individual."""
        cantidad = int(data['cantidad_prestada'])
        lote = LoteInsumo.objects.select_for_update().get(
            id=data['id'], 
            estado=estado_disp, 
            cantidad__gte=cantidad
        )
        
        PrestamoDetalle.objects.create(prestamo=prestamo, lote=lote, cantidad_prestada=cantidad)
        
        lote.cantidad -= cantidad
        lote.save(update_fields=['cantidad', 'updated_at'])
        
        self._crear_movimiento(lote.compartimento, None, lote, -1 * cantidad, destinatario, notas)

    def _crear_movimiento(self, compartimento, activo, lote, cantidad, destinatario, notas):
        """Helper genérico para movimientos."""
        MovimientoInventario.objects.create(
            tipo_movimiento=TipoMovimiento.PRESTAMO,
            usuario=self.request.user,
            estacion=self.estacion_activa,
            compartimento_origen=compartimento,
            activo=activo,
            lote_insumo=lote,
            cantidad_movida=cantidad,
            notas=f"Préstamo a {destinatario.nombre_entidad}. {notas}"
        )




class HistorialPrestamosView(BaseEstacionMixin, CustomPermissionRequiredMixin, ListView):
    """
    Vista para listar el historial de préstamos.
    Utiliza ListView genérica y BaseEstacionMixin para obtener 
    la estación directamente de la sesión, eliminando consultas redundantes a Membresía.
    """
    model = Prestamo
    template_name = 'gestion_inventario/pages/historial_prestamos.html'
    context_object_name = 'prestamos' # O 'page_obj' si tu template usa la paginación genérica
    paginate_by = 25
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_prestamos"

    def get_queryset(self):
        """
        Construye el queryset filtrado por estación y parámetros GET.
        """
        # 1. Base: Filtrar por estación de la sesión (Sin consultar Membresia)
        qs = super().get_queryset().filter(
            estacion=self.estacion_activa
        ).select_related(
            'destinatario', 'usuario_responsable'
        ).order_by('-fecha_prestamo')

        # 2. Inicializar formulario de filtros con los datos GET
        # Guardamos el form en self para pasarlo luego al contexto
        self.filter_form = PrestamoFilterForm(self.request.GET, estacion=self.estacion_activa)

        # 3. Aplicar filtros si el formulario es válido
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            
            if data.get('destinatario'):
                qs = qs.filter(destinatario=data['destinatario'])
            
            if data.get('estado'):
                qs = qs.filter(estado=data['estado'])
            
            if data.get('start_date'):
                qs = qs.filter(fecha_prestamo__gte=data['start_date'])

            if data.get('end_date'):
                # Incluir todo el día final
                end_date = data['end_date'] + datetime.timedelta(days=1)
                qs = qs.filter(fecha_prestamo__lt=end_date)
        
        return qs

    def get_context_data(self, **kwargs):
        """Inyecta el formulario y parámetros de paginación."""
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        # Preservar filtros al cambiar de página
        context['params'] = self.request.GET.urlencode()
        return context




class GestionarDevolucionView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, View):
    """
    Vista para gestionar devoluciones de préstamos.
    Descompone la lógica de devolución masiva en servicios
    transaccionales, optimiza queries y asegura la integridad del stock.
    """
    template_name = 'gestion_inventario/pages/gestionar_devolucion.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_prestamos"

    def get_prestamo_seguro(self, prestamo_id):
        """Obtiene el préstamo asegurando pertenencia a la estación."""
        return get_object_or_404(
            Prestamo.objects.select_related('destinatario', 'usuario_responsable'),
            id=prestamo_id,
            estacion_id=self.estacion_activa_id
        )


    def get(self, request, prestamo_id):
        prestamo = self.get_prestamo_seguro(prestamo_id)
        
        # Optimización: Traer detalles con productos relacionados
        items_prestados = prestamo.items_prestados.select_related(
            'activo__producto__producto_global', 
            'lote__producto__producto_global'
        ).order_by('id')

        # Cálculo en memoria para la UI
        for item in items_prestados:
            item.pendiente_real = item.cantidad_prestada - item.cantidad_devuelta - item.cantidad_extraviada

        context = {
            'prestamo': prestamo,
            'items_prestados': items_prestados
        }
        return render(request, self.template_name, context)

    def post(self, request, prestamo_id):
        prestamo = self.get_prestamo_seguro(prestamo_id)

        if prestamo.estado == Prestamo.EstadoPrestamo.COMPLETADO:
            messages.warning(request, "Este préstamo ya ha sido completado.")
            return redirect('gestion_inventario:ruta_gestionar_devolucion', prestamo_id=prestamo.id)

        try:
            with transaction.atomic():
                resultado = self._procesar_devoluciones(request, prestamo)
                
                if resultado['procesados'] > 0:
                    messages.success(request, f"Se registraron {resultado['procesados']} devoluciones correctamente.")
                else:
                    messages.warning(request, "No se registraron devoluciones (revise las cantidades).")

        except Exception as e:
            messages.error(request, f"Error al procesar devolución: {e}")

        return redirect('gestion_inventario:ruta_gestionar_devolucion', prestamo_id=prestamo.id)


    def _procesar_devoluciones(self, request, prestamo):
        """Orquesta la lógica de devolución de ítems."""
        items_prestados = prestamo.items_prestados.select_related('activo', 'lote').all()
        estado_disponible = Estado.objects.get(nombre='DISPONIBLE')
        
        movimientos_bulk = []
        items_actualizados_count = 0
        
        total_items_prestamo = len(items_prestados)
        total_items_completados = 0
        total_unidades_fisicas_devueltas = 0 # Contador para el log

        items_perdidos_count = 0
        ahora = timezone.now()

        for detalle in items_prestados:
            pendiente = detalle.cantidad_prestada - detalle.cantidad_devuelta - detalle.cantidad_extraviada
            if pendiente <= 0:
                total_items_completados += 1
                continue

            # 1. Capturar Inputs
            cant_devolver = int(request.POST.get(f'cantidad-devolver-{detalle.id}', 0))
            cant_perder = int(request.POST.get(f'cantidad-perder-{detalle.id}', 0)) # Nuevo input

            # Validaciones básicas
            suma_accion = cant_devolver + cant_perder
            if suma_accion <= 0:
                continue 
            
            if suma_accion > pendiente:
                # Error de validación: intentan devolver/perder más de lo que deben
                messages.warning(request, f"Error en {detalle}: La suma de devolución y pérdida excede lo pendiente.")
                continue

            hubo_cambios = False

            # PROCESAR DEVOLUCIÓN (Tu lógica existente)
            if cant_devolver > 0:
                detalle.cantidad_devuelta += cant_devolver
                movimiento = self._restaurar_stock(detalle, cant_devolver, estado_disponible, prestamo.id)
                movimientos_bulk.append(movimiento)
                total_unidades_fisicas_devueltas += cant_devolver
                hubo_cambios = True

            # PROCESAR PÉRDIDA (Nueva lógica integrada)
            if cant_perder > 0:
                detalle.cantidad_extraviada += cant_perder
                self._procesar_perdida_desde_prestamo(detalle, cant_perder, request.user)
                items_perdidos_count += cant_perder
                hubo_cambios = True

            # ACTUALIZACIÓN DE FECHA ULTIMOS CAMBIOS
            if hubo_cambios:
                detalle.fecha_ultima_devolucion = ahora

            # Actualizar Detalle
            detalle.save()
            items_actualizados_count += 1

            # Verificar si esta línea quedó saldada
            if detalle.esta_saldado:
                total_items_completados += 1


        # Guardar Movimientos en Lote (Eficiencia)
        if movimientos_bulk:
            MovimientoInventario.objects.bulk_create(movimientos_bulk)

        # Actualizar Estado del Préstamo
        self._actualizar_estado_prestamo(prestamo, total_items_completados, total_items_prestamo)

         # --- AUDITORÍA ---
        if total_unidades_fisicas_devueltas > 0:
            self.auditar(
                verbo=f"registró la devolución de {total_unidades_fisicas_devueltas} unidad(es) del Préstamo #{prestamo.id}",
                objetivo=prestamo.destinatario, # Quien devuelve
                objetivo_repr=f"Préstamo #{prestamo.id} - {prestamo.destinatario.nombre_entidad}",
                detalles={
                    'id_prestamo': prestamo.id,
                    'items_lineas_procesadas': items_actualizados_count,
                    'total_unidades': total_unidades_fisicas_devueltas,
                    'nuevo_estado_prestamo': prestamo.estado
                }
            )

        return {
            'procesados': total_unidades_fisicas_devueltas, 
            'perdidos': items_perdidos_count
        }


    def _restaurar_stock(self, detalle, cantidad, estado_disp, prestamo_id):
        """Restaura el stock (Activo o Lote) y retorna el objeto Movimiento (sin guardar)."""
        movimiento = MovimientoInventario(
            tipo_movimiento=TipoMovimiento.DEVOLUCION,
            usuario=self.request.user,
            estacion=self.estacion_activa,
            cantidad_movida=cantidad, # Positivo (Entrada)
            notas=f"Devolución Préstamo Folio #{prestamo_id}",
            fecha_hora=timezone.now()
        )

        if detalle.activo:
            activo = detalle.activo
            activo.estado = estado_disp
            activo.save(update_fields=['estado', 'updated_at'])
            
            movimiento.activo = activo
            movimiento.compartimento_destino = activo.compartimento
            # Nota: cantidad_movida para activos siempre es 1 en lógica, pero aquí usamos la recibida por consistencia

        elif detalle.lote:
            lote = detalle.lote
            lote.cantidad += cantidad
            lote.save(update_fields=['cantidad', 'updated_at'])
            
            movimiento.lote_insumo = lote
            movimiento.compartimento_destino = lote.compartimento

        return movimiento


    def _actualizar_estado_prestamo(self, prestamo, completados, total):
        """Calcula y guarda el nuevo estado del préstamo."""
        nuevo_estado = None
        if completados == total:
            nuevo_estado = Prestamo.EstadoPrestamo.COMPLETADO
        elif completados > 0 or any(i.cantidad_devuelta > 0 for i in prestamo.items_prestados.all()):
             # Si hay al menos algo devuelto (aunque no ítems completos), es parcial
             if prestamo.estado != Prestamo.EstadoPrestamo.DEVUELTO_PARCIAL:
                 nuevo_estado = Prestamo.EstadoPrestamo.DEVUELTO_PARCIAL
        
        if nuevo_estado:
            prestamo.estado = nuevo_estado
            prestamo.save(update_fields=['estado', 'updated_at'])

    
    def _procesar_perdida_desde_prestamo(self, detalle, cantidad, usuario):
        """
        Ejecuta la lógica de extravío (cambio de estado y movimiento) para un ítem prestado.
        """
        estado_extraviado = Estado.objects.get(nombre='EXTRAVIADO')
        compartimento_limbo = get_or_create_extraviado_compartment(self.estacion_activa) # Tu función helper
        
        # A. Si es Activo Serializado
        if detalle.activo:
            activo = detalle.activo
            activo.estado = estado_extraviado
            activo.compartimento = compartimento_limbo
            activo.save()
            
            # Movimiento de Ajuste (Cantidad 0 porque ya estaba fuera)
            MovimientoInventario.objects.create(
                tipo_movimiento=TipoMovimiento.AJUSTE,
                usuario=usuario,
                estacion=self.estacion_activa,
                compartimento_destino=compartimento_limbo,
                activo=activo,
                cantidad_movida=0, 
                notas=f"Reportado extraviado durante devolución de Préstamo #{detalle.prestamo.id}"
            )

        # B. Si es Lote (Insumo)
        elif detalle.lote:
            # Aquí NO cambiamos el estado del lote original (porque el lote original sigue en bodega)
            # Simplemente registramos que esas unidades prestadas "murieron" afuera.
            MovimientoInventario.objects.create(
                tipo_movimiento=TipoMovimiento.AJUSTE,
                usuario=usuario,
                estacion=self.estacion_activa,
                compartimento_destino=compartimento_limbo,
                lote_insumo=detalle.lote,
                cantidad_movida=0, # Igual es 0 porque salieron del stock prestado, no del físico
                notas=f"Reportado extraviado ({cantidad} u.) durante devolución de Préstamo #{detalle.prestamo.id}"
            )




class DestinatarioListView(BaseEstacionMixin, CustomPermissionRequiredMixin, ListView):
    """
    Vista para listar Destinatarios.
    Nivel Senior: Utiliza ListView genérica para manejar paginación estándar y
    BaseEstacionMixin para seguridad de contexto (filtro por estación activa).
    """
    model = Destinatario
    template_name = 'gestion_inventario/pages/lista_destinatarios.html'
    paginate_by = 25
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_prestamos"
    context_object_name = 'destinatarios'

    def get_queryset(self):
        """
        Construye el queryset:
        1. Filtra estrictamente por la estación activa.
        2. Aplica filtros de búsqueda (q) si existen.
        """
        # 1. Filtro Base de Seguridad (Usamos self.estacion_activa_id del mixin)
        qs = super().get_queryset().filter(
            estacion_id=self.estacion_activa_id
        ).order_by('nombre_entidad')

        # 2. Inicializamos el form aquí para usarlo en el filtro
        self.filter_form = DestinatarioFilterForm(self.request.GET)

        # 3. Lógica de Búsqueda
        if self.filter_form.is_valid():
            q = self.filter_form.cleaned_data.get('q')
            if q:
                qs = qs.filter(
                    Q(nombre_entidad__icontains=q) |
                    Q(rut_entidad__icontains=q) |
                    Q(nombre_contacto__icontains=q)
                )
        return qs

    def get_context_data(self, **kwargs):
        """
        Inyecta datos auxiliares al contexto.
        """
        context = super().get_context_data(**kwargs)
        
        # Pasamos el formulario para mantener el estado del input en el HTML
        context['filter_form'] = self.filter_form
        
        # Pasamos los parámetros GET para mantener el filtro al cambiar de página
        context['params'] = self.request.GET.urlencode()
        
        return context




class DestinatarioCreateView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, CreateView):
    """
    Vista para crear un nuevo destinatario.
    Implementa CreateView genérica, inyección automática de dependencias
    (estación/usuario) y manejo robusto de integridad referencial.
    """
    model = Destinatario
    form_class = DestinatarioForm
    template_name = 'gestion_inventario/pages/form_destinatario.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_prestamos"
    success_url = reverse_lazy('gestion_inventario:ruta_lista_destinatarios')

    def get_context_data(self, **kwargs):
        """Añade el título al contexto para reutilizar la plantilla."""
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Destinatario'
        return context

    def form_valid(self, form):
        """
        Asigna la estación activa y el usuario creador antes de persistir.
        """
        # Inyección de dependencias (BaseEstacionMixin garantiza self.estacion_activa)
        form.instance.estacion = self.estacion_activa
        form.instance.creado_por = self.request.user

        try:
            # super().form_valid() guarda el objeto y redirige
            response = super().form_valid(form)

            # --- AUDITORÍA ---
            self.auditar(
                verbo="registró una nueva entidad destinataria para préstamos",
                objetivo=self.object,
                detalles={
                    'nombre': self.object.nombre_entidad,
                    'rut': self.object.rut_entidad,
                    'contacto': self.object.nombre_contacto
                }
            )
            
            messages.success(
                self.request, 
                f"Destinatario '{self.object.nombre_entidad}' creado con éxito."
            )
            return response

        except IntegrityError:
            # Manejo de duplicados (unique_together: nombre + estacion)
            nombre = form.cleaned_data.get('nombre_entidad')
            messages.error(self.request, f"Ya existe un destinatario llamado '{nombre}' en esta estación.")
            form.add_error('nombre_entidad', 'Este nombre ya está en uso.')
            return self.form_invalid(form)
        
        except Exception as e:
            messages.error(self.request, f"Error inesperado al crear destinatario: {e}")
            return self.form_invalid(form)
        
    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error en el formulario. Por favor, revisa los datos ingresados.")
        return super().form_invalid(form)




class DestinatarioEditView(BaseEstacionMixin, CustomPermissionRequiredMixin, AuditoriaMixin, UpdateView):
    """
    Vista para editar un destinatario existente.
    Utiliza UpdateView para simplificar el ciclo de vida (GET/POST),
    asegurando la propiedad mediante filtrado de queryset y manejo robusto de errores.
    """
    model = Destinatario
    form_class = DestinatarioForm
    template_name = 'gestion_inventario/pages/form_destinatario.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_gestionar_prestamos"
    
    # Configuración para que UpdateView encuentre el objeto por 'destinatario_id'
    pk_url_kwarg = 'destinatario_id'
    context_object_name = 'destinatario'
    success_url = reverse_lazy('gestion_inventario:ruta_lista_destinatarios')

    def get_queryset(self):
        """
        Restringe la edición: Solo destinatarios que pertenecen a la estación activa.
        """
        return super().get_queryset().filter(estacion_id=self.estacion_activa_id)

    def get_context_data(self, **kwargs):
        """Añade el título dinámico al contexto."""
        context = super().get_context_data(**kwargs)
        context['titulo'] = f"Editar Destinatario: {self.object.nombre_entidad}"
        return context

    def form_valid(self, form):
        """
        Guarda los cambios manejando posibles conflictos de unicidad.
        """
        try:
            # 1. Guardamos primero para confirmar que la operación es válida en BD
            response = super().form_valid(form)
            
            # 2. --- AUDITORÍA CON DETECCIÓN DE CAMBIOS ---
            if form.changed_data:
                self.auditar(
                    verbo="actualizó los datos de la entidad destinataria",
                    objetivo=self.object,
                    detalles={
                        'campos_modificados': form.changed_data,
                        'nombre_actual': self.object.nombre_entidad
                    }
                )
            
            messages.success(
                self.request, 
                f"Destinatario '{self.object.nombre_entidad}' actualizado con éxito."
            )
            return response

        except IntegrityError:
            # Captura si el nuevo nombre entra en conflicto con otro existente en la misma estación
            nombre = form.cleaned_data.get('nombre_entidad')
            messages.error(self.request, f"Ya existe otro destinatario con el nombre '{nombre}'.")
            form.add_error('nombre_entidad', 'Este nombre ya está en uso.')
            return self.form_invalid(form)
            
        except Exception as e:
            messages.error(self.request, f"Error inesperado al actualizar: {e}")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Hubo un error en el formulario. Por favor, revisa los datos ingresados.")
        return super().form_invalid(form)




class MovimientoInventarioListView(BaseEstacionMixin, CustomPermissionRequiredMixin, ListView):
    """
    Vista de Historial de Movimientos.
    Implementa ListView genérica con filtrado dinámico avanzado,
    paginación automática y optimización de consultas SQL (select_related).
    """
    model = MovimientoInventario
    template_name = 'gestion_inventario/pages/historial_movimientos.html'
    context_object_name = 'movimientos'
    paginate_by = 50
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_historial_movimientos"

    def get_queryset(self):
        """
        Construye el queryset base filtrado por estación y optimizado.
        """
        qs = super().get_queryset().filter(
            estacion=self.estacion_activa
        ).select_related(
            'usuario', 
            'proveedor_origen', 
            'compartimento_origen__ubicacion', 
            'compartimento_destino__ubicacion', 
            'activo__producto__producto_global', 
            'lote_insumo__producto__producto_global'
        ).order_by('-fecha_hora')

        # Inicializar el formulario con GET params para filtrar
        self.filter_form = MovimientoFilterForm(self.request.GET, estacion=self.estacion_activa)
        
        if self.filter_form.is_valid():
            qs = self._apply_filters(qs, self.filter_form.cleaned_data)
            
        return qs

    def _apply_filters(self, qs, data):
        """Aplica filtros dinámicos al queryset."""
        q = data.get('q')
        if q:
            qs = qs.filter(
                Q(activo__producto__producto_global__nombre_oficial__icontains=q) |
                Q(lote_insumo__producto__producto_global__nombre_oficial__icontains=q) |
                Q(activo__codigo_activo__icontains=q) |
                Q(lote_insumo__codigo_lote__icontains=q) |
                Q(notas__icontains=q)
            ).distinct()

        if data.get('tipo_movimiento'):
            qs = qs.filter(tipo_movimiento=data['tipo_movimiento'])

        if data.get('usuario'):
            qs = qs.filter(usuario=data['usuario'])

        if data.get('fecha_inicio'):
            qs = qs.filter(fecha_hora__gte=data['fecha_inicio'])
        
        if data.get('fecha_fin'):
            # Ajuste para incluir el final del día si es fecha (no datetime)
            qs = qs.filter(fecha_hora__lte=data['fecha_fin'])
            
        return qs

    def get_context_data(self, **kwargs):
        """Inyecta el formulario de filtros al contexto."""
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        # Mantiene los filtros en la paginación
        context['params'] = self.request.GET.urlencode()
        return context




class GenerarQRView(BaseEstacionMixin, CustomPermissionRequiredMixin, View):
    """
    Genera un código QR dinámico en formato PNG.
    Nivel Senior: Implementa FileResponse para manejo eficiente de binarios
    y cabeceras HTTP de Cache-Control para reducir carga en el servidor.
    """
    permission_required = "gestion_usuarios.accion_gestion_inventario_ver_stock"
    
    def get(self, request, *args, **kwargs):
        codigo = kwargs.get('codigo')
        
        # 1. Validación de Entrada
        if not codigo:
            return HttpResponseBadRequest("Error: Código no proporcionado.")

        try:
            # 2. Configuración del QR (Optimizada)
            # box_size=10 genera una imagen de buen tamaño para impresión sin ser enorme
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M, # 'M' es mejor balance para lectura/daño
                box_size=10,
                border=2, # Borde más fino ahorra espacio
            )
            qr.add_data(codigo)
            qr.make(fit=True)

            # 3. Generación de Imagen en Memoria
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0) # Rebobinar el buffer para lectura

            # 4. Respuesta Optimizada (FileResponse + Caching)
            response = FileResponse(buffer, content_type="image/png")
            
            # HEADER CLAVE: Cachear por 1 año (31536000s). 
            # El QR de un código específico es inmutable; si el código cambia, la URL cambia.
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
            
            return response

        except Exception as e:
            # En caso de error en la librería qrcode
            return HttpResponseBadRequest(f"Error generando QR: {e}")




class ImprimirEtiquetasView(BaseEstacionMixin, CustomPermissionRequiredMixin, TemplateView):
    """
    Vista para imprimir etiquetas QR.
    Implementa TemplateView, maneja correctamente UUIDs en la URL
    y separa la lógica de filtrado (Directa vs Masiva).
    """
    template_name = 'gestion_inventario/pages/imprimir_etiquetas.html'
    permission_required = "gestion_usuarios.accion_gestion_inventario_imprimir_etiquetas_qr"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Detectar modo: ¿Vienen IDs en la URL?
        activos_ids_str = self.request.GET.get('activos')
        lotes_ids_str = self.request.GET.get('lotes')
        impresion_directa = bool(activos_ids_str or lotes_ids_str)

        if impresion_directa:
            context.update(self._get_impresion_directa(activos_ids_str, lotes_ids_str))
        else:
            context.update(self._get_impresion_masiva())

        context['impresion_directa'] = impresion_directa
        # Calculamos total sumando la longitud de los querysets ya obtenidos
        context['total_items'] = len(context['activos']) + len(context['lotes'])
        
        return context

    def _parse_uuids(self, id_string):
        """Convierte una cadena separada por comas en una lista de UUIDs válidos."""
        valid_uuids = []
        if not id_string:
            return valid_uuids
            
        for item in id_string.split(','):
            try:
                # Validamos si es un UUID real
                uuid_obj = uuid.UUID(item.strip())
                valid_uuids.append(uuid_obj)
            except ValueError:
                continue # Ignoramos basura en la URL
        return valid_uuids

    def _get_impresion_directa(self, activos_str, lotes_str):
        """Lógica para MODO 1: Imprimir IDs específicos."""
        activos_ids = self._parse_uuids(activos_str)
        lotes_ids = self._parse_uuids(lotes_str)

        activos_qs = Activo.objects.filter(
            estacion_id=self.estacion_activa_id,
            id__in=activos_ids
        ).select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).order_by('codigo_activo')

        lotes_qs = LoteInsumo.objects.filter(
            compartimento__ubicacion__estacion_id=self.estacion_activa_id,
            id__in=lotes_ids
        ).select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).order_by('codigo_lote')

        return {
            'activos': activos_qs,
            'lotes': lotes_qs,
            'filter_form': None
        }

    def _get_impresion_masiva(self):
        """Lógica para MODO 2: Filtrar stock existente."""
        # Filtro Base: Solo operativos
        activos_qs = Activo.objects.filter(
            estacion_id=self.estacion_activa_id
        ).exclude(estado__nombre__in=['ANULADO POR ERROR', 'DE BAJA', 'EXTRAVIADO'])
        
        lotes_qs = LoteInsumo.objects.filter(
            compartimento__ubicacion__estacion_id=self.estacion_activa_id,
            cantidad__gt=0
        ).exclude(estado__nombre__in=['ANULADO POR ERROR', 'DE BAJA', 'EXTRAVIADO'])

        # Aplicar Filtros de Formulario
        filter_form = EtiquetaFilterForm(self.request.GET, estacion=self.estacion_activa)
        
        if filter_form.is_valid():
            ubicacion = filter_form.cleaned_data.get('ubicacion')
            if ubicacion:
                activos_qs = activos_qs.filter(compartimento__ubicacion=ubicacion)
                lotes_qs = lotes_qs.filter(compartimento__ubicacion=ubicacion)

        # Optimización final
        activos_qs = activos_qs.select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).order_by('codigo_activo')
        
        lotes_qs = lotes_qs.select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).order_by('codigo_lote')

        return {
            'activos': activos_qs,
            'lotes': lotes_qs,
            'filter_form': filter_form
        }