import json
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from django.db.models import Count, Sum, Value, Q
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator

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
    Region,
    Comuna
    )
from .forms import (
    AreaForm, 
    CompartimentoForm, 
    ProductoGlobalForm, 
    ProductoLocalEditForm,
    ProveedorForm,
    ContactoProveedorForm
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




class AreaListaView(View):
    def get(self, request):
        estacion_id = request.session.get('active_estacion_id')

        # --- CONSULTA OPTIMIZADA ---
        # Usamos .annotate() para calcular todo en una sola consulta a la base de datos.
        ubicaciones_con_totales = (
            Ubicacion.objects
            .filter(estacion_id=estacion_id)
            .exclude(tipo_ubicacion__nombre__iexact='VEHÍCULO')
            .annotate(
                # 1. Contar el número de compartimentos por ubicación
                total_compartimentos=Count('compartimento', distinct=True),
                
                # 2. Contar el número de Activos únicos en los compartimentos de esta ubicación
                total_activos=Count('compartimento__activo', distinct=True),
                
                # 3. Sumar la CANTIDAD de todos los Lotes de Insumos en los compartimentos
                # Usamos Coalesce para que si no hay insumos, el resultado sea 0 en lugar de None
                total_cantidad_insumos=Coalesce(Sum('compartimento__loteinsumo__cantidad'), 0)
            )
            .select_related('tipo_ubicacion')
        )

        # --- CÁLCULO FINAL ---
        # Ahora iteramos sobre el resultado de la consulta (que ya tiene todos los datos)
        # para sumar los activos y los insumos en una sola variable.
        for ubicacion in ubicaciones_con_totales:
            ubicacion.total_existencias = ubicacion.total_activos + ubicacion.total_cantidad_insumos

        return render(
            request, 
            "gestion_inventario/pages/lista_areas.html", 
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




class AreaDetalleView(View):
    """Vista para gestionar un almacén/ubicación: mostrar imagen, nombre, descripción, fecha de creación y sus compartimentos."""
    def get(self, request, ubicacion_id):
        estacion_id = request.session.get('active_estacion_id')
        ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id, estacion_id=estacion_id)

        compartimentos = Compartimento.objects.filter(ubicacion=ubicacion)

        context = {
            'ubicacion': ubicacion,
            'compartimentos': compartimentos,
        }
        return render(request, 'gestion_inventario/pages/gestionar_area.html', context)




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
    """
    template_name = 'gestion_inventario/pages/lista_proveedores.html'
    paginate_by = 15

    def get(self, request, *args, **kwargs):
        search_query = request.GET.get('q', None)
        region_id_str = request.GET.get('region', None)
        comuna_id_str = request.GET.get('comuna', None)
        page_number = request.GET.get('page')

        # --- QUERYSET BASE CORREGIDO ---
        queryset = Proveedor.objects.select_related(
            # La ruta correcta para optimizar la consulta
            'contacto_principal__comuna__region' 
        ).annotate(
            contactos_count=Count('contactos')
        ).order_by('nombre')

        # --- LÓGICA DE FILTRADO CORREGIDA ---
        if search_query:
            queryset = queryset.filter(
                Q(nombre__icontains=search_query) |
                Q(rut__icontains=search_query.replace('-', '').replace('.', ''))
            )
        
        region_id = None
        if region_id_str and region_id_str.isdigit():
            region_id = int(region_id_str)
            # Filtra a través de la comuna del contacto principal
            queryset = queryset.filter(contacto_principal__comuna__region_id=region_id)

        comuna_id = None
        if comuna_id_str and comuna_id_str.isdigit():
            comuna_id = int(comuna_id_str)
            # Filtra por la comuna del contacto principal
            queryset = queryset.filter(contacto_principal__comuna_id=comuna_id)
        
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
            # ... (el resto de tu contexto se mantiene igual) ...
            'all_regiones': all_regiones,
            'comunas_para_filtro': comunas_para_filtro,
            'current_search': search_query or "",
            'current_region_id': region_id_str or "",
            'current_comuna_id': comuna_id_str or "",
        }
        
        return render(request, self.template_name, context)