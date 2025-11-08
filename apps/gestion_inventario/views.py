import json
import datetime
from itertools import chain
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.db import models
from django.db.models import Count, Sum, Q, Subquery, OuterRef, Q, ProtectedError
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
import qrcode
import io



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
    VehiculoUbicacionCreateForm,
    VehiculoUbicacionEditForm,
    VehiculoDetalleEditForm,
    CompartimentoForm, 
    CompartimentoEditForm, 
    ProductoGlobalForm, 
    ProductoLocalEditForm,
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
    EtiquetaFilterForm
    )
from .utils import generar_sku_sugerido
from core.settings import INVENTARIO_AREA_NOMBRE as AREA_NOMBRE

from apps.gestion_usuarios.models import Membresia


class InventarioInicioView(View):
    def get(self, request):
        context = {
            'existencias':range(10),
            'proveedores':range(5),
        }
        return render(request, "gestion_inventario/pages/home.html", context)




class InventarioPruebasView(View):
    def get(self, request):
        return render(request, "gestion_inventario/pages/pruebas.html")




# Obtener total de existencias por categoría (VISTA TEMPORAL, DEBE MOVERSE A LA APP API)
def grafico_existencias_por_categoria(request):
    datos = (
        Activo.objects
        .values('catalogo__categoria__nombre')
        .annotate(score=Count('id'))
        .order_by('-score')
    )

    dataset = [['name', 'score']]
    for fila in datos:
        dataset.append([fila['catalogo__categoria__nombre'], fila['score']])

    return JsonResponse({'dataset': dataset})




class AreaListaView(LoginRequiredMixin, View):
    """
    Vista para listar las Áreas (Ubicaciones) de la estación activa,
    excluyendo vehículos y mostrando conteos optimizados.
    """
    template_name = "gestion_inventario/pages/lista_areas.html"
    login_url = '/acceso/login/'

    def get(self, request):
        estacion_id = request.session.get('active_estacion_id')

        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        # --- CONSULTA OPTIMIZADA ---
        # Usamos .annotate() para calcular todo en una sola consulta.
        ubicaciones_con_totales = (
            Ubicacion.objects
            .filter(estacion_id=estacion_id)
            .filter(tipo_ubicacion__nombre='ÁREA')
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

        # --- CÁLCULO FINAL (Tu lógica) ---
        # Iteramos para sumar los totales en una sola variable para la plantilla.
        for ubicacion in ubicaciones_con_totales:
            ubicacion.total_existencias = ubicacion.total_activos + ubicacion.total_cantidad_insumos

        return render(
            request, 
            self.template_name, 
            {'ubicaciones': ubicaciones_con_totales}
        )




class AreaCrearView(View):
    def get(self, request):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No tienes una estación activa. No puedes crear áreas.")
            return redirect(reverse('portal:ruta_inicio'))

        form = AreaForm()
        return render(request, 'gestion_inventario/pages/crear_area.html', {'formulario': form})

    def post(self, request):
        form = AreaForm(request.POST)
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No tienes una estación activa. No puedes crear areas.")
            return redirect(reverse('portal:ruta_inicio'))

        if form.is_valid():
            # Guardar sin confirmar para asignar tipo_ubicacion y potencialmente estacion desde sesión
            ubicacion = form.save(commit=False)

            # Obtener o crear el Tipoubicacion con nombre 'ÁREA' (mayúsculas para consistencia)
            tipo_ubicacion, created = TipoUbicacion.objects.get_or_create(nombre__iexact=AREA_NOMBRE, defaults={'nombre': AREA_NOMBRE})
            # Si get_or_create con lookup no funciona en el dialecto usado, fallback a get_or_create por nombre exacto
            if not tipo_ubicacion:
                tipo_ubicacion, created = TipoUbicacion.objects.get_or_create(nombre=AREA_NOMBRE)

            ubicacion.tipo_ubicacion = tipo_ubicacion

            # Si hay una estación activa en sesión, asignarla; si no, mantener la seleccionada en el formulario
            # Asignar la estación desde la sesión (usuario sólo puede crear para su compañía)
            try:
                estacion_obj = Estacion.objects.get(id=estacion_id)
                ubicacion.estacion = estacion_obj
            except Estacion.DoesNotExist:
                messages.error(request, "La estación activa en sesión no es válida.")
                return redirect(reverse('portal:ruta_inicio'))

            ubicacion.save()
            messages.success(request, f'Almacén/ubicación "{ubicacion.nombre.title()}" creado exitosamente.')
            # Redirigir a la lista de areas
            return redirect(reverse('gestion_inventario:ruta_lista_areas'))
        # Si hay errores, volver a mostrar el formulario con errores
        return render(request, 'gestion_inventario/pages/crear_area.html', {'formulario': form})




class UbicacionDetalleView(LoginRequiredMixin, View):
    """
    Vista para gestionar un área/ubicación: muestra detalles, 
    resúmenes de stock, lista de compartimentos con sus totales,
    y una lista detallada de todas las existencias en el área.
    """
    template_name = 'gestion_inventario/pages/gestionar_ubicacion.html'
    login_url = '/acceso/login/'

    def get(self, request, ubicacion_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        # 1. Obtener la Ubicación (genérica)
        ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id, estacion_id=estacion_id)

        # 2. Denegar acceso si es de tipo ADMINISTRATIVA
        if ubicacion.tipo_ubicacion.nombre == 'ADMINISTRATIVA':
            messages.error(request, "Esta ubicación es interna del sistema y no se puede gestionar.")
            return redirect('gestion_inventario:ruta_stock_actual')

        # 3. Obtener compartimentos con sus totales de stock anotados
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
        return render(request, self.template_name, context)




class UbicacionDeleteView(LoginRequiredMixin, View):
    """
    Vista para confirmar y ejecutar la eliminación de una Ubicación (Área o Vehículo).
    Maneja ProtectedError si la ubicación aún tiene compartimentos.
    """
    template_name = 'gestion_inventario/pages/eliminar_ubicacion.html'
    login_url = '/acceso/login/'

    def get(self, request, ubicacion_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        ubicacion = get_object_or_404(
            Ubicacion.objects.select_related('tipo_ubicacion'),
            id=ubicacion_id,
            estacion_id=estacion_id
        )
        
        context = { 'ubicacion': ubicacion }
        return render(request, self.template_name, context)

    def post(self, request, ubicacion_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        ubicacion = get_object_or_404(
            Ubicacion.objects.select_related('tipo_ubicacion'),
            id=ubicacion_id,
            estacion_id=estacion_id
        )
        
        # Guardamos el tipo y nombre antes de borrar
        tipo_nombre = ubicacion.tipo_ubicacion.nombre
        ubicacion_nombre = ubicacion.nombre
        
        try:
            # Intento de eliminación
            ubicacion.delete()
            
            messages.success(request, f"El {tipo_nombre.lower()} '{ubicacion_nombre}' ha sido eliminado exitosamente.")
            
            # Redirigir a la lista correspondiente
            if tipo_nombre == 'VEHÍCULO':
                return redirect('gestion_inventario:ruta_lista_vehiculos')
            else:
                return redirect('gestion_inventario:ruta_lista_areas')

        except ProtectedError:
            # Si falla (on_delete=PROTECT), capturamos el error
            messages.error(request, f"No se puede eliminar '{ubicacion_nombre}'. Asegúrese de que todos sus compartimentos (incluido 'General') estén vacíos y hayan sido eliminados primero.")
            # Devolvemos al usuario a la página de gestión
            return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion.id)
        
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")
            return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion.id)




class AreaEditarView(View):
    """Editar datos de una ubicación/almacén."""
    def get(self, request, ubicacion_id):
        ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
        form = CompartimentoForm.__module__  # placeholder to avoid unused import warnings
        from .forms import AreaEditForm
        form = AreaEditForm(instance=ubicacion)
        return render(request, 'gestion_inventario/pages/editar_area.html', {'formulario': form, 'ubicacion': ubicacion})

    def post(self, request, ubicacion_id):
        ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
        from .forms import AreaEditForm
        form = AreaEditForm(request.POST, request.FILES, instance=ubicacion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Almacén actualizado correctamente.')
            return redirect(reverse('gestion_inventario:ruta_gestionar_area', kwargs={'ubicacion_id': ubicacion.id}))
        return render(request, 'gestion_inventario/pages/editar_area.html', {'formulario': form, 'ubicacion': ubicacion})




class VehiculoListaView(LoginRequiredMixin, View):
    """
    Vista para listar los Vehículos (Ubicaciones de tipo 'VEHÍCULO')
    de la estación activa, mostrando conteos optimizados.
    """
    template_name = "gestion_inventario/pages/lista_vehiculos.html"
    login_url = '/acceso/login/'

    def get(self, request):
        estacion_id = request.session.get('active_estacion_id')

        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        # --- CONSULTA OPTIMIZADA PARA VEHÍCULOS ---
        vehiculos_con_totales = (
            Ubicacion.objects
            .filter(
                estacion_id=estacion_id,
                tipo_ubicacion__nombre__iexact='VEHÍCULO' # Filtro clave
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

        # Calculamos el total de existencias
        for vehiculo in vehiculos_con_totales:
            vehiculo.total_existencias = vehiculo.total_activos + vehiculo.total_cantidad_insumos

        return render(
            request, 
            self.template_name, 
            # Cambiamos el nombre del contexto para claridad en la plantilla
            {'vehiculos': vehiculos_con_totales} 
        )




class VehiculoCreateView(LoginRequiredMixin, View):
    """
    Vista para crear un nuevo Vehículo.
    Maneja la creación simultánea en los modelos Ubicacion y Vehiculo.
    """
    template_name = 'gestion_inventario/pages/crear_vehiculo.html'
    login_url = '/acceso/login/'

    def get(self, request, *args, **kwargs):
        # Instanciamos los formularios vacíos
        form_ubicacion = VehiculoUbicacionCreateForm()
        form_detalles = VehiculoDetalleEditForm() # Reutilizamos el form de edición
        
        context = {
            'form_ubicacion': form_ubicacion,
            'form_detalles': form_detalles,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        # Obtenemos los objetos fijos que necesitamos
        try:
            estacion_activa = Estacion.objects.get(id=estacion_id)
            tipo_vehiculo_obj = TipoUbicacion.objects.get(nombre='VEHÍCULO')
        except (Estacion.DoesNotExist, TipoUbicacion.DoesNotExist):
            messages.error(request, "Error de configuración: No se encontró la estación o el tipo 'VEHÍCULO'.")
            return redirect('gestion_inventario:ruta_lista_vehiculos') # O a la lista

        # Instanciamos formularios con los datos del POST
        form_ubicacion = VehiculoUbicacionCreateForm(request.POST)
        form_detalles = VehiculoDetalleEditForm(request.POST) # Reutilizamos el form

        if form_ubicacion.is_valid() and form_detalles.is_valid():
            try:
                # Usamos una transacción para asegurar que ambos se creen o ninguno
                with transaction.atomic():
                    # 1. Guardar la parte de Ubicacion (sin commit)
                    ubicacion_obj = form_ubicacion.save(commit=False)
                    # Asignar los campos faltantes
                    ubicacion_obj.estacion = estacion_activa
                    ubicacion_obj.tipo_ubicacion = tipo_vehiculo_obj
                    ubicacion_obj.save() # Guardar en la BD

                    # 2. Guardar la parte de Detalles (sin commit)
                    detalles_obj = form_detalles.save(commit=False)
                    # Asignar la relación OneToOne
                    detalles_obj.ubicacion = ubicacion_obj 
                    detalles_obj.save() # Guardar en la BD
                
                messages.success(request, f"Vehículo '{ubicacion_obj.nombre}' creado exitosamente.")
                # Redirigimos a la vista de gestión del nuevo vehículo
                return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion_obj.id)
            
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado al guardar: {e}")

        else:
            messages.error(request, "Hubo un error. Por favor, revisa los campos de ambos formularios.")
        
        context = {
            'form_ubicacion': form_ubicacion,
            'form_detalles': form_detalles,
        }
        return render(request, self.template_name, context)




class VehiculoEditView(LoginRequiredMixin, View):
    """
    Vista para editar los detalles de un Vehículo.
    Maneja dos formularios:
    1. VehiculoUbicacionEditForm (para el modelo Ubicacion)
    2. VehiculoDetalleEditForm (para el modelo Vehiculo)
    """
    template_name = 'gestion_inventario/pages/editar_vehiculo.html'
    login_url = '/acceso/login/'

    def get(self, request, ubicacion_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        # Obtenemos la Ubicacion (Vehículo)
        ubicacion = get_object_or_404(
            Ubicacion,
            id=ubicacion_id,
            estacion_id=estacion_id,
            tipo_ubicacion__nombre='VEHÍCULO'
        )
        
        # Obtenemos los detalles del vehículo (modelo Vehiculo)
        # Usamos try-except por si acaso se borró el registro hijo
        try:
            vehiculo_detalles = ubicacion.detalles_vehiculo
        except Vehiculo.DoesNotExist:
            vehiculo_detalles = None # El POST creará uno nuevo

        # Instanciamos ambos formularios
        form_ubicacion = VehiculoUbicacionEditForm(instance=ubicacion)
        form_detalles = VehiculoDetalleEditForm(instance=vehiculo_detalles)
        
        context = {
            'form_ubicacion': form_ubicacion,
            'form_detalles': form_detalles,
            'ubicacion': ubicacion
        }
        return render(request, self.template_name, context)

    def post(self, request, ubicacion_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        ubicacion = get_object_or_404(
            Ubicacion,
            id=ubicacion_id,
            estacion_id=estacion_id,
            tipo_ubicacion__nombre='VEHÍCULO'
        )
        
        try:
            vehiculo_detalles = ubicacion.detalles_vehiculo
        except Vehiculo.DoesNotExist:
            vehiculo_detalles = None

        # Instanciamos formularios con los datos del POST y los archivos
        form_ubicacion = VehiculoUbicacionEditForm(request.POST, request.FILES, instance=ubicacion)
        form_detalles = VehiculoDetalleEditForm(request.POST, instance=vehiculo_detalles)

        if form_ubicacion.is_valid() and form_detalles.is_valid():
            try:
                # Usamos una transacción para asegurar que ambos formularios se guarden
                with transaction.atomic():
                    # Guardamos el formulario de Ubicacion
                    form_ubicacion.save()
                    
                    # Guardamos el formulario de Detalles (sin commit)
                    detalles_obj = form_detalles.save(commit=False)
                    # Asignamos la relación OneToOne a la Ubicacion padre
                    detalles_obj.ubicacion = ubicacion 
                    detalles_obj.save()
                
                messages.success(request, f"El vehículo '{ubicacion.nombre}' se actualizó correctamente.")
                # Redirigimos de vuelta a la vista de gestión
                return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion.id)
            
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")

        else:
            messages.error(request, "Hubo un error. Por favor, revisa los campos de ambos formularios.")
        
        context = {
            'form_ubicacion': form_ubicacion,
            'form_detalles': form_detalles,
            'ubicacion': ubicacion
        }
        return render(request, self.template_name, context)




class CompartimentoListaView(View):
    """Lista potente de compartimentos con filtros y búsqueda."""
    def get(self, request):
        estacion_id = request.session.get('active_estacion_id')

        # Base queryset: todos los compartimentos pertenecientes a la estación
        qs = Compartimento.objects.select_related('ubicacion', 'ubicacion__tipo_ubicacion', 'ubicacion__estacion')
        if estacion_id:
            qs = qs.filter(ubicacion__estacion_id=estacion_id)

        # Filtros avanzados desde GET
        ubicacion_id = request.GET.get('ubicacion')
        nombre = request.GET.get('nombre')
        descripcion_presente = request.GET.get('descripcion_presente')  # '1' para solo con descripción

        if ubicacion_id:
            try:
                qs = qs.filter(ubicacion_id=int(ubicacion_id))
            except ValueError:
                pass

        if nombre:
            qs = qs.filter(nombre__icontains=nombre)

        if descripcion_presente == '1':
            qs = qs.exclude(descripcion__isnull=True).exclude(descripcion__exact='')

        # Orden por sección y nombre
        qs = qs.order_by('ubicacion__nombre', 'nombre')

        # Opciones para filtros
        ubicaciones = Ubicacion.objects.filter(estacion_id=estacion_id).order_by('nombre') if estacion_id else Ubicacion.objects.order_by('nombre')

        context = {
            'compartimentos': qs,
            'ubicaciones': ubicaciones,
        }
        return render(request, 'gestion_inventario/pages/lista_compartimentos.html', context)




class CompartimentoCrearView(View):
    """Crear un compartimento asociado a una ubicación (almacén)."""
    def get(self, request, ubicacion_id):
        form = CompartimentoForm()
        ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
        return render(request, 'gestion_inventario/pages/crear_compartimento.html', {'formulario': form, 'ubicacion': ubicacion})

    def post(self, request, ubicacion_id):
        ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
        form = CompartimentoForm(request.POST)
        if form.is_valid():
            compartimento = form.save(commit=False)
            compartimento.ubicacion = ubicacion
            compartimento.save()
            messages.success(request, f'Compartimento "{compartimento.nombre}" creado en {ubicacion.nombre}.')
            return redirect(reverse('gestion_inventario:ruta_gestionar_ubicacion', kwargs={'ubicacion_id': ubicacion.id}))
        return render(request, 'gestion_inventario/pages/crear_compartimento.html', {'formulario': form, 'ubicacion': ubicacion})




class CompartimentoDetalleView(LoginRequiredMixin, View):
    """
    Vista para ver el detalle de un compartimento: muestra detalles, 
    resúmenes de stock y una lista detallada de todas las 
    existencias en el compartimento.
    """
    template_name = 'gestion_inventario/pages/detalle_compartimento.html'
    login_url = '/acceso/login/'

    def get(self, request, compartimento_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        # 1. Obtener el Compartimento principal
        # Optimizamos la consulta trayendo la ubicación y su tipo de una vez
        try:
            compartimento = get_object_or_404(
                Compartimento.objects.select_related(
                    'ubicacion', 
                    'ubicacion__tipo_ubicacion'
                ),
                id=compartimento_id,
                ubicacion__estacion_id=estacion_id
            )
        except Compartimento.DoesNotExist:
            messages.error(request, "El compartimento no existe o no pertenece a su estación.")
            return redirect('gestion_inventario:ruta_lista_areas') # O a donde estimes

        # 2. Obtener la lista detallada de todo el stock (Activos y Lotes)
        activos_en_compartimento = Activo.objects.filter(compartimento=compartimento).select_related(
            'producto__producto_global', 'compartimento', 'estado'
        )
        lotes_en_compartimento = LoteInsumo.objects.filter(compartimento=compartimento).select_related(
            'producto__producto_global', 'compartimento'
        )

        stock_items_list = list(chain(activos_en_compartimento, lotes_en_compartimento))
        
        # 3. Ordenar la lista detallada (p.ej. por nombre de producto)
        stock_items_list.sort(key=lambda x: x.producto.producto_global.nombre_oficial)

        # 4. Calcular el resumen de stock para la tarjeta de información
        resumen_activos = activos_en_compartimento.count()
        resumen_insumos_obj = lotes_en_compartimento.aggregate(total=Coalesce(Sum('cantidad'), 0))
        resumen_insumos = resumen_insumos_obj['total']
        resumen_total = resumen_activos + resumen_insumos

        # 5. Preparar el contexto completo
        context = {
            'compartimento': compartimento,
            'stock_items': stock_items_list,       # Lista combinada para la tabla
            'resumen_activos': resumen_activos,
            'resumen_insumos': resumen_insumos,
            'resumen_total': resumen_total,
            'today': timezone.now().date(),
        }
        return render(request, self.template_name, context)




class CompartimentoEditView(LoginRequiredMixin, View):
    """
    Vista para editar los detalles de un compartimento (nombre, descripción, imagen).
    """
    template_name = 'gestion_inventario/pages/editar_compartimento.html'
    login_url = '/acceso/login/'

    def get(self, request, compartimento_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        # Obtenemos el compartimento asegurándonos que pertenece a la estación activa
        compartimento = get_object_or_404(
            Compartimento.objects.select_related('ubicacion'),
            id=compartimento_id,
            ubicacion__estacion_id=estacion_id
        )
        
        form = CompartimentoEditForm(instance=compartimento)
        
        context = {
            'form': form,
            'compartimento': compartimento
        }
        return render(request, self.template_name, context)

    def post(self, request, compartimento_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        compartimento = get_object_or_404(
            Compartimento.objects.select_related('ubicacion'),
            id=compartimento_id,
            ubicacion__estacion_id=estacion_id
        )

        form = CompartimentoEditForm(request.POST, request.FILES, instance=compartimento)

        if form.is_valid():
            form.save()
            messages.success(request, f"El compartimento '{compartimento.nombre}' se actualizó correctamente.")
            # Redirigimos de vuelta al detalle del compartimento
            return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=compartimento.id)
        
        messages.error(request, "Hubo un error al actualizar el compartimento. Por favor, revisa los campos.")
        context = {
            'form': form,
            'compartimento': compartimento
        }
        return render(request, self.template_name, context)




class CompartimentoDeleteView(LoginRequiredMixin, View):
    """
    Vista para confirmar y ejecutar la eliminación de un Compartimento.
    Maneja ProtectedError si el compartimento aún tiene existencias (Activos o Lotes).
    """
    template_name = 'gestion_inventario/pages/eliminar_compartimento.html'
    login_url = '/acceso/login/'

    def get(self, request, compartimento_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')
        
        compartimento = get_object_or_404(
            Compartimento.objects.select_related('ubicacion'),
            id=compartimento_id,
            ubicacion__estacion_id=estacion_id
        )
        
        context = { 'compartimento': compartimento }
        return render(request, self.template_name, context)

    def post(self, request, compartimento_id):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "No se ha seleccionado una estación activa.")
            return redirect('gestion_inventario:ruta_inicio')

        compartimento = get_object_or_404(
            Compartimento.objects.select_related('ubicacion'),
            id=compartimento_id,
            ubicacion__estacion_id=estacion_id
        )
        
        # Guardamos datos para la redirección y mensajes
        ubicacion_padre_id = compartimento.ubicacion.id
        compartimento_nombre = compartimento.nombre
        
        try:
            # Intento de eliminación
            compartimento.delete()
            
            messages.success(request, f"El compartimento '{compartimento_nombre}' ha sido eliminado exitosamente.")
            
            # Redirigir a la página de la ubicación padre
            return redirect('gestion_inventario:ruta_gestionar_ubicacion', ubicacion_id=ubicacion_padre_id)

        except ProtectedError:
            # Si falla (on_delete=PROTECT), capturamos el error
            messages.error(request, f"No se puede eliminar '{compartimento_nombre}'. Asegúrese de que el compartimento esté completamente vacío (sin Activos ni Lotes).")
            # Devolvemos al usuario a la página de detalle del compartimento
            return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=compartimento.id)
        
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")
            return redirect('gestion_inventario:ruta_detalle_compartimento', compartimento_id=compartimento.id)




class CatalogoGlobalListView(View):
    """
    Muestra el Catálogo Maestro Global de Productos con filtros avanzados
    de búsqueda, marca, categoría y asignación.
    """
    template_name = 'gestion_inventario/pages/catalogo_global.html'
    paginate_by = 12

    def get(self, request, *args, **kwargs):
        
        # 1. Obtener todos los parámetros de filtro de la URL
        search_query = request.GET.get('q', None)
        categoria_id_str = request.GET.get('categoria', None)
        marca_id_str = request.GET.get('marca', None)
        filtro_asignacion = request.GET.get('filtro', 'todos')
        
        view_mode = request.GET.get('view', 'gallery')
        page_number = request.GET.get('page')

        # 2. Empezar con el QuerySet base optimizado
        queryset = ProductoGlobal.objects.select_related(
            'marca', 
            'categoria'
        ).order_by('nombre_oficial')

        # 3. Aplicar filtros dinámicamente
        
        # Filtro de Búsqueda (q)
        if search_query:
            queryset = queryset.filter(
                Q(nombre_oficial__icontains=search_query) |
                Q(modelo__icontains=search_query) |
                Q(marca__nombre__icontains=search_query)
            )
        
        # Filtro de Categoría
        categoria_id = None
        if categoria_id_str and categoria_id_str.isdigit():
            categoria_id = int(categoria_id_str)
            queryset = queryset.filter(categoria_id=categoria_id)

        # Filtro de Marca
        marca_id = None
        if marca_id_str and marca_id_str.isdigit():
            marca_id = int(marca_id_str)
            queryset = queryset.filter(marca_id=marca_id)

        # Filtro de Asignación (el que ya tenías, mejorado)
        estacion_id = request.session.get('active_estacion_id')
        productos_locales_ids = set()
        if estacion_id:
            productos_locales_ids = set(
                Producto.objects.filter(estacion_id=estacion_id)
                .values_list('producto_global_id', flat=True)
            )
            
            if filtro_asignacion == 'no_asignados':
                queryset = queryset.exclude(id__in=productos_locales_ids)
            elif filtro_asignacion == 'asignados':
                queryset = queryset.filter(id__in=productos_locales_ids)
        
        # 4. Obtener datos para rellenar los <select> del formulario
        all_categorias = Categoria.objects.order_by('nombre')
        all_marcas = Marca.objects.order_by('nombre')

        # 5. Preparar parámetros para la paginación (para que conserve los filtros)
        params = request.GET.copy()
        if 'page' in params:
            del params['page']
        query_params = params.urlencode()

        # 6. Paginación Manual
        paginator = Paginator(queryset, self.paginate_by)
        page_obj = paginator.get_page(page_number)

        # 7. Construir el Contexto final
        context = {
            'productos': page_obj,
            'page_obj': page_obj,
            'paginator': paginator,
            'view_mode': view_mode,
            'query_params': query_params,
            'productos_locales_set': productos_locales_ids,
            
            # Contexto para los filtros
            'all_categorias': all_categorias,
            'all_marcas': all_marcas,
            'current_search': search_query or "",
            'current_categoria_id': categoria_id_str or "",
            'current_marca_id': marca_id_str or "",
            'current_filtro': filtro_asignacion,
        }
        
        return render(request, self.template_name, context)




# --- VISTA API 1: OBTENER DETALLES Y SKU ---
class ApiGetProductoGlobalSKU(View):
    """
    API (GET) para obtener los detalles de un ProductoGlobal y 
    generar un SKU sugerido para el modal.
    """
    def get(self, request, pk, *args, **kwargs):
        try:
            producto_global = ProductoGlobal.objects.select_related('categoria', 'marca').get(pk=pk)
            
            # Generar el SKU sugerido
            sku_sugerido = generar_sku_sugerido(producto_global)
            
            data = {
                'id': producto_global.id,
                'nombre_oficial': producto_global.nombre_oficial,
                'sku_sugerido': sku_sugerido,
            }
            return JsonResponse(data, status=200)
            
        except ProductoGlobal.DoesNotExist:
            return JsonResponse({'error': 'Producto no encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# --- VISTA API 2: CREAR EL PRODUCTO LOCAL ---
class ApiAnadirProductoLocal(View):
    """
    API (POST) para crear un nuevo registro de Producto (catálogo local)
    desde el modal del catálogo global.
    """
    def post(self, request, *args, **kwargs):
        try:
            # Obtener la estación activa
            estacion_id = request.session.get('active_estacion_id')
            if not estacion_id:
                return JsonResponse({'error': 'No hay una estación activa en la sesión.'}, status=403)
            
            estacion = Estacion.objects.get(pk=estacion_id)
            
            # Cargar datos del POST (que viene como JSON)
            data = json.loads(request.body)
            
            productoglobal_id = int(data.get('productoglobal_id'))
            sku = data.get('sku')
            es_serializado = bool(data.get('es_serializado'))
            es_expirable = bool(data.get('es_expirable'))
            
            # Validaciones básicas
            if not productoglobal_id or not sku:
                return JsonResponse({'error': 'Faltan datos (ID de producto o SKU).'}, status=400)
            
            producto_global = ProductoGlobal.objects.get(pk=productoglobal_id)
            
            # Crear el nuevo Producto local
            nuevo_producto = Producto.objects.create(
                producto_global=producto_global,
                estacion=estacion,
                sku=sku,
                es_serializado=es_serializado,
                es_expirable=es_expirable
                # Puedes añadir más campos aquí si los recopilas (costo, etc.)
            )
            
            return JsonResponse({
                'success': True, 
                'message': f'Producto "{nuevo_producto.producto_global.nombre_oficial}" añadido a tu estación.',
                'productoglobal_id': nuevo_producto.producto_global_id
            }, status=201)

        except ProductoGlobal.DoesNotExist:
            return JsonResponse({'error': 'El producto global no existe.'}, status=404)
        except Estacion.DoesNotExist:
            return JsonResponse({'error': 'La estación activa no es válida.'}, status=404)
        except IntegrityError:
            # Error de 'unique_together' (el producto ya fue añadido)
            return JsonResponse({'error': 'Este producto ya ha sido añadido a tu estación.'}, status=409)
        except Exception as e:
            return JsonResponse({'error': f'Error inesperado: {str(e)}'}, status=500)




class ProductoGlobalCrearView(View):
    template_name = 'gestion_inventario/pages/crear_producto_global.html'
    form_class = ProductoGlobalForm

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES)
        
        # --- LÓGICA PARA MANEJAR LA CREACIÓN DE MARCA ---
        marca_input = request.POST.get('marca')
        marca_obj = None

        if marca_input:
            # Si el valor NO es un número, significa que el usuario escribió una nueva marca
            if not marca_input.isdigit():
                try:
                    # Intenta obtener o crear la nueva marca
                    # Usamos .strip() para quitar espacios al inicio/final
                    marca_obj, created = Marca.objects.get_or_create(
                        nombre=marca_input.strip(), 
                        defaults={'descripcion': ''} # Puedes añadir valores por defecto si tu modelo Marca los necesita
                    )
                    if created:
                        messages.info(request, f'Se ha creado la nueva marca "{marca_obj.nombre}".')
                    
                    # MODIFICAMOS request.POST TEMPORALMENTE para que el form.is_valid() funcione
                    # Le decimos al formulario que use el ID de la marca recién creada/encontrada
                    post_data = request.POST.copy()
                    post_data['marca'] = str(marca_obj.id)
                    form = self.form_class(post_data, request.FILES) # Re-inicializamos el form con los datos modificados
                    
                except IntegrityError:
                    # Esto podría pasar si hay un 'unique=True' en Marca y algo falla
                    messages.error(request, f'Error al intentar crear la marca "{marca_input}". Ya existe o hubo un problema.')
                    return render(request, self.template_name, {'form': form})
                except Exception as e:
                    messages.error(request, f'Error inesperado al crear la marca: {e}')
                    return render(request, self.template_name, {'form': form})
            # Si era un número, el ModelForm lo manejará como un ID existente normalmente
        # --- FIN DE LA LÓGICA DE CREACIÓN DE MARCA ---

        if form.is_valid():
            try:
                # Ahora .save() funcionará porque el campo 'marca' tiene un ID válido
                nuevo_producto_global = form.save()
                messages.success(request, f'Producto Global "{nuevo_producto_global.nombre_oficial}" creado exitosamente.')
                return redirect('gestion_inventario:ruta_catalogo_global')
            
            except IntegrityError as e:
                # Captura errores de unicidad del ProductoGlobal
                messages.error(request, f'Error al guardar: Ya existe un producto con esa marca y modelo, o un genérico con ese nombre.')
            except Exception as e:
                messages.error(request, f'Ha ocurrido un error inesperado al guardar el producto: {e}')
        
        # Si el form no es válido (o si la creación de marca falló antes de re-inicializar)
        return render(request, self.template_name, {'form': form})




class ProductoLocalListView(View):
    """
    Muestra el Catálogo Local de Productos para la estación activa.
    Incluye filtros avanzados, ordenación y cambio de vista (galería/tabla).
    """
    template_name = 'gestion_inventario/pages/catalogo_local.html'
    paginate_by = 12 # Ajusta según prefieras

    def get(self, request, *args, **kwargs):
        
        # 1. Obtener la estación activa (CRÍTICO para esta vista)
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Debes tener una estación activa para ver el catálogo local.")
            # Redirige a donde el usuario selecciona su estación o al inicio
            return redirect('portal:ruta_inicio') # Ajusta esta URL si es necesario
            
        try:
            estacion = Estacion.objects.get(pk=estacion_id)
        except Estacion.DoesNotExist:
             messages.error(request, "La estación activa no es válida.")
             return redirect('portal:ruta_inicio') # Ajusta esta URL

        # 2. Obtener parámetros de filtro y ordenación
        search_query = request.GET.get('q', None)
        categoria_id_str = request.GET.get('categoria', None)
        marca_id_str = request.GET.get('marca', None)
        es_serializado_str = request.GET.get('serializado', None) # 'si', 'no', ''
        es_expirable_str = request.GET.get('expirable', None) # 'si', 'no', ''
        sort_by = request.GET.get('sort', 'fecha_desc') # Opciones: fecha_desc, fecha_asc, costo_desc, costo_asc
        
        view_mode = request.GET.get('view', 'gallery')
        page_number = request.GET.get('page')

        # 3. QuerySet base: Productos de la estación activa, optimizado
        queryset = Producto.objects.filter(
            estacion_id=estacion_id
        ).select_related(
            'producto_global__marca', 
            'producto_global__categoria'
        ).order_by('-created_at') # Orden por defecto

        # 4. Aplicar filtros dinámicamente
        if search_query:
            queryset = queryset.filter(
                Q(sku__icontains=search_query) |
                Q(producto_global__nombre_oficial__icontains=search_query) |
                Q(producto_global__modelo__icontains=search_query) |
                Q(producto_global__marca__nombre__icontains=search_query)
            )
        
        categoria_id = None
        if categoria_id_str and categoria_id_str.isdigit():
            categoria_id = int(categoria_id_str)
            queryset = queryset.filter(producto_global__categoria_id=categoria_id)

        marca_id = None
        if marca_id_str and marca_id_str.isdigit():
            marca_id = int(marca_id_str)
            queryset = queryset.filter(producto_global__marca_id=marca_id)
            
        if es_serializado_str == 'si':
            queryset = queryset.filter(es_serializado=True)
        elif es_serializado_str == 'no':
             queryset = queryset.filter(es_serializado=False)
             
        if es_expirable_str == 'si':
            queryset = queryset.filter(es_expirable=True)
        elif es_expirable_str == 'no':
             queryset = queryset.filter(es_expirable=False)

        # 5. Aplicar Ordenación
        if sort_by == 'fecha_asc':
            queryset = queryset.order_by('created_at')
        elif sort_by == 'costo_desc':
            queryset = queryset.order_by('-costo_compra', '-created_at') # '-created_at' como desempate
        elif sort_by == 'costo_asc':
            queryset = queryset.order_by('costo_compra', 'created_at')
        else: # Por defecto (fecha_desc)
            queryset = queryset.order_by('-created_at')

        # 6. Obtener datos para los <select> del formulario
        all_categorias = Categoria.objects.order_by('nombre')
        # Mostramos solo marcas que realmente estén en el catálogo local de esta estación
        marcas_en_catalogo_ids = queryset.exclude(
            producto_global__marca__isnull=True
        ).values_list(
            'producto_global__marca_id', flat=True
        ).distinct()
        all_marcas = Marca.objects.filter(id__in=marcas_en_catalogo_ids).order_by('nombre')

        # 7. Preparar parámetros para la paginación
        params = request.GET.copy()
        if 'page' in params:
            del params['page']
        query_params = params.urlencode()

        # 8. Paginación Manual
        paginator = Paginator(queryset, self.paginate_by)
        page_obj = paginator.get_page(page_number)

        # 9. Construir el Contexto final
        context = {
            'productos': page_obj,
            'page_obj': page_obj,
            'paginator': paginator,
            'view_mode': view_mode,
            'query_params': query_params,
            'estacion': estacion, # Pasamos la estación actual a la plantilla
            
            # Contexto para los filtros y ordenación
            'all_categorias': all_categorias,
            'all_marcas': all_marcas,
            'current_search': search_query or "",
            'current_categoria_id': categoria_id_str or "",
            'current_marca_id': marca_id_str or "",
            'current_serializado': es_serializado_str or "",
            'current_expirable': es_expirable_str or "",
            'current_sort': sort_by,
        }
        
        return render(request, self.template_name, context)




class ProductoLocalEditView(View):
    template_name = 'gestion_inventario/pages/editar_producto_local.html'
    form_class = ProductoLocalEditForm

    def dispatch(self, request, *args, **kwargs):
        """
        Verifica que haya una estación activa antes de proceder.
        """
        self.estacion_id = request.session.get('active_estacion_id')
        if not self.estacion_id:
            messages.error(request, "Debes tener una estación activa para editar productos locales.")
            return redirect('portal:ruta_inicio') # Ajusta si es necesario
        try:
            self.estacion = Estacion.objects.get(pk=self.estacion_id)
        except Estacion.DoesNotExist:
             messages.error(request, "La estación activa no es válida.")
             return redirect('portal:ruta_inicio')
             
        # Obtener el producto a editar, asegurándose que pertenezca a la estación activa
        self.producto = get_object_or_404(Producto, pk=kwargs['pk'], estacion_id=self.estacion_id)
        
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk, *args, **kwargs):
        """Muestra el formulario pre-rellenado."""
        
        # Verificar si existe inventario asociado para deshabilitar 'es_serializado'
        existe_inventario = Activo.objects.filter(producto=self.producto).exists() or \
                           LoteInsumo.objects.filter(producto=self.producto).exists()
        
        # Pasamos la instancia y los parámetros extra al formulario
        form = self.form_class(
            instance=self.producto, 
            estacion=self.estacion, 
            disable_es_serializado=existe_inventario
        )
        
        context = {
            'form': form,
            'producto': self.producto, # Pasamos el objeto para mostrar info en la plantilla
            'estacion': self.estacion
        }
        return render(request, self.template_name, context)

    def post(self, request, pk, *args, **kwargs):
        """Procesa el formulario enviado."""
        
        # Verificar si existe inventario asociado (igual que en GET)
        existe_inventario = Activo.objects.filter(producto=self.producto).exists() or \
                           LoteInsumo.objects.filter(producto=self.producto).exists()

        # Pasamos la instancia, datos POST/FILES y los parámetros extra al formulario
        form = self.form_class(
            request.POST, 
            request.FILES, 
            instance=self.producto, 
            estacion=self.estacion,
            disable_es_serializado=existe_inventario
        )
        
        if form.is_valid():
            try:
                producto_editado = form.save()
                messages.success(request, f'Producto "{producto_editado.producto_global.nombre_oficial}" actualizado correctamente.')
                # Redirigir de vuelta al catálogo local
                return redirect('gestion_inventario:ruta_catalogo_local')
            
            except IntegrityError:
                 messages.error(request, 'Error: Ya existe otro producto en tu estación con ese SKU.')
            except Exception as e:
                messages.error(request, f'Ha ocurrido un error inesperado: {e}')
        
        # Si el formulario no es válido, se vuelve a renderizar con los errores
        context = {
            'form': form,
            'producto': self.producto,
            'estacion': self.estacion
        }
        return render(request, self.template_name, context)




class ProveedorListView(View):
    """
    Muestra una lista paginada de todos los Proveedores globales.
    Permite filtrar por nombre/RUT, Región y Comuna.

    MODIFICADO: El filtro de ubicación (Región/Comuna) ahora busca en
    el Contacto Principal Y en todos los Contactos Personalizados.
    """
    template_name = 'gestion_inventario/pages/lista_proveedores.html'
    paginate_by = 15

    def get(self, request, *args, **kwargs):
        search_query = request.GET.get('q', None)
        region_id_str = request.GET.get('region', None)
        comuna_id_str = request.GET.get('comuna', None)
        page_number = request.GET.get('page')

        # --- SUBQUERY para contar TOTAL de contactos ---
        # Esto evita que los JOINS del filtro (más abajo) contaminen el conteo.
        total_contactos_subquery = ContactoProveedor.objects.filter(
            proveedor_id=OuterRef('pk')
        ).values('proveedor_id').annotate(
            c=Count('pk')
        ).values('c')

        # --- QUERYSET BASE MEJORADO ---
        queryset = Proveedor.objects.select_related(
            'contacto_principal__comuna__region'
        ).annotate(
            # Usamos Coalesce para asegurar 0 en lugar de None si no hay contactos
            contactos_count=Coalesce(
                Subquery(total_contactos_subquery, output_field=models.IntegerField()),
                0
            )
        ).order_by('nombre')

        # --- LÓGICA DE FILTRADO (Búsqueda por Nombre/RUT) ---
        if search_query:
            queryset = queryset.filter(
                Q(nombre__icontains=search_query) |
                Q(rut__icontains=search_query.replace('-', '').replace('.', ''))
            )
        
        # --- LÓGICA DE FILTRADO (Ubicación) ---
        
        # Creamos un objeto Q para los filtros de ubicación
        location_filters = Q()

        region_id = None
        if region_id_str and region_id_str.isdigit():
            region_id = int(region_id_str)
            # Filtra por región principal O región de contactos personalizados
            location_filters.add(
                Q(contacto_principal__comuna__region_id=region_id) |
                Q(contactos__comuna__region_id=region_id),
                Q.AND
            )

        comuna_id = None
        if comuna_id_str and comuna_id_str.isdigit():
            comuna_id = int(comuna_id_str)
            # Filtra por comuna principal O comuna de contactos personalizados
            location_filters.add(
                Q(contacto_principal__comuna_id=comuna_id) |
                Q(contactos__comuna_id=comuna_id),
                Q.AND
            )
        
        # Aplicamos los filtros de ubicación si existen
        if location_filters:
            # Usamos .distinct() para evitar duplicados si un proveedor
            # coincide tanto en el principal como en el personalizado.
            queryset = queryset.filter(location_filters).distinct()
        
        # ... (El resto de la vista: obtener datos para filtros, paginación y contexto se mantiene igual) ...
        all_regiones = Region.objects.order_by('nombre')
        comunas_para_filtro = Comuna.objects.none()
        if region_id:
            comunas_para_filtro = Comuna.objects.filter(region_id=region_id).order_by('nombre')
        
        params = request.GET.copy()
        if 'page' in params:
            del params['page']
        query_params = params.urlencode()
        
        paginator = Paginator(queryset, self.paginate_by)
        page_obj = paginator.get_page(page_number)
        
        context = {
            'proveedores': page_obj,
            'page_obj': page_obj,
            'all_regiones': all_regiones,
            'comunas_para_filtro': comunas_para_filtro,
            'current_search': search_query or "",
            'current_region_id': region_id_str or "",
            'current_comuna_id': comuna_id_str or "",
        }
        
        return render(request, self.template_name, context)




class ProveedorCrearView(View):
    template_name = 'gestion_inventario/pages/crear_proveedor.html'

    def get(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Debes tener una estación activa para crear proveedores.")
            return redirect('portal:ruta_inicio')

        proveedor_form = ProveedorForm()
        contacto_form = ContactoProveedorForm()
        
        context = {
            'proveedor_form': proveedor_form,
            'contacto_form': contacto_form
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Tu sesión ha expirado o no tienes una estación activa.")
            return redirect('portal:ruta_inicio')
            
        estacion = get_object_or_404(Estacion, pk=estacion_id)

        proveedor_form = ProveedorForm(request.POST)
        contacto_form = ContactoProveedorForm(request.POST)

        if proveedor_form.is_valid() and contacto_form.is_valid():
            try:
                # Usamos una transacción para asegurar que todo se guarde o nada se guarde.
                with transaction.atomic():
                    # 1. Guardar el Proveedor
                    proveedor = proveedor_form.save(commit=False)
                    proveedor.estacion_creadora = estacion
                    proveedor.save()

                    # 2. Guardar el Contacto y vincularlo al Proveedor
                    contacto = contacto_form.save(commit=False)
                    contacto.proveedor = proveedor
                    contacto.save()

                    # 3. Actualizar el Proveedor para asignarle su Contacto Principal
                    proveedor.contacto_principal = contacto
                    proveedor.save()
                
                messages.success(request, f'Proveedor "{proveedor.nombre}" y su contacto principal han sido creados exitosamente.')
                return redirect('gestion_inventario:ruta_lista_proveedores')

            except IntegrityError as e:
                print(e)
                messages.error(request, 'Error: Ya existe un proveedor con ese RUT.')
            except Exception as e:
                messages.error(request, f'Ha ocurrido un error inesperado: {e}')

        # Si algún formulario no es válido, volvemos a mostrar la página con los errores
        context = {
            'proveedor_form': proveedor_form,
            'contacto_form': contacto_form
        }
        return render(request, self.template_name, context)




class ProveedorDetalleView(View):
    """
    Muestra el detalle de un Proveedor, separando el contacto principal (global)
    de los contactos personalizados por estación.
    """
    template_name = 'gestion_inventario/pages/detalle_proveedor.html'

    def get(self, request, *args, **kwargs):
        proveedor_id = self.kwargs.get('pk')
        estacion_id = request.session.get('active_estacion_id')

        try:
            # Obtenemos el proveedor y precargamos sus relaciones principales
            proveedor = Proveedor.objects.select_related(
                'contacto_principal__comuna__region', 
                'estacion_creadora' # Asumo que Estacion no necesita más joins
            ).get(pk=proveedor_id)
        
        except Proveedor.DoesNotExist:
            messages.error(request, "El proveedor solicitado no existe.")
            return redirect('gestion_inventario:ruta_lista_proveedores')

        # 1. Obtenemos el Contacto Principal (Global)
        contacto_principal = proveedor.contacto_principal

        # 2. Buscamos si la estación activa tiene un contacto personalizado
        # Asumo que el modelo ContactoProveedor tiene un campo FK a Estacion
        # llamado 'estacion_personalizada' (que puede ser Null).
        contacto_estacion_actual = None
        if estacion_id:
            try:
                contacto_estacion_actual = ContactoProveedor.objects.select_related('comuna__region').get(
                    proveedor=proveedor,
                    estacion_especifica=estacion_id
                )
            except ContactoProveedor.DoesNotExist:
                contacto_estacion_actual = None

        # 3. Obtenemos la lista de "otros" contactos personalizados
        # Es decir, todos los que tienen una estación asignada, excluyendo
        # el de la estación actual (si existe) para no mostrarlo duplicado.
        query_otros_contactos = ContactoProveedor.objects.filter(
            proveedor=proveedor,
            estacion_especifica__isnull=False
        ).select_related('estacion_especifica', 'comuna__region')

        if contacto_estacion_actual:
            query_otros_contactos = query_otros_contactos.exclude(pk=contacto_estacion_actual.pk)

        # 4. Determinamos permisos
        # Solo la estación creadora puede editar la info "global"
        es_estacion_creadora = (estacion_id == proveedor.estacion_creadora_id)

        context = {
            'proveedor': proveedor,
            'contacto_principal': contacto_principal,
            'contacto_estacion_actual': contacto_estacion_actual, # El de la sesión
            'otros_contactos_personalizados': query_otros_contactos,
            'es_estacion_creadora': es_estacion_creadora,
            'active_estacion_id': estacion_id, # Para saber si hay sesión activa
        }

        return render(request, self.template_name, context)




class ContactoPersonalizadoCrearView(View):
    """
    Permite a una estación activa crear un ContactoProveedor específico
    (un 'ContactoPersonalizado') para un Proveedor existente.
    """
    template_name = 'gestion_inventario/pages/crear_contacto_personalizado.html'

    def get(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Debes tener una estación activa para esta acción.")
            return redirect('gestion_inventario:ruta_lista_proveedores')

        proveedor_id = self.kwargs.get('proveedor_pk')
        proveedor = get_object_or_404(Proveedor, pk=proveedor_id)

        # --- Validación clave ---
        # Verificamos si ya existe un contacto para esta estación y este proveedor
        existe_ya = ContactoProveedor.objects.filter(
            proveedor=proveedor,
            estacion_especifica_id=estacion_id
        ).exists()

        if existe_ya:
            messages.warning(request, f"Tu estación ya tiene un contacto personalizado para {proveedor.nombre}. Serás redirigido para editarlo.")
            # (Opcional: Redirigir a la vista de EDICIÓN cuando exista)
            # Por ahora, lo devolvemos al detalle.
            return redirect('gestion_inventario:ruta_detalle_proveedor', pk=proveedor_id)

        # Si no existe, preparamos el formulario
        contacto_form = ContactoProveedorForm()
        
        context = {
            'contacto_form': contacto_form,
            'proveedor': proveedor
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            messages.error(request, "Tu sesión ha expirado o no tienes una estación activa.")
            return redirect('gestion_inventario:ruta_lista_proveedores')

        proveedor_id = self.kwargs.get('proveedor_pk')
        proveedor = get_object_or_404(Proveedor, pk=proveedor_id)
        estacion_actual = get_object_or_404(Estacion, pk=estacion_id)

        # Repetimos la validación por seguridad en el POST
        existe_ya = ContactoProveedor.objects.filter(
            proveedor=proveedor,
            estacion_especifica=estacion_actual
        ).exists()

        if existe_ya:
            messages.error(request, "Error: Ya existe un contacto personalizado para este proveedor.")
            return redirect('gestion_inventario:ruta_detalle_proveedor', pk=proveedor_id)

        # Procesamos el formulario
        contacto_form = ContactoProveedorForm(request.POST)

        if contacto_form.is_valid():
            try:
                contacto = contacto_form.save(commit=False)
                
                # --- Asignación de claves foráneas ---
                # El formulario no los pide, los asignamos desde el contexto
                contacto.proveedor = proveedor
                contacto.estacion_especifica = estacion_actual
                
                contacto.save()
                
                messages.success(request, f'Se ha creado el contacto "{contacto.nombre_contacto}" para tu estación.')
                return redirect('gestion_inventario:ruta_detalle_proveedor', pk=proveedor.pk)
            
            except Exception as e:
                messages.error(request, f'Ha ocurrido un error inesperado: {e}')
        
        # Si el formulario no es válido, volvemos a mostrar la página con errores
        context = {
            'contacto_form': contacto_form,
            'proveedor': proveedor
        }
        return render(request, self.template_name, context)




class ContactoPersonalizadoEditarView(View):
    """
    Permite a una estación activa editar SU PROPIO ContactoProveedor
    específico (su 'ContactoPersonalizado').
    """
    template_name = 'gestion_inventario/pages/editar_contacto_personalizado.html'

    def get_objeto_seguro(self, request, pk_contacto):
        """
        Método helper para obtener el contacto, asegurando que pertenezca
        a la estación activa.
        """
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            return None, redirect('gestion_inventario:ruta_lista_proveedores')

        try:
            # --- Validación clave de seguridad ---
            # Obtenemos el contacto SÓLO SI el pk coincide Y
            # la estacion_especifica coincide con la estación activa.
            contacto = ContactoProveedor.objects.select_related(
                'proveedor', 'comuna__region'
            ).get(
                pk=pk_contacto,
                estacion_especifica_id=estacion_id
            )
            return contacto, None
        
        except ContactoProveedor.DoesNotExist:
            messages.error(request, "El contacto no existe o no tienes permiso para editarlo.")
            # Si el contacto no existe, no podemos saber de qué proveedor era,
            # así que redirigimos a la lista general.
            return None, redirect('gestion_inventario:ruta_lista_proveedores')

    def get(self, request, *args, **kwargs):
        pk_contacto = self.kwargs.get('pk')
        contacto_a_editar, error_redirect = self.get_objeto_seguro(request, pk_contacto)
        
        if error_redirect:
            return error_redirect
        
        # --- Pre-poblar el formulario ---
        # Pasamos 'instance' para que el formulario se cargue con datos.
        contacto_form = ContactoProveedorForm(instance=contacto_a_editar)

        # --- Lógica para pre-seleccionar la Región ---
        # El campo 'region' no está en el modelo, así que lo seteamos manualmente.
        if contacto_a_editar.comuna:
            # Seteamos el valor inicial del campo 'region'
            contacto_form.fields['region'].initial = contacto_a_editar.comuna.region_id
            
            # El __init__ del form ya maneja poblar el queryset de comunas
            # si 'instance' es proveído.
            
        
        context = {
            'contacto_form': contacto_form,
            'proveedor': contacto_a_editar.proveedor,
            'contacto': contacto_a_editar # Para el título o breadcrumbs
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        pk_contacto = self.kwargs.get('pk')
        contacto_a_editar, error_redirect = self.get_objeto_seguro(request, pk_contacto)

        if error_redirect:
            return error_redirect
        
        # Pasamos 'instance' Y 'request.POST' para procesar la actualización
        contacto_form = ContactoProveedorForm(request.POST, instance=contacto_a_editar)

        if contacto_form.is_valid():
            try:
                # No necesitamos asignar proveedor ni estación,
                # 'instance' se encarga de que estemos actualizando el correcto.
                contacto_form.save()
                
                messages.success(request, f'Se ha actualizado el contacto "{contacto_a_editar.nombre_contacto}".')
                # Devolvemos al usuario al detalle del proveedor
                return redirect('gestion_inventario:ruta_detalle_proveedor', pk=contacto_a_editar.proveedor_id)
            
            except Exception as e:
                messages.error(request, f'Ha ocurrido un error inesperado: {e}')
        
        # Si el formulario no es válido, volvemos a mostrar la página con errores
        context = {
            'contacto_form': contacto_form,
            'proveedor': contacto_a_editar.proveedor,
            'contacto': contacto_a_editar
        }
        return render(request, self.template_name, context)




class StockActualListView(LoginRequiredMixin, View):
    """
    Vista para mostrar, filtrar y buscar en el stock actual
    de Activos (serializados) y Lotes de Insumo (fungibles).
    """
    template_name = 'gestion_inventario/pages/stock_actual.html'
    login_url = '/acceso/login/' # Ajusta si es necesario
    paginate_by = 25

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
        sort_by = request.GET.get('sort', 'fecha_desc')

        # 3. Obtener querysets base, filtrados por la ESTACIÓN ACTIVA
        activos_qs = Activo.objects.filter(estacion=estacion_usuario).select_related(
            'producto__producto_global', 'compartimento__ubicacion', 'estado'
        ).all()
        
        lotes_qs = LoteInsumo.objects.filter(producto__estacion=estacion_usuario).select_related(
            'producto__producto_global', 'compartimento__ubicacion'
        ).all()

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
        reverse_sort = sort_by.endswith('_desc') 
        sort_field = sort_by.replace('_desc', '').replace('_asc', '')

        if sort_field == 'fecha':
            # Usa una fecha por defecto para manejar valores None
            default_date = datetime.date.min if reverse_sort else datetime.date.max 
            stock_items_list.sort(key=lambda x: getattr(x, 'fecha_recepcion', default_date) or default_date, reverse=reverse_sort)
        elif sort_field == 'nombre': # Añadido orden por nombre
             stock_items_list.sort(key=lambda x: x.producto.producto_global.nombre_oficial, reverse=reverse_sort)
        # else: # Orden por defecto (fecha desc) ya aplicado arriba si sort_field == 'fecha'
             # Si no es fecha ni nombre, podrías ordenar por nombre como fallback
             # stock_items_list.sort(key=lambda x: x.producto.producto_global.nombre_oficial)

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
            'stock_items': page_obj.object_list,
            'todas_las_ubicaciones': Ubicacion.objects.filter(estacion=estacion_usuario),
            'todos_los_estados': Estado.objects.all(),
            'current_q': query,
            'current_tipo': tipo_producto,
            'current_ubicacion': ubicacion_id,
            'current_estado': estado_id,
            'current_fecha_desde': fecha_desde,
            'current_fecha_hasta': fecha_hasta,
            'current_sort': sort_by,
            'today': timezone.now().date() # Mantenido para lógica de vencimiento
        }
        
        return render(request, self.template_name, context)




class RecepcionStockView(LoginRequiredMixin, View):
    template_name = 'gestion_inventario/pages/recepcion_stock.html'
    login_url = '/acceso/login/'

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




class AgregarStockACompartimentoView(LoginRequiredMixin, View):
    """
    Vista para añadir stock (Activos o Lotes) directamente
    a un compartimento específico.
    """
    template_name = 'gestion_inventario/pages/agregar_stock_compartimento.html'
    login_url = '/acceso/login/'

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




class AnularExistenciaView(LoginRequiredMixin, View):
    """
    Vista para anular un registro de existencia (Activo o LoteInsumo)
    que fue ingresado por error.
    """
    template_name = 'gestion_inventario/pages/anular_existencia.html'
    login_url = '/acceso/login/'

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




class AjustarStockLoteView(LoginRequiredMixin, View):
    """
    Vista para ajustar la cantidad de un LoteInsumo y crear
    un MovimientoInventario de tipo AJUSTE.
    """
    template_name = 'gestion_inventario/pages/ajustar_stock_lote.html'
    login_url = '/acceso/login/'

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




class BajaExistenciaView(LoginRequiredMixin, View):
    """
    Vista para Dar de Baja una existencia (Activo o LoteInsumo),
    cambiando su estado y generando un movimiento de SALIDA.
    """
    template_name = 'gestion_inventario/pages/dar_de_baja_existencia.html'
    login_url = '/acceso/login/'

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




class ExtraviadoExistenciaView(LoginRequiredMixin, View):
    """
    Vista para reportar una existencia como Extraviada (Activo o LoteInsumo),
    cambiando su estado, moviéndola al limbo y generando un movimiento de SALIDA.
    """
    template_name = 'gestion_inventario/pages/extraviado_existencia.html'
    login_url = '/acceso/login/'

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




class ConsumirStockLoteView(LoginRequiredMixin, View):
    """
    Vista para consumir una cantidad de un LoteInsumo y crear
    un MovimientoInventario de tipo SALIDA.
    """
    template_name = 'gestion_inventario/pages/consumir_stock_lote.html'
    login_url = '/acceso/login/'

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




class TransferenciaExistenciaView(LoginRequiredMixin, View):
    """
    Mueve una existencia (Activo o Lote) de un compartimento a otro
    dentro de la misma estación, generando un movimiento de TRANSFERENCIA_INTERNA.
    """
    template_name = 'gestion_inventario/pages/transferir_existencia.html'
    login_url = '/acceso/login/'

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




class CrearPrestamoView(LoginRequiredMixin, View):
    """
    Vista para crear un Préstamo (Cabecera y Detalles)
    usando un flujo de "scan-first".
    """
    template_name = 'gestion_inventario/pages/crear_prestamo.html'
    login_url = '/acceso/login/'

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




class BuscarItemPrestamoJson(LoginRequiredMixin, View):
    """
    API endpoint (solo GET) para buscar un ítem por su código
    y verificar si está disponible para préstamo.
    """
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




class HistorialPrestamosView(LoginRequiredMixin, View):
    """
    Vista (basada en View) para mostrar el historial de préstamos externos
    de la estación activa del usuario.
    """
    template_name = 'gestion_inventario/pages/historial_prestamos.html'
    paginate_by = 25

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




class MovimientoInventarioListView(LoginRequiredMixin, View):
    """
    Muestra una lista paginada y filtrable de todos los 
    movimientos de inventario de la estación activa.
    """
    template_name = 'gestion_inventario/pages/historial_movimientos.html'
    login_url = '/acceso/login/'
    paginate_by = 50 # 50 movimientos por página

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




class GenerarQRView(View):
    """
    Esta vista no renderiza HTML.
    Genera una imagen QR basada en el 'codigo' proporcionado
    y la devuelve como una respuesta de imagen PNG.
    """
    
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




class ImprimirEtiquetasView(LoginRequiredMixin, View):
    """
    Muestra una página diseñada para imprimir etiquetas QR
    para Activos y Lotes.
    
    Maneja dos modos:
    1. Específico: Recibe IDs por GET (ej: ?activos=1,2&lotes=3)
    2. Masivo: Muestra filtros para seleccionar qué imprimir
    """
    template_name = 'gestion_inventario/pages/imprimir_etiquetas.html'
    login_url = '/acceso/login/'

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