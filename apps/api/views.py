import uuid
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Sum, Q, Max
from django.db.models.functions import Coalesce
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from PIL import Image
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.gestion_usuarios.models import Usuario, Membresia
from apps.gestion_mantenimiento.models import PlanMantenimiento, PlanActivoConfig, OrdenMantenimiento, RegistroMantenimiento
from apps.gestion_mantenimiento.services import auditar_modificacion_incremental
from apps.common.utils import procesar_imagen_en_memoria, generar_thumbnail_en_memoria
from apps.common.mixins import AuditoriaMixin
from apps.gestion_inventario.models import Comuna, Activo, LoteInsumo, ProductoGlobal, Producto, Estado, MovimientoInventario, RegistroUsoActivo
from apps.gestion_inventario.utils import generar_sku_sugerido
from .utils import obtener_contexto_bomberil
from .serializers import ComunaSerializer, ProductoLocalInputSerializer, CustomTokenObtainPairSerializer, CustomTokenRefreshSerializer
from .permissions import (
    IsEstacionActiva, 
    CanCrearUsuario,
    CanVerCatalogos, 
    CanVerStock,
    CanCrearProductoGlobal,
    CanGestionarPlanes,
    CanGestionarOrdenes,
    IsSelfOrStationAdmin
)


class MeView(APIView):
    """
    Devuelve los datos actuales del usuario (perfil, estación, permisos)
    sin necesidad de refrescar el token. Útil para el inicio de la App.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Reutilizamos la lógica central. Si el usuario perdió su membresía
        # o hay algún problema, la función lanzará ValidationError y DRF
        # responderá con un error 400 automáticamente.
        data = obtener_contexto_bomberil(request.user)
        return Response(data)


class BomberilLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            print("\n" + "="*30)
            print("🚨 ERROR DE VALIDACIÓN DETECTADO")
            print("Datos Recibidos:", request.data)
            print("Errores del Serializer:", serializer.errors)
            print("="*30 + "\n")
            raise e # Vuelve a lanzar el error para que responda 400 normal

        return super().post(request, *args, **kwargs)




class BomberilRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer




class BomberilLogoutView(APIView):
    """
    Invalida el Refresh Token del usuario, impidiendo que genere nuevos tokens de acceso.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # El cliente debe enviar el "refresh" token en el body
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            
            # Bloqueamos el token
            token.blacklist()
            
            return Response({"detail": "Sesión cerrada correctamente."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            # Si el token no es válido o falta, devolvemos error
            return Response({"detail": "Token inválido o no proporcionado."}, status=status.HTTP_400_BAD_REQUEST)




class PasswordResetRequestView(APIView):
    """
    Endpoint para solicitar restablecimiento de contraseña desde la App Móvil.
    Recibe un email, valida que exista y envía el correo usando las mismas
    plantillas que la versión Web.
    """
    # Permitir acceso sin token (el usuario no puede loguearse si olvidó la clave)
    permission_classes = [] 

    def post(self, request):
        form = PasswordResetForm(request.data)
        
        if form.is_valid():
            # Configuración para mantener consistencia con CustomPasswordResetView
            opts = {
                'use_https': request.is_secure(),
                
                # Usamos TUS plantillas personalizadas (acceso/emails/...)
                'email_template_name': 'acceso/emails/password_reset_email.txt',
                'html_email_template_name': 'acceso/emails/password_reset_email.html',
                'subject_template_name': 'acceso/emails/password_reset_subject.txt',
                
                'request': request,
                # El link debe apuntar a la WEB (donde está el formulario de nueva password)
                'domain_override': 'localhost:8000' if settings.DEBUG else 'tudominio.com',
            }
            
            # save() busca usuarios activos, genera el token y envía el email
            form.save(**opts)
            
            # Respuesta genérica por seguridad (evita enumeración de usuarios)
            return Response(
                {"detail": "Si el correo está registrado, recibirás las instrucciones pronto."},
                status=status.HTTP_200_OK
            )
        
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)




class TestConnectionView(APIView):
    permission_classes = [IsAuthenticated] # ¡Importante! Solo entra si el Token es válido

    def get(self, request):
        # Si llegamos aquí, el usuario ya fue autenticado por el JWT
        return Response({
            "status": "ok",
            "mensaje": "¡Conexión exitosa desde App Móvil!",
            "usuario_autenticado": f"{request.user.first_name} {request.user.last_name}",
            "rut": request.user.rut,
            "estacion_activa_id": request.session.get('active_estacion_id', 'No establecida en sesión Django')
        })




class AlternarTemaOscuroAPIView(APIView):
    """
    API robusta para alternar el modo oscuro.
    Requiere autenticación y usa POST para cambios de estado seguros.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Obtenemos el estado actual (False por defecto)
        current = request.session.get('dark_mode', False)
        
        # Invertimos el estado
        nuevo_estado = not current
        request.session['dark_mode'] = nuevo_estado
        request.session.modified = True # Forzamos el guardado de sesión
        
        return Response({
            'status': 'ok',
            'dark_mode': nuevo_estado,
            'mensaje': 'Tema actualizado correctamente.'
        })




class BuscarUsuarioAPIView(APIView):
    """
    Busca un usuario por su RUT
    y devuelve su estado de membresía.
    """

    permission_classes = [IsAuthenticated, CanCrearUsuario]


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
        except Exception as e:
            return Response(
                {'error': f'Error interno al buscar usuario: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class ActualizarAvatarUsuarioAPIView(APIView):
    """
    Actualiza el avatar del usuario.
    Permite acceso al dueño del perfil O a un administrador de la misma estación.
    Usa IsSelfOrStationAdmin para validar la autorización.
    """
    permission_classes = [IsAuthenticated, IsSelfOrStationAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, id, format=None):
        # 1. Buscamos al usuario objetivo
        usuario = get_object_or_404(Usuario, pk=id)

        # 2. Ejecutamos la validación de permisos de objeto explícitamente
        # Esto dispara IsSelfOrStationAdmin.has_object_permission(request, view, usuario)
        self.check_object_permissions(request, usuario)

        # 3. Validamos el archivo
        nuevo_avatar_file = request.FILES.get('nuevo_avatar')
        if not nuevo_avatar_file:
            return Response({'error': 'No se proporcionó ningún archivo.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Procesamiento de Imágenes
            base_name = str(uuid.uuid4())
            main_name = f"{base_name}.jpg"
            
            # Procesar principal (Cuadrada 1024x1024)
            processed_avatar = procesar_imagen_en_memoria(nuevo_avatar_file, (1024, 1024), main_name, crop_to_square=True)

            # Nos aseguramos de leer el archivo procesado desde el inicio
            if hasattr(processed_avatar, 'seek'):
                processed_avatar.seek(0)
            
            with Image.open(processed_avatar) as img_procesada:
                # Generamos los thumbnails basados en la versión cuadrada perfecta
                # Nota: No necesitamos .copy() si generar_thumbnail lo maneja, pero es buena práctica
                thumb_medium = generar_thumbnail_en_memoria(img_procesada, (600, 600), f"{base_name}_medium.jpg")
                thumb_small = generar_thumbnail_en_memoria(img_procesada, (60, 60), f"{base_name}_small.jpg")

            # Asignación y Guardado
            # django-cleanup se encargará de borrar los anteriores al guardar los nuevos
            usuario.avatar = processed_avatar
            usuario.avatar_thumb_small = thumb_small
            usuario.avatar_thumb_medium = thumb_medium
            
            usuario.save()
            usuario.refresh_from_db()

            return Response({'success': True, 'new_avatar_url': usuario.avatar.url})
            
        except Exception as e:
            return Response({'error': f'Error interno: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class ComunasPorRegionAPIView(APIView):
    """
    Endpoint de API para obtener una lista de Comunas filtradas por una Región.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, region_id, *args, **kwargs):
        try:
            # Filtra las comunas que pertenecen a la region_id especificada en la URL
            comunas = Comuna.objects.filter(region_id=region_id).order_by('nombre')
        
            # Si no se encuentran comunas, devuelve una lista vacía (lo cual es correcto)
            serializer = ComunaSerializer(comunas, many=True)
        
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': f'Error al cargar comunas: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




# --- VISTAS DE GRÁFICOS (Requieren Estación Activa) ---
class InventarioGraficoExistenciasCategoriaAPIView(APIView):
    """
    API Endpoint para obtener datos del gráfico de existencias por categoría.
    Suma Activos y Lotes de Insumo de la estación activa.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva]
    
    def get(self, request, format=None):
        try:
            # 1. Obtener Estación Activa de la sesión
            estacion = request.estacion_activa

            # 2. Agrupar Activos por Categoría
            # Ruta: Activo -> Producto -> ProductoGlobal -> Categoria -> nombre
            activos_por_categoria = (
                Activo.objects
                .filter(estacion=estacion)
                .values(nombre_categoria=F('producto__producto_global__categoria__nombre'))
                .annotate(total=Count('id'))
            )

            # 3. Agrupar Lotes por Categoría
            # Ruta: LoteInsumo -> Producto -> ProductoGlobal -> Categoria -> nombre
            # NOTA: Para lotes, ¿queremos contar lotes O sumar cantidades?
            # Generalmente para inventario masivo se suman cantidades.
            # Si prefieres sumar cantidades, usa Sum('cantidad') en lugar de Count('id').
            # Por ahora usaremos Count('id') para ser consistentes con Activos (1 activo = 1 unidad).
            lotes_por_categoria = (
                LoteInsumo.objects
                .filter(compartimento__ubicacion__estacion=estacion)
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
        
        except Exception as e:
            return Response(
                {'error': f'Error generando gráfico: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class InventarioGraficoEstadosAPIView(APIView):
    """
    API Endpoint para obtener datos del gráfico de estado general del inventario.
    Agrupa por TipoEstado (OPERATIVO, NO OPERATIVO, ADMINISTRATIVO, etc.)
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva]

    def get(self, request, format=None):
        try:
            estacion = request.estacion_activa

            # Agrupamos por Tipo de Estado
            # Ruta: Activo -> Estado -> TipoEstado -> nombre
            activos_por_estado = (
                Activo.objects.filter(estacion=estacion)
                .values(nombre_estado=F('estado__tipo_estado__nombre'))
                .annotate(total=Count('id'))
            )

            # Ruta: LoteInsumo -> Estado -> TipoEstado -> nombre
            lotes_por_estado = (
                LoteInsumo.objects.filter(compartimento__ubicacion__estacion=estacion)
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
        
        except Exception as e:
            return Response(
                {'error': f'Error generando gráfico: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class InventarioProductoGlobalSKUAPIView(APIView):
    """
    Endpoint para obtener detalles de producto y sugerencia de SKU.
    Uso: Fetch desde modal de inventario o App Móvil.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerCatalogos]

    def get(self, request, pk, format=None):
        # IsEstacionActiva ya validó que tenemos sesión
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




class InventarioAnadirProductoLocalAPIView(AuditoriaMixin, APIView):
    """
    Endpoint (POST) para crear un Producto local en la estación activa.
    Utiliza Serializers para validación de entrada, 
    Manejo de Excepciones granular y Transacciones atómicas.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanCrearProductoGlobal]
    required_permission = "gestion_usuarios.accion_gestion_inventario_crear_producto_global"

    def post(self, request, format=None):
        # Validación de Entrada con Serializer
        serializer = ProductoLocalInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'details': serializer.errors}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Datos ya validados y limpios
        data = serializer.validated_data
        estacion = request.estacion_activa

        # Obtención de Producto Global
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




class InventarioBuscarExistenciasPrestablesAPI(APIView):
    """
    Endpoint para búsqueda tipo 'Typeahead' de existencias.
    Requiere autenticación y una estación activa (vía Sesión, Header o Membresía).
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva]

    def get(self, request, format=None):
        # 1. Validación de Parámetros
        query = request.query_params.get('q', '').strip()

        # Capturar IDs a excluir
        exclude_param = request.query_params.get('exclude', '')
        excluded_ids = []
        if exclude_param:
            # Convertimos "uuid1,uuid2" en una lista ['uuid1', 'uuid2']
            excluded_ids = [x.strip() for x in exclude_param.split(',') if x.strip()]
        
        if not query:
            return Response(
                {"error": "El término de búsqueda no puede estar vacío.", "items": []}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(query) < 2:
            return Response(
                {"error": "Ingrese al menos 2 caracteres.", "items": []}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Obtención de la Estación (Inyectada por el Permiso IsEstacionActiva)
        estacion = request.estacion_activa
        estacion_id = estacion.id

        try:
            results = []

            # 3. Búsqueda de ACTIVOS
            # [cite: 36, 37] Solo estados operativos/disponibles
            activos = Activo.objects.filter(
                estacion_id=estacion_id,
                estado__nombre='DISPONIBLE',
                estado__tipo_estado__nombre='OPERATIVO'
            ).filter(
                Q(codigo_activo__icontains=query) | 
                Q(producto__producto_global__nombre_oficial__icontains=query) |
                Q(numero_serie_fabricante__icontains=query)
            )

            # Aplicar exclusión de activos ya seleccionados
            if excluded_ids:
                activos = activos.exclude(id__in=excluded_ids)

            # Optimizamos y limitamos DESPUÉS de filtrar
            activos = activos.select_related('producto__producto_global')[:10]

            for a in activos:
                results.append({
                    'id': f"activo_{a.id}",
                    'real_id': str(a.id),
                    'tipo': 'activo',
                    'codigo': a.codigo_activo,
                    'nombre': a.producto.producto_global.nombre_oficial,
                    'texto_mostrar': f"[ACTIVO] {a.producto.producto_global.nombre_oficial} ({a.codigo_activo})",
                    'max_qty': 1
                })

            # 4. Búsqueda de LOTES
            # [cite: 32] Lotes fungibles con stock positivo
            lotes = LoteInsumo.objects.filter(
                compartimento__ubicacion__estacion_id=estacion_id,
                estado__nombre='DISPONIBLE',
                cantidad__gt=0 
            ).filter(
                Q(codigo_lote__icontains=query) | 
                Q(producto__producto_global__nombre_oficial__icontains=query)
            )

            # Aplicar exclusión de lotes ya seleccionados
            if excluded_ids:
                lotes = lotes.exclude(id__in=excluded_ids)

            lotes = lotes.select_related('producto__producto_global')[:10]

            for l in lotes:
                results.append({
                    'id': f"lote_{l.id}",
                    'real_id': str(l.id),
                    'tipo': 'lote',
                    'codigo': l.codigo_lote,
                    'nombre': l.producto.producto_global.nombre_oficial,
                    'texto_mostrar': f"[LOTE] {l.producto.producto_global.nombre_oficial} ({l.codigo_lote}) - Disp: {l.cantidad}",
                    'max_qty': l.cantidad
                })

            return Response({'items': results}, status=status.HTTP_200_OK)

        except Exception as e:
            # En producción, usar logger.error(e)
            print(f"Error en API Búsqueda: {e}")
            return Response(
                {"error": "Error interno del servidor."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class InventarioDetalleExistenciaAPIView(APIView):
    """
    Endpoint para consultar el detalle de una existencia escaneando su código.
    URL: /api/v1/inventario/existencias/detalle/?codigo=ABC-123
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerStock]

    def get(self, request):
        codigo = request.query_params.get('codigo')
        
        if not codigo:
            return Response(
                {"detail": "Debe proporcionar un parámetro 'codigo'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        estacion = request.estacion_activa
        data_response = {}
        item_obj = None
        tipo_item = None

        # ---------------------------------------------------------
        # 1. INTENTO DE BÚSQUEDA: ACTIVO SERIALIZADO
        # ---------------------------------------------------------
        # Filtramos Activo por codigo_activo y estación
        activo = Activo.objects.filter(
            codigo_activo=codigo, 
            estacion=estacion
        ).select_related(
            'producto__producto_global__marca',  # Traemos la marca para no hacer otra query
            'compartimento__ubicacion', 
            'estado', 
            'proveedor'
        ).first()

        if activo:
            data_response = self._construir_data_activo(activo)
            item_obj = activo
            tipo_item = 'activo'

        # ---------------------------------------------------------
        # 2. INTENTO DE BÚSQUEDA: LOTE DE INSUMOS
        # ---------------------------------------------------------
        else:
            # Filtramos LoteInsumo por codigo_lote
            lote = LoteInsumo.objects.filter(
                codigo_lote=codigo,
                # La relación de lote a estación pasa por Ubicación -> Compartimento
                compartimento__ubicacion__estacion=estacion
            ).select_related(
                'producto__producto_global__marca', 
                'compartimento__ubicacion', 
                'estado'
            ).first()

            if lote:
                data_response = self._construir_data_lote(lote)
                item_obj = lote
                tipo_item = 'lote'
            else:
                return Response(
                    {"detail": f"No se encontró ninguna existencia con el código '{codigo}' en esta estación."}, 
                    status=status.HTTP_404_NOT_FOUND
                )

        # ---------------------------------------------------------
        # 3. CONTEXTO COMÚN: HISTORIAL DE MOVIMIENTOS
        # ---------------------------------------------------------
        # Filtro dinámico en MovimientoInventario
        filtro_mov = Q(activo=item_obj) if tipo_item == 'activo' else Q(lote_insumo=item_obj)
        
        movimientos = MovimientoInventario.objects.filter(
            estacion=estacion
        ).filter(filtro_mov).select_related(
            'usuario', 'compartimento_origen__ubicacion', 'compartimento_destino__ubicacion'
        ).order_by('-fecha_hora')[:20]

        data_response['historial_movimientos'] = [
            {
                "id": m.id,
                "fecha": m.fecha_hora.isoformat(),
                "tipo": m.get_tipo_movimiento_display(),
                "usuario": m.usuario.get_full_name() if m.usuario else "Sistema",
                "origen": str(m.compartimento_origen) if m.compartimento_origen else "N/A",
                "destino": str(m.compartimento_destino) if m.compartimento_destino else "Externo/Baja",
            } for m in movimientos
        ]

        return Response(data_response, status=status.HTTP_200_OK)

    def _construir_data_activo(self, activo):
        """Helper para serializar manualmente la data compleja del Activo"""
        # Navegamos a ProductoGlobal para sacar datos maestros
        prod_global = activo.producto.producto_global
        marca_nombre = prod_global.marca.nombre if prod_global.marca else "Genérico"
        
        # Imagen: Prioridad Activo > Producto Global > None
        imagen_url = None
        if activo.imagen:
            imagen_url = activo.imagen.url
        elif prod_global.imagen:
            imagen_url = prod_global.imagen.url

        data = {
            "tipo_existencia": "ACTIVO",
            "id": activo.id,
            "sku": activo.producto.sku or "N/A",
            "codigo": activo.codigo_activo,
            "nombre": prod_global.nombre_oficial, 
            "marca": marca_nombre,
            "modelo": prod_global.modelo or "",
            "serie": activo.numero_serie_fabricante or "S/N", #
            "ubicacion": f"{activo.compartimento.ubicacion.nombre} > {activo.compartimento.nombre}" if activo.compartimento else "Sin Ubicación",
            "estado": activo.estado.nombre if activo.estado else "Desconocido",
            "estado_color": "green" if activo.estado and activo.estado.nombre == "DISPONIBLE" else "red",
            "imagen": imagen_url,
        }

        # B. Estadísticas de Uso (RegistroUsoActivo)
        uso_stats = RegistroUsoActivo.objects.filter(activo=activo).aggregate(
            total_horas=Sum('horas_registradas'),
            ultimo_uso=Max('fecha_uso'),
            total_registros=Count('id')
        )
        
        data['uso_stats'] = {
            "total_horas": uso_stats['total_horas'] or 0,
            "ultimo_uso": uso_stats['ultimo_uso'].isoformat() if uso_stats['ultimo_uso'] else None,
            "total_registros": uso_stats['total_registros']
        }

        # C. Mantenimiento (OrdenMantenimiento)
        ordenes_activas = OrdenMantenimiento.objects.filter(
            activos_afectados=activo,
            estado__in=['PENDIENTE', 'EN_CURSO']
        ).count()
        
        data['mantenimiento'] = {
            "ordenes_activas_count": ordenes_activas,
            "en_taller": activo.estado.nombre == "EN MANTENIMIENTO" if activo.estado else False
        }

        return data

    def _construir_data_lote(self, lote):
        """Helper para serializar la data simple del Lote"""
        # Navegamos a ProductoGlobal
        prod_global = lote.producto.producto_global
        marca_nombre = prod_global.marca.nombre if prod_global.marca else "Genérico"

        # Imagen: Producto Global > None (Lote no tiene imagen propia en models.py)
        imagen_url = prod_global.imagen.url if prod_global.imagen else None

        return {
            "tipo_existencia": "LOTE",
            "id": lote.id,
            "sku": lote.producto.sku or "N/A",
            "codigo": lote.codigo_lote, #
            "nombre": prod_global.nombre_oficial,
            "marca": marca_nombre,
            "cantidad_actual": lote.cantidad, #
            "unidad_medida": "Unidades", # No existe campo en modelo, valor por defecto seguro
            "vencimiento": lote.fecha_expiracion.isoformat() if lote.fecha_expiracion else None, #
            "ubicacion": f"{lote.compartimento.ubicacion.nombre} > {lote.compartimento.nombre}" if lote.compartimento else "Sin Ubicación",
            "estado": lote.estado.nombre if lote.estado else "Desconocido",
            "estado_color": "green" if lote.estado and lote.estado.nombre == "DISPONIBLE" else "orange",
            "imagen": imagen_url,
            
            # Campos vacíos para consistencia UI
            "uso_stats": None,
            "mantenimiento": None
        }




class InventarioCatalogoStockAPIView(APIView):
    """
    Endpoint para listar el catálogo local FILTRADO por existencias positivas.
    Ideal para la vista principal de "Mi Inventario" en la App.
    
    URL: /api/v1/inventario/catalogo/stock/
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerCatalogos]

    def get(self, request):
        estacion = request.estacion_activa
        busqueda = request.query_params.get('search', '').strip()

        # 1. Base: Productos de MI estación
        # Optimizamos consultas trayendo datos del global (nombre, imagen, categoria)
        productos = Producto.objects.filter(estacion=estacion).select_related(
            'producto_global', 
            'producto_global__categoria',
            'producto_global__marca'
        )

        # 2. Búsqueda opcional (Texto)
        if busqueda:
            productos = productos.filter(
                Q(sku__icontains=busqueda) |
                Q(producto_global__nombre_oficial__icontains=busqueda) |
                Q(producto_global__marca__nombre__icontains=busqueda)
            )

        # 3. Anotaciones de Stock (El corazón del filtro)
        # Calculamos el stock ANTES de filtrar para ser eficientes
        productos = productos.annotate(
            # Cuenta cuantos activos (filas en tabla Activo) hay asociados a este producto
            # Opcional: Podrías filtrar aquí .exclude(estado__nombre='DE BAJA') si quisieras
            cantidad_activos=Count('activo'),
            
            # Suma la cantidad de todos los lotes asociados
            # Coalesce convierte el Null (si no hay lotes) en 0
            cantidad_insumos=Coalesce(Sum('loteinsumo__cantidad'), 0)
        )

        # 4. Filtro Final: "Solo lo que tenga existencias"
        # La lógica es: (Es Serializado Y tiene activos > 0) O (No es Serializado Y tiene suma lotes > 0)
        productos_con_stock = productos.filter(
            Q(es_serializado=True, cantidad_activos__gt=0) |
            Q(es_serializado=False, cantidad_insumos__gt=0)
        ).distinct()

        # 5. Construcción de Respuesta JSON ligera para móvil
        data = []
        for p in productos_con_stock:
            # Determinamos la cantidad real a mostrar según el tipo
            stock_real = p.cantidad_activos if p.es_serializado else p.cantidad_insumos
            
            # Imagen segura
            img_url = None
            if p.producto_global.imagen_thumb_medium:
                img_url = p.producto_global.imagen_thumb_medium.url

            data.append({
                "id": p.id, # ID del Producto Local
                "nombre": p.producto_global.nombre_oficial,
                "marca": p.producto_global.marca.nombre if p.producto_global.marca else "Genérico",
                "sku": p.sku or "S/SKU",
                "categoria": p.producto_global.categoria.nombre,
                "es_activo": p.es_serializado, # Booleano útil para UI (ej: mostrar icono de código de barras vs cubos)
                "stock_total": stock_real,
                "imagen": img_url,
                "critico": p.stock_critico > 0 and stock_real <= p.stock_critico # Flag para pintar en rojo en la app
            })

        return Response(data, status=status.HTTP_200_OK)




# --- VISTAS DE GESTIÓN DE MANTENIMIENTO ---
class MantenimientoBuscarActivoParaPlanAPIView(APIView):
    """
    API DRF: Busca activos de la estación que NO estén ya en el plan actual.
    GET params: q (búsqueda), plan_id
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarPlanes]

    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        plan_id = request.GET.get('plan_id')
        estacion = request.estacion_activa

        if not query or len(query) < 2:
            return Response({'results': []})

        # 1. Obtener plan
        plan = get_object_or_404(PlanMantenimiento, id=plan_id, estacion=estacion)
        
        # 2. Filtrar
        activos = Activo.objects.filter(
            estacion=estacion
        ).filter(
            Q(codigo_activo__icontains=query) | 
            Q(producto__producto_global__nombre_oficial__icontains=query)
        ).exclude(
            configuraciones_plan__plan=plan
        ).select_related(
            'producto__producto_global', 
            'compartimento__ubicacion', 
        )[:10]

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

        return Response({'results': results})




class MantenimientoAnadirActivoEnPlanAPIView(APIView):
    """
    API DRF: Añade un activo a un plan.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarPlanes]

    def post(self, request, plan_pk):
        try:
            estacion = request.estacion_activa
            plan = get_object_or_404(PlanMantenimiento, pk=plan_pk, estacion=estacion)
            activo_id = request.data.get('activo_id')

            if not activo_id:
                return Response({'error': 'Falta activo_id'}, status=status.HTTP_400_BAD_REQUEST)

            activo = get_object_or_404(Activo, pk=activo_id, estacion=estacion)

            # Lógica de Negocio
            config, created = PlanActivoConfig.objects.get_or_create(
                plan=plan,
                activo=activo,
                defaults={
                    'horas_uso_en_ultima_mantencion': activo.horas_uso_totales 
                }
            )

            if not created:
                return Response({'message': 'El activo ya está en el plan'}, status=status.HTTP_400_BAD_REQUEST)

            # --- AUDITORÍA INCREMENTAL ---
            # No inundamos el log. Agrupamos.
            auditar_modificacion_incremental(
                request=request,
                plan=plan,
                accion_detalle=f"Agregó activo: {activo.codigo_activo}"
            )

            return Response({'status': 'ok', 'message': f"Activo {activo.codigo_activo} añadido."}, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response({'error': f'Error al añadir activo: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class MantenimientoQuitarActivoDePlanAPIView(APIView):
    """
    API DRF: Quita un activo de un plan.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarPlanes]

    def delete(self, request, pk):
        try:
            estacion = request.estacion_activa

            # Buscamos la configuración asegurando estación
            config = get_object_or_404(PlanActivoConfig, pk=pk, plan__estacion=estacion)

            plan = config.plan
            activo_codigo = config.activo.codigo_activo

            config.delete()

            # --- AUDITORÍA INCREMENTAL ---
            auditar_modificacion_incremental(
                request=request,
                plan=plan,
                accion_detalle=f"Retiró activo: {activo_codigo}"
            )

            return Response({'status': 'ok', 'message': f"Activo {activo_codigo} removido."}, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({'error': f'Error al quitar activo: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class MantenimientoTogglePlanActivoAPIView(AuditoriaMixin, APIView):
    """
    API DRF: Cambia el estado 'activo_en_sistema' de un plan (On/Off).
    POST: plan_pk
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarPlanes]

    def post(self, request, pk):
        try:
            estacion = request.estacion_activa
            # Buscamos el plan
            plan = get_object_or_404(PlanMantenimiento, pk=pk, estacion=estacion)

            # Toggle
            plan.activo_en_sistema = not plan.activo_en_sistema
            plan.save(update_fields=['activo_en_sistema'])

            estado_texto = "activó" if plan.activo_en_sistema else "desactivó"

            # --- AUDITORÍA ---
            # 2. Usamos el método del Mixin para consistencia
            self.auditar(
                verbo=f"{estado_texto} la ejecución automática del plan",
                objetivo=plan,
                objetivo_repr=plan.nombre,
                detalles={'nuevo_estado': plan.activo_en_sistema}
            )

            return Response({
                'status': 'ok',
                'nuevo_estado': plan.activo_en_sistema,
                'mensaje': f'Plan {estado_texto.lower()} correctamente.'
            })
        
        except Exception as e:
            return Response({'error': f'Error al cambiar estado: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class MantenimientoCambiarEstadoOrdenAPIView(AuditoriaMixin, APIView):
    """
    API DRF: Cambia el estado global de la orden (INICIAR / FINALIZAR / CANCELAR).
    POST: { accion: 'iniciar' | 'finalizar' | 'cancelar' }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request, pk):
        try:
            estacion = request.estacion_activa
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=estacion)
            accion = request.data.get('accion')
            verbo_auditoria = ""

            if accion == 'iniciar':
                if orden.estado != OrdenMantenimiento.EstadoOrden.PENDIENTE:
                    return Response({'message': 'La orden no está pendiente.'}, status=status.HTTP_400_BAD_REQUEST)

                # Validación de orden vacía
                if orden.activos_afectados.count() == 0:
                    return Response({'status': 'error', 'message': 'No se puede iniciar una orden sin activos.'}, status=status.HTTP_400_BAD_REQUEST)

                orden.estado = OrdenMantenimiento.EstadoOrden.EN_CURSO
                orden.save()
                verbo_auditoria = "Inició la ejecución de la Orden de Mantenimiento"

                # Poner activos en "EN REPARACIÓN"
                try:
                    estado_reparacion = Estado.objects.get(nombre__iexact="EN REPARACIÓN")
                    orden.activos_afectados.update(estado=estado_reparacion)
                except Estado.DoesNotExist:
                    pass

            elif accion == 'finalizar':
                orden.estado = OrdenMantenimiento.EstadoOrden.REALIZADA
                orden.fecha_cierre = timezone.now()
                orden.save()
                verbo_auditoria = "Finalizó exitosamente la Orden de Mantenimiento"

            elif accion == 'cancelar':
                orden.estado = OrdenMantenimiento.EstadoOrden.CANCELADA
                orden.fecha_cierre = timezone.now()
                orden.save()
                verbo_auditoria = "Canceló la Orden de Mantenimiento"

                # Devolver activos a "DISPONIBLE"
                try:
                    estado_disponible = Estado.objects.get(nombre__iexact="DISPONIBLE")
                    orden.activos_afectados.update(estado=estado_disponible)
                except Estado.DoesNotExist:
                    pass

            else:
                return Response({'message': 'Acción no válida.'}, status=status.HTTP_400_BAD_REQUEST)

            # --- AUDITORÍA (Cambio de Estado - Registro Único) ---
            self.auditar(
                verbo=verbo_auditoria,
                objetivo=orden,
                objetivo_repr=f"Orden #{orden.id} ({orden.tipo_orden})",
                detalles={'nuevo_estado': orden.estado}
            )

            return Response({'status': 'ok', 'message': 'Estado actualizado.'})
        
        except Exception as e:
            return Response({'error': f'Error procesando la orden: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MantenimientoRegistrarTareaAPIView(APIView):
    """
    API DRF: Crea un RegistroMantenimiento para un activo.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request, pk):
        try:
            estacion = request.estacion_activa
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=estacion)

            if orden.estado != OrdenMantenimiento.EstadoOrden.EN_CURSO:
                return Response({'message': 'Debe INICIAR la orden antes de registrar tareas.'}, status=status.HTTP_400_BAD_REQUEST)

            activo_id = request.data.get('activo_id')
            notas = request.data.get('notas')
            fue_exitoso = request.data.get('exitoso', True)

            activo = get_object_or_404(Activo, pk=activo_id, estacion=estacion)

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

            # Actualizar estado del activo
            if fue_exitoso:
                try:
                    nuevo_estado = Estado.objects.get(nombre__iexact="DISPONIBLE")
                    activo.estado = nuevo_estado
                except Estado.DoesNotExist:
                    pass
            else:
                try:
                    nuevo_estado = Estado.objects.get(nombre__iexact="NO OPERATIVO")
                    activo.estado = nuevo_estado
                except Estado.DoesNotExist:
                    pass
                
            activo.save()

            # Actualizar Plan si aplica
            if fue_exitoso and orden.plan_origen:
                plan_config = PlanActivoConfig.objects.filter(plan=orden.plan_origen, activo=activo).first()
                if plan_config:
                    plan_config.fecha_ultima_mantencion = timezone.now()
                    plan_config.horas_uso_en_ultima_mantencion = activo.horas_uso_totales
                    plan_config.save()

            # --- AUDITORÍA INCREMENTAL (Avance de Tareas) ---
            # Agrupamos el progreso: "Registró tareas en la Orden X"
            accion_txt = "Tarea exitosa" if fue_exitoso else "Falla reportada"

            auditar_modificacion_incremental(
                request=request,
                plan=orden, # El objetivo es la Orden
                accion_detalle=f"{accion_txt} en {activo.codigo_activo}"
            )

            return Response({'status': 'ok', 'message': 'Registro guardado.'})
        
        except Exception as e:
            return Response({'error': f'Error guardando tarea: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MantenimientoBuscarActivoParaOrdenAPIView(APIView):
    """
    API DRF: Busca activos para agregar a una ORDEN específica.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        orden_id = request.GET.get('orden_id')
        estacion = request.estacion_activa

        if not query or len(query) < 2:
            return Response({'results': []})

        orden = get_object_or_404(OrdenMantenimiento, id=orden_id, estacion=estacion)
        
        activos = Activo.objects.filter(
            estacion=estacion
        ).filter(
            Q(codigo_activo__icontains=query) | 
            Q(producto__producto_global__nombre_oficial__icontains=query)
        ).exclude(
            ordenes_mantenimiento=orden
        ).select_related(
            'producto__producto_global', 
            'compartimento__ubicacion'
        )[:10]

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

        return Response({'results': results})


class MantenimientoAnadirActivoOrdenAPIView(APIView):
    """
    API DRF: Añade un activo a la lista de 'activos_afectados' de una orden.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request, pk):
        try:
            estacion = request.estacion_activa
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=estacion)

            if orden.estado != OrdenMantenimiento.EstadoOrden.PENDIENTE:
                return Response({'message': 'Solo se pueden agregar activos a órdenes PENDIENTES.'}, status=status.HTTP_400_BAD_REQUEST)

            activo_id = request.data.get('activo_id')
            activo = get_object_or_404(Activo, pk=activo_id, estacion=estacion)

            orden.activos_afectados.add(activo)

            # --- AUDITORÍA INCREMENTAL ---
            auditar_modificacion_incremental(
                request=request,
                plan=orden, # Reutilizamos la función pasando la orden como 'plan' (objeto genérico)
                accion_detalle=f"Añadió a la orden: {activo.codigo_activo}"
            )
            return Response({'status': 'ok', 'message': f"Activo {activo.codigo_activo} añadido."})
        
        except Exception as e:
            return Response({'error': f'Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MantenimientoQuitarActivoOrdenAPIView(APIView):
    """
    API DRF: Quita un activo de la orden.
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request, pk):
        try:
            estacion = request.estacion_activa
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=estacion)

            if orden.estado != OrdenMantenimiento.EstadoOrden.PENDIENTE:
                return Response({'message': 'Solo se pueden quitar activos de órdenes PENDIENTES.'}, status=status.HTTP_400_BAD_REQUEST)

            activo_id = request.data.get('activo_id')
            activo = get_object_or_404(Activo, pk=activo_id, estacion=estacion)

            orden.activos_afectados.remove(activo)

            # --- AUDITORÍA INCREMENTAL ---
            auditar_modificacion_incremental(
                request=request,
                plan=orden, 
                accion_detalle=f"Quitó de la orden: {activo.codigo_activo}"
            )
            return Response({'status': 'ok', 'message': f"Activo {activo.codigo_activo} quitado."})
        
        except Exception as e:
            return Response({'error': f'Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)