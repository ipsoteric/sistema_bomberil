import json
import datetime
from itertools import chain
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from django.db import models
from django.db.models import Count, Sum, Value, Q, Subquery, OuterRef, Q
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin



from .models import (
    Estacion, 
    Ubicacion, 
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
    MovimientoInventario,
    TipoMovimiento
    )
from .forms import (
    AreaForm, 
    CompartimentoForm, 
    CompartimentoEditForm, 
    ProductoGlobalForm, 
    ProductoLocalEditForm,
    ProveedorForm,
    ContactoProveedorForm,
    RecepcionCabeceraForm,
    RecepcionDetalleFormSet,
    ActivoSimpleCreateForm,
    LoteInsumoSimpleCreateForm
    )
from .utils import generar_sku_sugerido
from core.settings import INVENTARIO_AREA_NOMBRE as AREA_NOMBRE


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
            .exclude(tipo_ubicacion__nombre__iexact='VEHÍCULO')
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

        # 2. Obtener compartimentos con sus totales de stock anotados
        compartimentos_con_stock = Compartimento.objects.filter(ubicacion=ubicacion).annotate(
            total_activos=Count('activo', distinct=True),
            total_cantidad_insumos=Coalesce(Sum('loteinsumo__cantidad'), 0)
        ).order_by('nombre')

        # 3. Calcular el resumen de stock total para el área (Tarjeta Izquierda)
        resumen_activos_area = 0
        resumen_insumos_area = 0
        for c in compartimentos_con_stock:
            c.total_existencias = c.total_activos + c.total_cantidad_insumos
            resumen_activos_area += c.total_activos
            resumen_insumos_area += c.total_cantidad_insumos
        
        resumen_total_area = resumen_activos_area + resumen_insumos_area

        # 4. Obtener la lista detallada de todo el stock en esta área
        activos_en_area = Activo.objects.filter(compartimento__ubicacion=ubicacion).select_related(
            'producto__producto_global', 'compartimento', 'estado'
        )
        lotes_en_area = LoteInsumo.objects.filter(compartimento__ubicacion=ubicacion).select_related(
            'producto__producto_global', 'compartimento'
        )

        stock_items_list = list(chain(activos_en_area, lotes_en_area))
        
        # 5. Ordenar la lista detallada (p.ej. por nombre de compartimento, luego por producto)
        stock_items_list.sort(key=lambda x: (x.compartimento.nombre, x.producto.producto_global.nombre_oficial))
        
        # 6. Preparar el contexto completo
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
            return redirect(reverse('gestion_inventario:ruta_gestionar_area', kwargs={'ubicacion_id': ubicacion.id}))
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
                                    estado_id=Estado.objects.get(nombre='DISPONIBLE', tipo_estado__nombre='OPERATIVO').id,
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
                                
                messages.success(request, "Recepción de stock guardada correctamente.")
                return redirect('gestion_inventario:ruta_stock_actual') # Redirige a la lista de stock

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