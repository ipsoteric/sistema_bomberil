import uuid
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from PIL import Image

from apps.gestion_usuarios.models import Usuario, Membresia
from apps.common.permissions import CanUpdateUserProfile
from apps.common.utils import procesar_imagen_en_memoria, generar_thumbnail_en_memoria
from apps.common.mixins import AuditoriaMixin
from apps.gestion_inventario.models import Comuna, Activo, LoteInsumo, ProductoGlobal, Estacion, Producto
from apps.gestion_inventario.utils import generar_sku_sugerido
from .serializers import ComunaSerializer, ProductoLocalInputSerializer
from .permissions import IsStationActiveAndHasPermission



class BuscarUsuarioAPIView(APIView):
    """
    Busca un usuario por su RUT
    y devuelve su estado de membresía.
    """

    permission_classes = [IsAuthenticated]


    def post(self, request, *args, **kwargs):
        rut_recibido = request.data.get('rut')

        if not isinstance(rut_recibido, str):
            print("El formato del RUT es inválido. Se esperaba un string")
            return Response(
                {'error': 'El formato del RUT es inválido. Se esperaba un string.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rut = rut_recibido.strip()

        if not rut:
            return Response(
                {'error': 'El RUT es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 1. Buscamos al usuario por su RUT
            usuario = Usuario.objects.get(rut=rut)
            
            # 2. Intentamos OBTENER la membresía activa para acceder a sus datos
            membresia_no_disponible = Membresia.objects.select_related('estacion', 'usuario').filter(usuario=usuario, estado__in=['ACTIVO', 'INACTIVO']).first()

            if membresia_no_disponible:
                # El usuario existe y ya está activo en alguna parte.
                # CONSTRUIMOS la respuesta con los datos solicitados.
                return Response({
                    'status': 'EXISTE_ACTIVO',
                    'mensaje': f'El usuario {usuario.get_full_name.title()} ya tiene una membresía activa.',
                    'membresia': {
                        'nombre_completo': usuario.get_full_name.title(),
                        'email': usuario.email,
                        'estacion': membresia_no_disponible.estacion.nombre,
                        'fecha_inicio': membresia_no_disponible.fecha_inicio.strftime('%d-%m-%Y'), # Formateamos la fecha
                        'estado': membresia_no_disponible.get_estado_display() # Muestra el "label" legible del ChoiceField
                    }
                })
            else:
                # El usuario existe y está disponible para ser agregado
                return Response({
                    'status': 'EXISTE_DISPONIBLE',
                    'mensaje': f'Usuario {usuario.get_full_name.title()} encontrado. Puede ser agregado a esta compañía.',
                    'usuario': {
                        'id': usuario.id,
                        'nombre_completo': usuario.get_full_name.title(),
                        'rut': usuario.rut,
                        'email': usuario.email
                    }
                })

        except Usuario.DoesNotExist:
            # 3. El usuario no existe en todo el sistema
            return Response({
                'status': 'NO_EXISTE',
                'mensaje': 'Usuario no encontrado. Puede crearlo y asignarlo a la compañía.'
            })



def alternar_tema_oscuro(request):
    current = request.session.get('dark_mode', False)
    request.session['dark_mode'] = not current
    return redirect(request.META.get('HTTP_REFERER', '/'))



class ActualizarAvatarUsuarioView(APIView):
    permission_classes = [IsAuthenticated, CanUpdateUserProfile]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, id, format=None):
        usuario = get_object_or_404(Usuario, pk=id)
        self.check_object_permissions(request, usuario)

        nuevo_avatar_file = request.FILES.get('nuevo_avatar')

        if not nuevo_avatar_file:
            return Response(
                {'error': 'No se proporcionó ningún archivo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # --- 1. Guardar referencias a los archivos antiguos ---
            old_avatar = usuario.avatar
            old_thumb_small = usuario.avatar_thumb_small
            old_thumb_medium = usuario.avatar_thumb_medium

            # --- 2. Generar nombres de archivo únicos con UUID ---
            # Forzamos .jpg porque nuestras funciones convierten a JPEG
            ext = '.jpg' 
            base_name = str(uuid.uuid4())
            
            main_name = f"{base_name}{ext}"
            medium_name = f"{base_name}_medium.jpg"
            small_name = f"{base_name}_small.jpg"

            # --- 3. Procesar la nueva imagen y thumbnails ---
            
            # Procesar la imagen principal (recortar a cuadrado 500x500)
            processed_avatar_content = procesar_imagen_en_memoria(
                nuevo_avatar_file,
                max_dimensions=(500, 500),
                new_filename=main_name,
                crop_to_square=True  # Avatares sí van recortados
            )
            
            # Rebobinar el archivo para leerlo de nuevo para los thumbs
            nuevo_avatar_file.seek(0) 
            
            with Image.open(nuevo_avatar_file) as img:
                # Generar thumbnail mediano (100x100)
                thumb_100_content = generar_thumbnail_en_memoria(
                    img.copy(), 
                    (100, 100), 
                    medium_name
                )
                
                # Generar thumbnail pequeño (40x40)
                thumb_40_content = generar_thumbnail_en_memoria(
                    img.copy(), 
                    (40, 40), 
                    small_name
                )

            # --- 4. Borrar los archivos antiguos del almacenamiento (S3) ---
            # (Tu lógica original estaba correcta)
            if old_avatar and old_avatar.name:
                old_avatar.delete(save=False)
            if old_thumb_small and old_thumb_small.name:
                old_thumb_small.delete(save=False)
            if old_thumb_medium and old_thumb_medium.name:
                old_thumb_medium.delete(save=False)

            # --- 5. Asignar y guardar los nuevos archivos ---
            usuario.avatar = processed_avatar_content
            usuario.avatar_thumb_small = thumb_40_content
            usuario.avatar_thumb_medium = thumb_100_content
            usuario.save()

            # Refrescar la instancia es una buena práctica
            usuario.refresh_from_db()

            return Response(
                {'success': True, 'new_avatar_url': usuario.avatar.url},
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            return Response(
                {'error': f'Ocurrió un error inesperado: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class ComunasPorRegionAPIView(APIView):
    """
    Endpoint de API para obtener una lista de Comunas filtradas por una Región.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, region_id, *args, **kwargs):
        # Filtra las comunas que pertenecen a la region_id especificada en la URL
        comunas = Comuna.objects.filter(region_id=region_id).order_by('nombre')
        
        # Si no se encuentran comunas, devuelve una lista vacía (lo cual es correcto)
        serializer = ComunaSerializer(comunas, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)




class GraficoExistenciasCategoriaView(APIView):
    """
    API Endpoint para obtener datos del gráfico de existencias por categoría.
    Suma Activos y Lotes de Insumo de la estación activa.
    """
    # Si usas autenticación por sesión de Django estándar, esto es suficiente.
    # Si tu API usa tokens, necesitarás permission_classes = [IsAuthenticated]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, format=None):
        # 1. Obtener Estación Activa de la sesión
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
            return Response(
                {"error": "No hay estación activa en la sesión"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Agrupar Activos por Categoría
        # Ruta: Activo -> Producto -> ProductoGlobal -> Categoria -> nombre
        activos_por_categoria = (
            Activo.objects
            .filter(estacion_id=estacion_id)
            .values(nombre_categoria=F('producto__producto_global__categoria__nombre'))
            .annotate(total=Count('id'))
        )

        # 3. Agrupar Lotes por Categoría
        # Ruta: LoteInsumo -> Producto -> ProductoGlobal -> Categoria -> nombre
        # NOTA: Para lotes, ¿queremos contar lotes O sumar cantidades?
        # Generalmente para inventario masivo se suman cantidades.
        # Si prefieres sumar cantidades, usa Sum('cantidad') en lugar de Count('id').
        # Por ahora usaremos Count('id') para ser consistentes con Activos (1 activo = 1 unidad).
        from django.db.models import Sum
        lotes_por_categoria = (
            LoteInsumo.objects
            .filter(compartimento__ubicacion__estacion_id=estacion_id)
            .values(nombre_categoria=F('producto__producto_global__categoria__nombre'))
            .annotate(total=Sum('cantidad')) # Sumamos la cantidad real de insumos
        )

        # 4. Combinar resultados en un diccionario para sumarlos
        conteo_final = {}

        # Procesar Activos
        for item in activos_por_categoria:
            cat = item['nombre_categoria']
            total = item['total']
            conteo_final[cat] = conteo_final.get(cat, 0) + total

        # Procesar Lotes (sumándolos a lo que ya exista)
        for item in lotes_por_categoria:
            cat = item['nombre_categoria']
            total = item['total'] or 0 # Asegurar que no sea None si Sum devuelve null
            conteo_final[cat] = conteo_final.get(cat, 0) + total

        # 5. Formatear para Chart.js (labels y data separados)
        labels = list(conteo_final.keys())
        values = list(conteo_final.values())

        data = {
            "labels": labels,
            "values": values
        }

        return Response(data)




class GraficoEstadosInventarioView(APIView):
    """
    API Endpoint para obtener datos del gráfico de estado general del inventario.
    Agrupa por TipoEstado (OPERATIVO, NO OPERATIVO, ADMINISTRATIVO, etc.)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        estacion_id = request.session.get('active_estacion_id')
        if not estacion_id:
             return Response({"error": "Sin estación activa"}, status=status.HTTP_400_BAD_REQUEST)

        # Agrupamos por Tipo de Estado
        # Ruta: Activo -> Estado -> TipoEstado -> nombre
        activos_por_estado = (
            Activo.objects.filter(estacion_id=estacion_id)
            .values(nombre_estado=F('estado__tipo_estado__nombre'))
            .annotate(total=Count('id'))
        )

        # Ruta: LoteInsumo -> Estado -> TipoEstado -> nombre
        lotes_por_estado = (
            LoteInsumo.objects.filter(compartimento__ubicacion__estacion_id=estacion_id)
            .values(nombre_estado=F('estado__tipo_estado__nombre'))
            .annotate(total=Sum('cantidad'))
        )

        conteo_final = {}
        for item in activos_por_estado:
             cat = item['nombre_estado'] or "Sin Estado" # Manejo de posibles nulos
             conteo_final[cat] = conteo_final.get(cat, 0) + item['total']

        for item in lotes_por_estado:
             cat = item['nombre_estado'] or "Sin Estado"
             conteo_final[cat] = conteo_final.get(cat, 0) + (item['total'] or 0)

        return Response({
            "labels": list(conteo_final.keys()),
            "values": list(conteo_final.values())
        })




class ProductoGlobalSKUAPIView(APIView):
    """
    Endpoint para obtener detalles de producto y sugerencia de SKU.
    Uso: Fetch desde modal de inventario o App Móvil.
    """
    permission_classes = [IsStationActiveAndHasPermission]
    
    # Definimos el permiso requerido para que nuestro validador lo lea
    required_permission = "gestion_usuarios.accion_gestion_inventario_ver_catalogos"

    def get(self, request, pk, format=None):
        # get_object_or_404 maneja el error 404 automáticamente y DRF lo formatea a JSON
        producto_global = get_object_or_404(
            ProductoGlobal.objects.select_related('categoria', 'marca'), 
            pk=pk
        )

        try:
            sku_sugerido = generar_sku_sugerido(producto_global)
            
            # Respuesta limpia y directa
            data = {
                'id': producto_global.id,
                'nombre_oficial': producto_global.nombre_oficial,
                'sku_sugerido': sku_sugerido,
                'marca': producto_global.marca.nombre if producto_global.marca else "Genérico"
            }
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            # Loguear el error real aquí si tienes logger
            return Response(
                {'error': 'Error interno al generar el SKU.'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class AnadirProductoLocalAPIView(AuditoriaMixin, APIView):
    """
    Endpoint (POST) para crear un Producto local en la estación activa.
    Utiliza Serializers para validación de entrada, 
    Manejo de Excepciones granular y Transacciones atómicas.
    """
    permission_classes = [IsStationActiveAndHasPermission]
    required_permission = "gestion_usuarios.accion_gestion_inventario_crear_producto_global"

    def post(self, request, format=None):
        # 1. Validación de Entrada con Serializer
        serializer = ProductoLocalInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'details': serializer.errors}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Datos ya validados y limpios
        data = serializer.validated_data

        # 2. Obtención de Contexto (Estación)
        # El permiso ya garantizó que existe 'active_estacion_id' en sesión
        estacion_id = request.session['active_estacion_id']
        estacion = get_object_or_404(Estacion, pk=estacion_id)

        # 3. Obtención de Producto Global
        try:
            producto_global = ProductoGlobal.objects.get(pk=data['productoglobal_id'])
        except ProductoGlobal.DoesNotExist:
            return Response(
                {'error': 'El producto global especificado no existe.'}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 4. Creación del Registro (Con manejo de integridad)
        try:
            # Usamos transaction.atomic por si en el futuro añades más lógica aquí
            with transaction.atomic():
                nuevo_producto = Producto.objects.create(
                    producto_global=producto_global,
                    estacion=estacion,
                    sku=data['sku'],
                    es_serializado=data['es_serializado'],
                    es_expirable=data['es_expirable']
                )

                # --- AUDITORÍA ---
                self.auditar(
                    verbo="agregó a la compañía el producto",
                    objetivo=nuevo_producto,
                    objetivo_repr=nuevo_producto.producto_global.nombre_oficial,
                    detalles={'nombre': nuevo_producto.producto_global.nombre_oficial}
                )
            
            # 5. Respuesta Exitosa
            return Response({
                'success': True,
                'message': f'Producto "{nuevo_producto.producto_global.nombre_oficial}" añadido a tu estación.',
                'productoglobal_id': nuevo_producto.producto_global_id,
                'producto_local_id': nuevo_producto.id # Dato útil para el frontend
            }, status=status.HTTP_201_CREATED)

        except IntegrityError:
            # Captura el error unique_together (Estación + SKU o Estación + ProductoGlobal)
            return Response(
                {'error': f'Error de integridad: Ya existe un producto con el SKU "{data["sku"]}" o este producto global ya fue añadido.'}, 
                status=status.HTTP_409_CONFLICT
            )
        except Exception as e:
            # Loguear error real en servidor
            return Response(
                {'error': f'Error interno inesperado: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )