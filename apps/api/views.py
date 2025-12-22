import uuid
import io
from django.http import HttpResponse
from django.template.loader import render_to_string
from datetime import date
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.shortcuts import redirect, get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Sum, Q, Max, Prefetch
from django.db.models.functions import Coalesce
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from PIL import Image
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.authentication import JWTAuthentication
from xhtml2pdf import pisa

from apps.gestion_usuarios.models import Usuario, Membresia
from apps.gestion_mantenimiento.models import PlanMantenimiento, PlanActivoConfig, OrdenMantenimiento, RegistroMantenimiento
from apps.gestion_mantenimiento.services import auditar_modificacion_incremental
from apps.common.utils import procesar_imagen_en_memoria, generar_thumbnail_en_memoria
from apps.common.mixins import AuditoriaMixin
from apps.gestion_inventario.models import (
    Comuna, 
    Activo, 
    LoteInsumo, 
    ProductoGlobal, 
    Producto, 
    Estado, 
    MovimientoInventario, 
    RegistroUsoActivo, 
    Ubicacion,
    Compartimento, 
    Proveedor, 
    TipoMovimiento,
    Prestamo,
    PrestamoDetalle,
    Destinatario
) 
from apps.gestion_voluntarios.models import Voluntario, HistorialCargo, HistorialReconocimiento, HistorialSancion, HistorialCurso
from apps.gestion_medica.models import FichaMedica
from apps.gestion_documental.models import DocumentoHistorico
from apps.gestion_inventario.utils import generar_sku_sugerido, get_or_create_anulado_compartment, get_or_create_extraviado_compartment
from .utils import obtener_contexto_bomberil
from .serializers import ComunaSerializer, ProductoLocalInputSerializer, CustomTokenObtainPairSerializer, CustomTokenRefreshSerializer
from .mixins import OrdenValidacionMixin
from .permissions import (
    IsEstacionActiva, 
    CanCrearUsuario,
    CanVerCatalogos, 
    CanGestionarCatalogoLocal,
    CanVerStock,
    CanCrearProductoGlobal,
    CanGestionarPlanes,
    CanGestionarOrdenes,
    CanVerOrdenes,
    CanRecepcionarStock,
    CanGestionarBajasStock,
    CanGestionarStockInterno,
    CanGestionarPrestamos,
    CanVerPrestamos,
    CanVerUbicaciones,
    CanVerProveedores,
    CanVerDocumentos,
    CanVerUsuarios,
    CanVerHojaVida,
    CanVerFichaMedica,
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
        
        # Validamos sin lanzar excepción automática para poder imprimir errores
        if not serializer.is_valid():
            print("\n" + "="*30)
            print("🚨 ERROR DE LOGIN:")
            print("Datos:", request.data)
            print("Errores:", serializer.errors) # Ahora sí funcionará este print
            print("="*30 + "\n")
            # Devolvemos el error 400/401 limpio a la App
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

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
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerStock]
    
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
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerStock]

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
    Endpoint API (POST) para la gestión de inventario local.
    
    Permite instanciar un 'Producto' local en la estación activa basándose en un
    'ProductoGlobal' existente. Implementa validación estricta vía Serializers,
    control transaccional de integridad y auditoría de eventos.
    """
    
    # --- Configuración de Seguridad y Permisos ---
    # IsAuthenticated: Requiere sesión válida.
    # IsEstacionActiva: Valida que el usuario tenga una estación seleccionada en su contexto.
    # CanGestionarCatalogoLocal: Verifica privilegios específicos sobre el inventario.
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarCatalogoLocal]
    required_permission = "gestion_usuarios.accion_gestion_inventario_crear_producto_global"

    def post(self, request, format=None):
        """
        Procesar la solicitud de creación de un producto local.
        
        Flujo de ejecución:
        1. Validar integridad de datos (Input Serializer).
        2. Verificar existencia del recurso padre (Producto Global).
        3. Persistir la nueva entidad Producto vinculada a la estación.
        4. Gestionar conflictos de integridad (SKUs duplicados).
        """
        
        # 1. Validación de Entrada
        # Deserializar y validar el payload de la solicitud.
        serializer = ProductoLocalInputSerializer(data=request.data)
        
        if not serializer.is_valid():
            # Retornar error 400 Bad Request con detalles de validación si el esquema es incorrecto.
            return Response(
                {'error': 'Datos inválidos', 'details': serializer.errors}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 2. Obtención de Contexto y Datos Saneados
        # Extraer datos validados y recuperar la estación activa inyectada por el middleware.
        data = serializer.validated_data
        estacion = request.estacion_activa

        # 3. Verificación de Dependencias (Producto Global)
        try:
            # Intentar recuperar el Producto Global base.
            producto_global = ProductoGlobal.objects.get(pk=data['productoglobal_id'])
        except ProductoGlobal.DoesNotExist:
            # Retornar 404 Not Found si el ID referenciado no existe en el catálogo global.
            return Response(
                {'error': 'El producto global especificado no existe.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': 'Error inesperado.'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


        # 4. Persistencia y Auditoría (Bloque Atómico)
        try:
            # Iniciar transacción para garantizar que la creación y la auditoría sean indivisibles.
            with transaction.atomic():
                # Crear la instancia del Producto Local vinculándola a la estación y al global.
                nuevo_producto = Producto.objects.create(
                    producto_global=producto_global,
                    estacion=estacion,
                    sku=data['sku'],
                    es_serializado=data['es_serializado'],
                    es_expirable=data['es_expirable']
                )

                # --- Registro de Auditoría ---
                # Documentar la incorporación del producto al inventario de la compañía.
                self.auditar(
                    verbo="agregó a la compañía el producto",
                    objetivo=nuevo_producto,
                    objetivo_repr=nuevo_producto.producto_global.nombre_oficial,
                    detalles={'nombre': nuevo_producto.producto_global.nombre_oficial}
                )
            
            # 5. Respuesta Exitosa
            # Retornar estado 201 Created con identificadores clave para confirmación en frontend.
            return Response({
                'success': True,
                'message': f'Producto "{nuevo_producto.producto_global.nombre_oficial}" añadido a tu estación.',
                'productoglobal_id': nuevo_producto.producto_global_id,
                'producto_local_id': nuevo_producto.id 
            }, status=status.HTTP_201_CREATED)

        except IntegrityError:
            # 6. Manejo de Conflictos de Integridad
            # Capturar errores de base de datos como 'unique_together' (ej. SKU duplicado en la misma estación).
            return Response(
                {'error': f'Error de integridad: Ya existe un producto con el SKU "{data["sku"]}" o este producto global ya fue añadido.'}, 
                status=status.HTTP_409_CONFLICT
            )
        except Exception as e:
            # 7. Manejo de Errores No Controlados
            # Capturar cualquier otra excepción para evitar caída del servicio y retornar error 500.
            # (Se recomienda integración con sistema de logs como Sentry/CloudWatch).
            return Response(
                {'error': f'Error interno inesperado: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




class InventarioBuscarExistenciasPrestablesAPI(APIView):
    """
    Endpoint para búsqueda tipo 'Typeahead' de existencias.
    Requiere autenticación y una estación activa (vía Sesión, Header o Membresía).
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarPrestamos]

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




class InventarioCrearPrestamoAPIView(AuditoriaMixin, APIView):
    """
    Endpoint transaccional para crear un Préstamo con múltiples ítems.
    Replica la lógica de CrearPrestamoView (Web).
    
    Payload:
    {
        "destinatario_id": 1, 
        "nuevo_destinatario_nombre": "Bomberos Iquique" (Opcional si no hay ID),
        "notas": "Apoyo incendio",
        "fecha_devolucion_esperada": "2023-12-31", // (Opcional) YYYY-MM-DD
        "items": [
            {"tipo": "activo", "id": "uuid...", "cantidad_prestada": 1},
            {"tipo": "lote", "id": "uuid...", "cantidad_prestada": 5}
        ]
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarPrestamos]

    def post(self, request):
        estacion = request.estacion_activa
        
        # --- PUENTE AUDITORÍA ---
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        data = request.data
        items = data.get('items', [])
        
        if not items:
            return Response({"detail": "La lista de ítems está vacía."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Validar Estados Singleton
        try:
            estado_prestado = Estado.objects.get(nombre='EN PRÉSTAMO EXTERNO')
            estado_disponible = Estado.objects.get(nombre='DISPONIBLE')
        except Estado.DoesNotExist:
            return Response({"detail": "Error crítico configuración estados."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            with transaction.atomic():
                # 2. Gestionar Destinatario
                destinatario = self._get_or_create_destinatario(data, estacion, request.user)
                
                # Manejo seguro de la fecha (string vacío o nulo -> None)
                fecha_devolucion = data.get('fecha_devolucion_esperada')
                if not fecha_devolucion:
                    fecha_devolucion = None

                # 3. Crear Cabecera Préstamo
                prestamo = Prestamo.objects.create(
                    estacion=estacion,
                    usuario_responsable=request.user,
                    destinatario=destinatario,
                    notas_prestamo=data.get('notas', ''),
                    fecha_devolucion_esperada=fecha_devolucion # <--- Campo agregado
                )

                # 4. Procesar Ítems
                total_items_fisicos = 0
                conteo_activos = 0
                conteo_insumos = 0

                for item_data in items:
                    tipo = item_data.get('tipo')
                    item_id = item_data.get('id')
                    cantidad = int(item_data.get('cantidad_prestada', 1))

                    if tipo == 'activo':
                        # select_for_update para bloqueo de fila
                        activo = Activo.objects.select_for_update().get(id=item_id, estado=estado_disponible, estacion=estacion)
                        
                        PrestamoDetalle.objects.create(prestamo=prestamo, activo=activo, cantidad_prestada=1)
                        
                        activo.estado = estado_prestado
                        activo.save(update_fields=['estado', 'updated_at'])
                        
                        self._crear_movimiento_prestamo(activo.compartimento, activo, None, -1, destinatario, prestamo.notas_prestamo, request.user, estacion)
                        
                        total_items_fisicos += 1
                        conteo_activos += 1

                    elif tipo == 'lote':
                        lote = LoteInsumo.objects.select_for_update().get(
                            id=item_id, 
                            estado=estado_disponible, 
                            cantidad__gte=cantidad,
                            compartimento__ubicacion__estacion=estacion
                        )
                        
                        PrestamoDetalle.objects.create(prestamo=prestamo, lote=lote, cantidad_prestada=cantidad)
                        
                        lote.cantidad -= cantidad
                        lote.save(update_fields=['cantidad', 'updated_at'])
                        
                        self._crear_movimiento_prestamo(lote.compartimento, None, lote, -1 * cantidad, destinatario, prestamo.notas_prestamo, request.user, estacion)
                        
                        total_items_fisicos += cantidad
                        conteo_insumos += cantidad

                # 5. Auditoría de Sistema
                self._auditar_prestamo(prestamo, destinatario, total_items_fisicos, conteo_activos, conteo_insumos)

            return Response({"message": f"Préstamo #{prestamo.id} creado exitosamente."}, status=status.HTTP_201_CREATED)

        except (Activo.DoesNotExist, LoteInsumo.DoesNotExist):
            return Response({"detail": "Error de concurrencia: Un ítem seleccionado ya no está disponible o no tiene stock suficiente."}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Helpers ---

    def _get_or_create_destinatario(self, data, estacion, usuario):
        dest_id = data.get('destinatario_id')
        if dest_id:
            return get_object_or_404(Destinatario, id=dest_id, estacion=estacion)
        
        # Crear nuevo
        nombre_nuevo = data.get('nuevo_destinatario_nombre')
        if not nombre_nuevo:
            raise ValueError("Debe seleccionar un destinatario o escribir un nombre para uno nuevo.")
            
        destinatario, created = Destinatario.objects.get_or_create(
            estacion=estacion,
            nombre_entidad=nombre_nuevo,
            defaults={
                'telefono_contacto': data.get('nuevo_destinatario_contacto')
            }
        )
        if created:
            self.auditar(verbo="registró como nuevo destinatario a", objetivo=destinatario, detalles={'origen': 'APP MÓVIL'})
        
        return destinatario

    def _crear_movimiento_prestamo(self, compartimento, activo, lote, cantidad, destinatario, notas, usuario, estacion):
        MovimientoInventario.objects.create(
            tipo_movimiento=TipoMovimiento.PRESTAMO,
            usuario=usuario,
            estacion=estacion,
            compartimento_origen=compartimento,
            activo=activo,
            lote_insumo=lote,
            cantidad_movida=cantidad,
            notas=f"Préstamo a {destinatario.nombre_entidad}. {notas}"
        )

    def _auditar_prestamo(self, prestamo, destinatario, total, n_activos, n_insumos):
        partes_msg = []
        if n_activos > 0: partes_msg.append(f"{n_activos} Activo(s)")
        if n_insumos > 0: partes_msg.append(f"{n_insumos} unidad(es) de Insumo(s)")
        
        detalle_texto = " y ".join(partes_msg)
        
        self.auditar(
            verbo=f"registró el préstamo de {detalle_texto} a",
            objetivo=destinatario,
            objetivo_repr=destinatario.nombre_entidad,
            detalles={
                'id_prestamo': prestamo.id,
                'total_items': total,
                'desglose': {'activos': n_activos, 'insumos': n_insumos},
                'origen_accion': 'APP MÓVIL'
            }
        )




class InventarioDestinatarioListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarPrestamos]
    def get(self, request):
        qs = Destinatario.objects.filter(estacion=request.estacion_activa).order_by('nombre_entidad')
        data = [{"id": d.id, "nombre": d.nombre_entidad} for d in qs]
        return Response(data, status=status.HTTP_200_OK)




class InventarioHistorialPrestamosAPIView(APIView):
    """
    Lista el historial de préstamos de la estación.
    Por defecto muestra solo los activos (Pendientes/Parciales).
    
    URL: /api/v1/inventario/prestamos/
    Params: 
      - ?todos=true (Muestra también completados/vencidos)
      - ?search=NombreDestinatario
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerPrestamos]

    def get(self, request):
        estacion = request.estacion_activa
        mostrar_todos = request.query_params.get('todos') == 'true'
        query = request.query_params.get('search', '').strip()

        # 1. Base Query
        qs = Prestamo.objects.filter(estacion=estacion).select_related(
            'destinatario', 
            'usuario_responsable'
        ).prefetch_related('items_prestados') # Para contar items

        # 2. Filtros
        if not mostrar_todos:
            # Solo "Vivos": Pendiente o Devuelto Parcial
            qs = qs.filter(estado__in=[
                Prestamo.EstadoPrestamo.PENDIENTE, 
                Prestamo.EstadoPrestamo.DEVUELTO_PARCIAL
            ])
        
        if query:
            qs = qs.filter(destinatario__nombre_entidad__icontains=query)

        # Ordenar: Más recientes primero
        qs = qs.order_by('-fecha_prestamo')

        # 3. Serialización Manual
        data = []
        for p in qs:
            # Conteo rápido de items para mostrar en la tarjeta de la lista
            # (Ej: "3 ítems prestados")
            total_items = p.items_prestados.count()
            
            # Formato de fecha amigable o ISO según prefieras en el front
            fecha_fmt = p.fecha_prestamo.isoformat()

            data.append({
                "id": p.id,
                "destinatario": p.destinatario.nombre_entidad,
                "fecha": fecha_fmt,
                "estado_display": p.get_estado_display(), # "Pendiente"
                "estado_codigo": p.estado, # "PEN" (Útil para colores en UI: PEN=Yellow, PAR=Orange, COM=Green)
                "responsable": p.usuario_responsable.get_full_name if p.usuario_responsable else "Sistema",
                "total_items": total_items,
                "notas": p.notas_prestamo
            })

        return Response(data, status=status.HTTP_200_OK)




class InventarioGestionarDevolucionAPIView(AuditoriaMixin, APIView):
    """
    Endpoint para gestionar la devolución de un préstamo.
    GET: Retorna el detalle del préstamo y el saldo pendiente de cada ítem.
    POST: Procesa devoluciones y reportes de pérdida en lote.
    
    URL: /api/v1/inventario/prestamos/<int:prestamo_id>/devolucion/
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarPrestamos]

    def get(self, request, prestamo_id):
        # 1. Obtener Préstamo Seguro
        estacion = request.estacion_activa
        prestamo = get_object_or_404(Prestamo, id=prestamo_id, estacion=estacion)

        # 2. Serializar Cabecera
        data = {
            "id": prestamo.id,
            "destinatario": prestamo.destinatario.nombre_entidad,
            "fecha_prestamo": prestamo.fecha_prestamo.isoformat(),
            "estado": prestamo.estado,
            "estado_display": prestamo.get_estado_display(),
            "notas": prestamo.notas_prestamo,
            "items": []
        }

        # 3. Serializar Detalles con Cálculo de Pendientes
        detalles = prestamo.items_prestados.select_related(
            'activo__producto__producto_global', 
            'lote__producto__producto_global'
        ).order_by('id')

        for d in detalles:
            # Polimorfismo visual
            if d.activo:
                nombre = d.activo.producto.producto_global.nombre_oficial
                codigo = d.activo.codigo_activo
                tipo = 'activo'
            else:
                nombre = d.lote.producto.producto_global.nombre_oficial
                codigo = d.lote.codigo_lote
                tipo = 'lote'

            pendiente = d.cantidad_prestada - d.cantidad_devuelta - d.cantidad_extraviada

            data["items"].append({
                "detalle_id": d.id,
                "tipo": tipo,
                "nombre": nombre,
                "codigo": codigo,
                "cantidad_prestada": d.cantidad_prestada,
                "cantidad_devuelta": d.cantidad_devuelta,
                "cantidad_extraviada": d.cantidad_extraviada,
                "pendiente": pendiente, # Dato vital para la UI (max input)
                "saldado": pendiente <= 0
            })

        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, prestamo_id):
        estacion = request.estacion_activa
        
        # --- PUENTE AUDITORÍA ---
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        prestamo = get_object_or_404(Prestamo, id=prestamo_id, estacion=estacion)

        if prestamo.estado == Prestamo.EstadoPrestamo.COMPLETADO:
            return Response({"detail": "El préstamo ya está completado."}, status=status.HTTP_409_CONFLICT)

        # Payload esperado: { "items": [ { "detalle_id": 1, "devolver": 1, "perder": 0 }, ... ] }
        items_payload = request.data.get('items', [])
        
        if not items_payload:
            return Response({"detail": "No se enviaron ítems para procesar."}, status=status.HTTP_400_BAD_REQUEST)

        # Estados Singleton
        try:
            estado_disponible = Estado.objects.get(nombre='DISPONIBLE')
        except Estado.DoesNotExist:
            return Response({"detail": "Error crítico: Estado DISPONIBLE no existe."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            with transaction.atomic():
                resumen = self._procesar_devoluciones(prestamo, items_payload, estado_disponible, request.user, estacion)
                
                if resumen['procesados'] == 0 and resumen['perdidos'] == 0:
                    return Response({"message": "No se registraron cambios (cantidades en 0)."}, status=status.HTTP_200_OK)

                return Response({
                    "message": "Devolución procesada correctamente.",
                    "resumen": resumen
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # --- Helpers de Lógica de Negocio (Adaptados de tu vista Web) ---

    def _procesar_devoluciones(self, prestamo, items_payload, estado_disponible, usuario, estacion):
        movimientos_bulk = []
        items_actualizados_count = 0
        total_unidades_devueltas = 0
        total_unidades_perdidas = 0
        
        # Convertir payload a dict para acceso rápido: { detalle_id: {devolver: x, perder: y} }
        payload_map = { int(i['detalle_id']): i for i in items_payload }
        
        # Iterar sobre los objetos reales de la BD
        db_detalles = prestamo.items_prestados.filter(id__in=payload_map.keys()).select_related('activo', 'lote')

        for detalle in db_detalles:
            accion = payload_map.get(detalle.id)
            if not accion: continue

            cant_devolver = int(accion.get('devolver', 0))
            cant_perder = int(accion.get('perder', 0))
            
            suma_accion = cant_devolver + cant_perder
            if suma_accion <= 0: continue

            # Validación de integridad
            pendiente = detalle.cantidad_prestada - detalle.cantidad_devuelta - detalle.cantidad_extraviada
            if suma_accion > pendiente:
                raise ValueError(f"Ítem {detalle.id}: La suma de devolución y pérdida ({suma_accion}) excede lo pendiente ({pendiente}).")

            hubo_cambios = False

            # A. Procesar Devolución
            if cant_devolver > 0:
                detalle.cantidad_devuelta += cant_devolver
                mov = self._restaurar_stock(detalle, cant_devolver, estado_disponible, prestamo.id, usuario, estacion)
                movimientos_bulk.append(mov)
                total_unidades_devueltas += cant_devolver
                hubo_cambios = True

            # B. Procesar Pérdida
            if cant_perder > 0:
                detalle.cantidad_extraviada += cant_perder
                self._procesar_perdida(detalle, cant_perder, usuario, estacion)
                total_unidades_perdidas += cant_perder
                hubo_cambios = True

            if hubo_cambios:
                detalle.fecha_ultima_devolucion = timezone.now()
                detalle.save()
                items_actualizados_count += 1

        # Guardar movimientos masivos
        if movimientos_bulk:
            MovimientoInventario.objects.bulk_create(movimientos_bulk)

        # Actualizar estado cabecera
        self._verificar_estado_prestamo(prestamo)

        # Auditoría
        if total_unidades_devueltas > 0 or total_unidades_perdidas > 0:
            self.auditar(
                verbo=f"gestionó devolución del Préstamo #{prestamo.id}",
                objetivo=prestamo.destinatario,
                objetivo_repr=f"Préstamo #{prestamo.id}",
                detalles={
                    'devueltos': total_unidades_devueltas,
                    'reportados_perdidos': total_unidades_perdidas,
                    'origen': 'APP MÓVIL'
                }
            )

        return {'procesados': total_unidades_devueltas, 'perdidos': total_unidades_perdidas}

    def _restaurar_stock(self, detalle, cantidad, estado_disp, prestamo_id, usuario, estacion):
        """Devuelve el ítem al stock operativo."""
        movimiento = MovimientoInventario(
            tipo_movimiento=TipoMovimiento.DEVOLUCION,
            usuario=usuario,
            estacion=estacion,
            cantidad_movida=cantidad, # Positivo
            notas=f"Devolución Móvil Préstamo #{prestamo_id}",
            fecha_hora=timezone.now()
        )

        if detalle.activo:
            activo = detalle.activo
            activo.estado = estado_disp
            activo.save(update_fields=['estado', 'updated_at'])
            movimiento.activo = activo
            movimiento.compartimento_destino = activo.compartimento
        elif detalle.lote:
            lote = detalle.lote
            lote.cantidad += cantidad
            lote.save(update_fields=['cantidad', 'updated_at'])
            movimiento.lote_insumo = lote
            movimiento.compartimento_destino = lote.compartimento

        return movimiento

    def _procesar_perdida(self, detalle, cantidad, usuario, estacion):
        """Mueve el ítem al limbo de extraviados."""
        estado_extraviado = Estado.objects.get(nombre='EXTRAVIADO')
        compartimento_limbo = get_or_create_extraviado_compartment(estacion)

        if detalle.activo:
            activo = detalle.activo
            activo.estado = estado_extraviado
            activo.compartimento = compartimento_limbo
            activo.save()
            
            MovimientoInventario.objects.create(
                tipo_movimiento=TipoMovimiento.AJUSTE,
                usuario=usuario,
                estacion=estacion,
                compartimento_destino=compartimento_limbo,
                activo=activo,
                cantidad_movida=0, # Ya estaba fuera (prestado)
                notas=f"Extraviado durante préstamo #{detalle.prestamo.id}"
            )
        elif detalle.lote:
            # Lotes: No movemos el original, solo registramos la "no vuelta"
            MovimientoInventario.objects.create(
                tipo_movimiento=TipoMovimiento.AJUSTE,
                usuario=usuario,
                estacion=estacion,
                compartimento_destino=compartimento_limbo,
                lote_insumo=detalle.lote,
                cantidad_movida=0,
                notas=f"Insumo extraviado ({cantidad}u) en préstamo #{detalle.prestamo.id}"
            )

    def _verificar_estado_prestamo(self, prestamo):
        """Recalcula si el préstamo está completado."""
        # Refrescamos desde BD para tener los datos actualizados por el loop
        todos_saldados = all(d.esta_saldado for d in prestamo.items_prestados.all())
        
        nuevo_estado = None
        if todos_saldados:
            nuevo_estado = Prestamo.EstadoPrestamo.COMPLETADO
        elif any(i.cantidad_devuelta > 0 for i in prestamo.items_prestados.all()):
            if prestamo.estado != Prestamo.EstadoPrestamo.DEVUELTO_PARCIAL:
                nuevo_estado = Prestamo.EstadoPrestamo.DEVUELTO_PARCIAL
        
        if nuevo_estado:
            prestamo.estado = nuevo_estado
            prestamo.save(update_fields=['estado', 'updated_at'])




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
                "usuario": m.usuario.get_full_name if m.usuario else "Sistema",
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
        elif prod_global.imagen_thumb_medium:
            imagen_url = prod_global.imagen_thumb_medium.url

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
            if p.producto_global.imagen_thumb_small:
                img_url = p.producto_global.imagen_thumb_small.url

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




class InventarioExistenciasPorProductoAPIView(APIView):
    """
    Lista las existencias físicas (Activos o Lotes) asociadas a un Producto del catálogo local.
    
    URL: /api/v1/gestion_inventario/existencias/?producto={id}
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerStock]

    def get(self, request):
        producto_id = request.query_params.get('producto')
        
        if not producto_id:
            return Response(
                {"detail": "Debe proporcionar el parámetro 'producto' (ID)."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        estacion = request.estacion_activa

        # 1. Obtener el producto padre asegurando que pertenezca a la estación activa
        producto = get_object_or_404(Producto, id=producto_id, estacion=estacion)

        data = []

        # ---------------------------------------------------------
        # CASO A: PRODUCTO SERIALIZADO (Lista de Activos Únicos)
        # ---------------------------------------------------------
        if producto.es_serializado:
            # Traemos los activos asociados a este producto en esta estación
            activos = Activo.objects.filter(
                producto=producto,
                estacion=estacion # Redundancia de seguridad
            ).select_related(
                'estado',
                'compartimento__ubicacion',
                'asignado_a'
            ).order_by('estado__nombre', 'compartimento__ubicacion__nombre')

            for activo in activos:
                data.append({
                    "id": activo.id, # UUID
                    "tipo": "ACTIVO",
                    "codigo": activo.codigo_activo,
                    "identificador": activo.numero_serie_fabricante or "S/N", # Serie para la UI
                    "ubicacion": f"{activo.compartimento.ubicacion.nombre} > {activo.compartimento.nombre}" if activo.compartimento else "Sin Ubicación",
                    "estado": activo.estado.nombre if activo.estado else "Desconocido",
                    "estado_color": "green" if activo.estado and activo.estado.nombre == "DISPONIBLE" else "orange",
                    "asignado_a": activo.asignado_a.get_full_name if activo.asignado_a else None,
                    "condicion": "Operativo" # Podrías mapear esto del estado si tuvieras un campo booleano
                })

        # ---------------------------------------------------------
        # CASO B: PRODUCTO NO SERIALIZADO (Lista de Lotes/Insumos)
        # ---------------------------------------------------------
        else:
            # Traemos los lotes asociados. Filtramos por la estación a través de la ubicación.
            lotes = LoteInsumo.objects.filter(
                producto=producto,
                compartimento__ubicacion__estacion=estacion
            ).select_related(
                'estado',
                'compartimento__ubicacion'
            ).exclude(cantidad=0).order_by('fecha_expiracion', 'estado__nombre') # Prioridad a lo que vence pronto

            for lote in lotes:
                vencimiento = lote.fecha_expiracion.isoformat() if lote.fecha_expiracion else None
                
                data.append({
                    "id": lote.id, # UUID
                    "tipo": "LOTE",
                    "codigo": lote.codigo_lote,
                    "identificador": f"Lote: {lote.numero_lote_fabricante}" if lote.numero_lote_fabricante else "Lote General",
                    "cantidad": lote.cantidad, # Dato clave para insumos
                    "ubicacion": f"{lote.compartimento.ubicacion.nombre} > {lote.compartimento.nombre}" if lote.compartimento else "Sin Ubicación",
                    "estado": lote.estado.nombre if lote.estado else "Desconocido",
                    "estado_color": "green" if lote.estado and lote.estado.nombre == "DISPONIBLE" else "orange",
                    "vencimiento": vencimiento,
                    "es_vencido": lote.fecha_expiracion and lote.fecha_expiracion < timezone.now().date() if hasattr(lote, 'fecha_expiracion') else False
                })

        return Response(data, status=status.HTTP_200_OK)




class InventarioRecepcionStockAPIView(AuditoriaMixin, APIView):
    """
    Endpoint transaccional para procesar la recepción de stock (Activos y Lotes).
    Replica la lógica de RecepcionStockView web.
    
    URL: /api/v1/inventario/movimientos/recepcion/
    Method: POST
    Payload esperado:
    {
        "proveedor_id": 1,
        "fecha_recepcion": "2023-10-27",
        "notas": "Recepción móvil",
        "detalles": [
            {
                "producto_id": 10,
                "compartimento_destino_id": "uuid...",
                "cantidad": 1, 
                "costo_unitario": 50000,
                "numero_serie": "SN-123", // Solo si es activo
                "fecha_fabricacion": "2023-01-01" // Opcional activo
            },
            {
                "producto_id": 15,
                "compartimento_destino_id": "uuid...",
                "cantidad": 50,
                "costo_unitario": 200,
                "numero_lote": "L-99", // Opcional lote
                "fecha_vencimiento": "2025-01-01" // Opcional lote
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanRecepcionarStock]

    def post(self, request):
        estacion = request.estacion_activa
        
        # --- PUENTE DE COMPATIBILIDAD CON CORE ---
        # core_registrar_actividad busca en session['active_estacion_id'].
        # Como IsEstacionActiva ya validó y obtuvo la estación, la inyectamos en la sesión
        # de este request para que el Mixin funcione sin cambios en el Core.
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id
        # -----------------------------------------

        data = request.data

        # 1. Validaciones de Cabecera
        proveedor_id = data.get('proveedor_id')
        fecha_recepcion_str = data.get('fecha_recepcion')
        notas = data.get('notas', '')
        detalles = data.get('detalles', [])

        if not proveedor_id or not fecha_recepcion_str or not detalles:
             return Response({"detail": "Faltan datos obligatorios."}, status=status.HTTP_400_BAD_REQUEST)

        proveedor = get_object_or_404(Proveedor, id=proveedor_id)
        fecha_recepcion = parse_date(fecha_recepcion_str)
        
        if not fecha_recepcion:
             return Response({"detail": "Formato de fecha inválido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            estado_disponible = Estado.objects.get(nombre='DISPONIBLE', tipo_estado__nombre='OPERATIVO')
        except Estado.DoesNotExist:
            return Response({"detail": "Error crítico: Estado 'DISPONIBLE' no encontrado."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Variables para Auditoría y Resumen
        nuevos_ids = {'activos': [], 'lotes': []}
        compartimentos_destino_set = set()
        cantidad_total_fisica = 0 

        try:
            with transaction.atomic():
                for index, item in enumerate(detalles):
                    # Validación de línea
                    prod_id = item.get('producto_id')
                    comp_id = item.get('compartimento_destino_id')
                    cantidad = int(item.get('cantidad', 0))
                    costo = item.get('costo_unitario')
                    
                    if not prod_id or not comp_id:
                        raise ValueError(f"Fila {index+1}: Datos incompletos.")

                    producto = get_object_or_404(Producto, id=prod_id, estacion=estacion)
                    compartimento = get_object_or_404(Compartimento, id=comp_id, ubicacion__estacion=estacion)

                    # Recolectar datos para auditoría
                    compartimentos_destino_set.add(compartimento.nombre)

                    # Actualizar Costo (Regla de Negocio)
                    if costo is not None:
                        producto.costo_compra = costo
                        producto.save(update_fields=['costo_compra'])

                    # Creación Polimórfica
                    if producto.es_serializado:
                        if cantidad != 1:
                             raise ValueError(f"Activo {producto.sku}: cantidad debe ser 1.")

                        activo_id = self._crear_activo(
                            producto, compartimento, proveedor, fecha_recepcion, 
                            notas, estado_disponible, item.get('numero_serie'), 
                            item.get('fecha_fabricacion'), request.user, estacion
                        )
                        nuevos_ids['activos'].append(activo_id)
                        cantidad_total_fisica += 1
                    else:
                        if cantidad <= 0:
                             raise ValueError(f"Insumo {producto.sku}: cantidad > 0.")
                        
                        lote_id = self._crear_lote(
                            producto, compartimento, proveedor, fecha_recepcion, 
                            notas, estado_disponible, cantidad, item.get('numero_lote'), 
                            item.get('fecha_vencimiento'), request.user, estacion
                        )
                        nuevos_ids['lotes'].append(lote_id)
                        cantidad_total_fisica += cantidad

                # --- AUDITORÍA DE SISTEMA (Usando tu Mixin) ---
                self._registrar_auditoria_sistema(
                    cantidad_total=cantidad_total_fisica,
                    nuevos_ids=nuevos_ids,
                    destinos=list(compartimentos_destino_set),
                    proveedor=proveedor,
                    notas=notas
                )

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Recepción guardada correctamente.",
            "resumen": {
                "activos_creados": len(nuevos_ids['activos']),
                "lotes_creados": len(nuevos_ids['lotes'])
            }
        }, status=status.HTTP_201_CREATED)

    # --- Métodos Auxiliares ---

    def _registrar_auditoria_sistema(self, cantidad_total, nuevos_ids, destinos, proveedor, notas):
        """Construye el mensaje y delega a self.auditar() del Mixin."""
        cant_activos = len(nuevos_ids['activos'])
        cant_insumos = cantidad_total - cant_activos
        
        partes_msg = []
        if cant_activos > 0:
            partes_msg.append(f"{cant_activos} Activo{'s' if cant_activos != 1 else ''}")
        if cant_insumos > 0:
            partes_msg.append(f"{cant_insumos} unidad{'es' if cant_insumos != 1 else ''} de Insumo{'s' if cant_insumos != 1 else ''}")
        
        detalle_texto = " y ".join(partes_msg) if partes_msg else "carga de inventario"
        
        texto_destinos = ""
        if destinos:
            if len(destinos) > 2:
                texto_destinos = f" en {', '.join(destinos[:2])} y otros"
            else:
                texto_destinos = f" en {', '.join(destinos)}"

        verbo_final = f"recepcionó {detalle_texto}{texto_destinos} desde"

        # Llamada al Mixin
        self.auditar(
            verbo=verbo_final,
            objetivo=proveedor, 
            detalles={
                'total_unidades': cantidad_total,
                'desglose': {'activos': cant_activos, 'insumos': cant_insumos},
                'destinos': destinos,
                'nuevos_activos_ids': nuevos_ids['activos'],
                'nuevos_lotes_ids': nuevos_ids['lotes'],
                'nota_recepcion': notas,
                'origen': 'APP MÓVIL'
            }
        )

    def _crear_activo(self, producto, compartimento, proveedor, fecha, notas, estado, serie, fecha_fab, usuario, estacion):
        activo = Activo.objects.create(
            producto=producto, estacion=estacion, compartimento=compartimento,
            proveedor=proveedor, estado=estado, numero_serie_fabricante=serie or "",
            fecha_fabricacion=parse_date(fecha_fab) if fecha_fab else None, fecha_recepcion=fecha
        )
        MovimientoInventario.objects.create(
            tipo_movimiento=TipoMovimiento.ENTRADA, usuario=usuario, estacion=estacion,
            proveedor_origen=proveedor, compartimento_destino=compartimento,
            activo=activo, cantidad_movida=1, notas=notas
        )
        return str(activo.id)

    def _crear_lote(self, producto, compartimento, proveedor, fecha, notas, estado, cantidad, n_lote, vencimiento, usuario, estacion):
        lote = LoteInsumo.objects.create(
            producto=producto, compartimento=compartimento, cantidad=cantidad,
            numero_lote_fabricante=n_lote,
            fecha_expiracion=parse_date(vencimiento) if vencimiento else None,
            fecha_recepcion=fecha, estado=estado
        )
        MovimientoInventario.objects.create(
            tipo_movimiento=TipoMovimiento.ENTRADA, usuario=usuario, estacion=estacion,
            proveedor_origen=proveedor, compartimento_destino=compartimento,
            lote_insumo=lote, cantidad_movida=cantidad, notas=notas
        )
        return str(lote.id)




class InventarioUbicacionListAPIView(APIView):
    """
    Lista las ubicaciones de la estación activa.
    Soporta filtro para excluir administrativas (útil para Recepción de Stock).
    URL: /api/v1/gestion_inventario/core/ubicaciones/?solo_fisicas=true
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva]

    def get(self, request):
        estacion = request.estacion_activa
        solo_fisicas = request.query_params.get('solo_fisicas') == 'true'

        qs = Ubicacion.objects.filter(estacion=estacion).select_related('tipo_ubicacion')
        
        if solo_fisicas:
            qs = qs.exclude(tipo_ubicacion__nombre='ADMINISTRATIVA')

        data = [
            {
                "id": str(u.id), # UUID a string
                "nombre": u.nombre,
                "tipo": u.tipo_ubicacion.nombre,
                "codigo": u.codigo
            }
            for u in qs.order_by('nombre')
        ]
        return Response(data, status=status.HTTP_200_OK)




class InventarioCompartimentoListAPIView(APIView):
    """
    Lista los compartimentos pertenecientes a una ubicación específica.
    Valida que la ubicación pertenezca a la estación activa por seguridad.
    URL: /api/v1/gestion_inventario/core/compartimentos/?ubicacion={uuid}
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva]

    def get(self, request):
        ubicacion_id = request.query_params.get('ubicacion')
        
        if not ubicacion_id:
            return Response({"detail": "Falta el parámetro 'ubicacion'."}, status=status.HTTP_400_BAD_REQUEST)

        # Filtro doble: por ID de ubicación Y por estación activa (Seguridad)
        compartimentos = Compartimento.objects.filter(
            ubicacion_id=ubicacion_id,
            ubicacion__estacion=request.estacion_activa
        ).order_by('nombre')

        data = [
            {
                "id": str(c.id),
                "nombre": c.nombre,
                "codigo": c.codigo
            }
            for c in compartimentos
        ]
        return Response(data, status=status.HTTP_200_OK)




class InventarioProveedorListAPIView(APIView):
    """
    Lista proveedores disponibles para la estación.
    Incluye:
    1. Proveedores Globales (estacion_creadora IS NULL)
    2. Proveedores Locales creados por esta estación.
    
    URL: /api/v1/gestion_inventario/core/proveedores/?search=bomberos
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva]

    def get(self, request):
        estacion = request.estacion_activa
        query = request.query_params.get('search', '').strip()

        # Lógica: Globales O Creados por mí
        filtros = Q(estacion_creadora__isnull=True) | Q(estacion_creadora=estacion)
        
        qs = Proveedor.objects.filter(filtros)

        if query:
            qs = qs.filter(nombre__icontains=query)

        data = [
            {
                "id": p.id,
                "nombre": p.nombre,
                "rut": p.rut,
                "es_local": p.estacion_creadora_id == estacion.id # Flag útil para UI
            }
            for p in qs.order_by('nombre')
        ]
        return Response(data, status=status.HTTP_200_OK)




class InventarioAnularExistenciaAPIView(AuditoriaMixin, APIView):
    """
    Endpoint para anular una existencia (Corrección de error de ingreso).
    Mueve el ítem a una ubicación administrativa 'ANULADO' y ajusta el stock a 0.
    
    URL: /api/v1/inventario/movimientos/anular/
    Method: POST
    Payload:
    {
        "tipo": "ACTIVO" | "LOTE",
        "id": "uuid-del-item",
        "motivo": "Error de digitación..."
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarBajasStock]

    def post(self, request):
        estacion = request.estacion_activa
        
        # 1. PUENTE DE AUDITORÍA (Vital para tu Mixin)
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        # 2. Obtener datos del request
        tipo = request.data.get('tipo') # 'ACTIVO' o 'LOTE'
        item_id = request.data.get('id')
        motivo = request.data.get('motivo', 'Anulación desde App Móvil')

        if not tipo or not item_id:
            return Response({"detail": "Faltan datos (tipo, id)."}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Buscar el objeto
        item = None
        codigo_repr = ""
        nombre_repr = ""

        if tipo == 'ACTIVO':
            item = get_object_or_404(Activo, id=item_id, estacion=estacion)
            codigo_repr = item.codigo_activo
            nombre_repr = item.producto.producto_global.nombre_oficial
        elif tipo == 'LOTE':
            item = get_object_or_404(LoteInsumo, id=item_id, compartimento__ubicacion__estacion=estacion)
            codigo_repr = item.codigo_lote
            nombre_repr = item.producto.producto_global.nombre_oficial
        else:
            return Response({"detail": "Tipo inválido."}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Validar Estado (Solo DISPONIBLE)
        if not item.estado or item.estado.nombre != 'DISPONIBLE':
            return Response(
                {"detail": f"El ítem no está DISPONIBLE (Estado actual: {item.estado.nombre if item.estado else 'Nulo'})."}, 
                status=status.HTTP_409_CONFLICT
            )

        try:
            with transaction.atomic():
                # A. Obtener destino usando TU función reutilizada
                # Esto asegura consistencia con la Web (mismo ID de compartimento)
                compartimento_destino = get_or_create_anulado_compartment(estacion)
                
                estado_anulado = Estado.objects.get(nombre='ANULADO POR ERROR')
                compartimento_origen = item.compartimento

                # B. Lógica de anulación (Vaciar cantidad si es lote)
                cantidad_ajuste = 0
                if tipo == 'LOTE':
                    cantidad_ajuste = item.cantidad * -1 # Restar todo
                    item.cantidad = 0
                else:
                    cantidad_ajuste = -1 # Activo es unitario
                
                # Mover al limbo
                item.estado = estado_anulado
                item.compartimento = compartimento_destino
                item.save()

                # C. Registrar Movimiento Técnico (AJUSTE)
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.AJUSTE,
                    usuario=request.user,
                    estacion=estacion,
                    compartimento_origen=compartimento_origen,
                    compartimento_destino=compartimento_destino,
                    activo=item if tipo == 'ACTIVO' else None,
                    lote_insumo=item if tipo == 'LOTE' else None,
                    cantidad_movida=cantidad_ajuste,
                    notas=f"Anulación Móvil: {motivo}"
                )

                # D. Auditoría de Sistema (Humana)
                self.auditar(
                    verbo="Anuló el registro de existencia (Error de Ingreso)",
                    objetivo=item,
                    objetivo_repr=f"{nombre_repr} ({codigo_repr})",
                    detalles={
                        'ubicacion_previa': compartimento_origen.nombre if compartimento_origen else "N/A",
                        'motivo': motivo,
                        'origen_accion': 'APP MÓVIL'
                    }
                )

            return Response({"message": "Ítem anulado correctamente."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class InventarioBajaExistenciaAPIView(AuditoriaMixin, APIView):
    """
    Endpoint para Dar de Baja una existencia (Fin de vida útil, daño irreparable, etc.).
    
    URL: /api/v1/inventario/movimientos/baja/
    Method: POST
    Payload:
    {
        "tipo": "ACTIVO" | "LOTE",
        "id": "uuid-del-item",
        "notas": "Motivo de la baja (Ej: Daño estructural en incendio)"
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarBajasStock]

    def post(self, request):
        estacion = request.estacion_activa
        
        # --- PUENTE AUDITORÍA ---
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        tipo = request.data.get('tipo')
        item_id = request.data.get('id')
        notas = request.data.get('notas', '')

        if not tipo or not item_id:
            return Response({"detail": "Faltan datos (tipo, id)."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Obtener el ítem
        item = None
        codigo_repr = ""
        nombre_repr = ""

        if tipo == 'ACTIVO':
            item = get_object_or_404(Activo, id=item_id, estacion=estacion)
            codigo_repr = item.codigo_activo
            nombre_repr = item.producto.producto_global.nombre_oficial
        elif tipo == 'LOTE':
            item = get_object_or_404(LoteInsumo, id=item_id, compartimento__ubicacion__estacion=estacion)
            codigo_repr = item.codigo_lote
            nombre_repr = item.producto.producto_global.nombre_oficial
        else:
            return Response({"detail": "Tipo inválido."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Validar Estado (Regla de Negocio)
        # Solo se permite dar de baja si está en control de la estación (no prestado fuera).
        estados_permitidos = ['DISPONIBLE', 'PENDIENTE REVISIÓN', 'EN REPARACIÓN']
        
        if not item.estado or item.estado.nombre not in estados_permitidos:
            return Response(
                {"detail": f"No se puede dar de baja. Estado actual: '{item.estado.nombre}'. Estados permitidos: {', '.join(estados_permitidos)}."}, 
                status=status.HTTP_409_CONFLICT
            )

        try:
            estado_baja = Estado.objects.get(nombre='DE BAJA')

            with transaction.atomic():
                # A. Actualizar Estado y Cantidad
                cantidad_movimiento = 0
                
                if tipo == 'LOTE':
                    cantidad_movimiento = item.cantidad * -1 # Salida total
                    item.cantidad = 0
                else:
                    cantidad_movimiento = -1
                
                item.estado = estado_baja
                item.save()

                # B. Auditoría Técnica (Movimiento SALIDA)
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.SALIDA,
                    usuario=request.user,
                    estacion=estacion,
                    compartimento_origen=item.compartimento,
                    # No hay destino físico en una baja
                    activo=item if tipo == 'ACTIVO' else None,
                    lote_insumo=item if tipo == 'LOTE' else None,
                    cantidad_movida=cantidad_movimiento,
                    notas=f"Baja Administrativa: {notas}"
                )

                # C. Auditoría de Sistema (Humana)
                self.auditar(
                    verbo="dio de baja del inventario operativo a",
                    objetivo=item,
                    objetivo_repr=f"{nombre_repr} ({codigo_repr})",
                    detalles={
                        'motivo_declarado': notas,
                        'tipo_existencia': tipo,
                        'origen_accion': 'APP MÓVIL'
                    }
                )

            return Response({"message": "Existencia dada de baja correctamente."}, status=status.HTTP_200_OK)

        except Estado.DoesNotExist:
            return Response({"detail": "Error crítico: Estado 'DE BAJA' no configurado."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class InventarioExtraviarActivoAPIView(AuditoriaMixin, APIView):
    """
    Endpoint para reportar un ACTIVO como extraviado.
    Maneja la lógica compleja de cierre de préstamos si el activo estaba prestado.
    
    URL: /api/v1/inventario/movimientos/extravio/
    Method: POST
    Payload:
    {
        "id": "uuid-del-activo",
        "notas": "Se perdió en el incendio forestal..."
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarBajasStock]

    def post(self, request):
        estacion = request.estacion_activa
        
        # --- PUENTE AUDITORÍA ---
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        activo_id = request.data.get('id')
        notas = request.data.get('notas', '')

        if not activo_id:
            return Response({"detail": "Falta el ID del activo."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Obtener Activo
        activo = get_object_or_404(Activo, id=activo_id, estacion=estacion)

        # 2. Validar Estado (Regla de Negocio)
        # Se permite reportar extravío incluso si está PRESTADO
        estados_permitidos = ['DISPONIBLE', 'PENDIENTE REVISIÓN', 'EN REPARACIÓN', 'EN PRÉSTAMO EXTERNO']
        
        if not activo.estado or activo.estado.nombre not in estados_permitidos:
            return Response(
                {"detail": f"Estado no válido para reporte de extravío: '{activo.estado.nombre}'. Estados permitidos: {', '.join(estados_permitidos)}."}, 
                status=status.HTTP_409_CONFLICT
            )

        try:
            estado_extraviado = Estado.objects.get(nombre='EXTRAVIADO')
            compartimento_limbo = get_or_create_extraviado_compartment(estacion)
            nombre_item = activo.producto.producto_global.nombre_oficial
            
            # Detectar si estaba prestado
            estaba_prestado = (activo.estado.nombre == 'EN PRÉSTAMO EXTERNO')

            with transaction.atomic():
                # A. Movimiento de Stock
                # Si estaba prestado, no restamos inventario físico (ya salió).
                cantidad_movimiento = 0 if estaba_prestado else -1
                compartimento_origen = None if estaba_prestado else activo.compartimento

                # Actualizar Activo
                activo.estado = estado_extraviado
                activo.compartimento = compartimento_limbo
                activo.save()

                # B. Registrar Movimiento (SALIDA)
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.SALIDA,
                    usuario=request.user,
                    estacion=estacion,
                    compartimento_origen=compartimento_origen,
                    compartimento_destino=compartimento_limbo,
                    activo=activo,
                    cantidad_movida=cantidad_movimiento,
                    notas=f"Extravío reportado (Móvil): {notas}"
                )

                # C. Gestión de Préstamos (Si aplica)
                if estaba_prestado:
                    self._registrar_perdida_en_prestamo(activo)

                # D. Auditoría Humana
                self.auditar(
                    verbo="reportó como extraviado a",
                    objetivo=activo,
                    objetivo_repr=f"{nombre_item} ({activo.codigo_activo})",
                    detalles={
                        'motivo': notas,
                        'estaba_prestado': estaba_prestado,
                        'origen_accion': 'APP MÓVIL'
                    }
                )

            return Response({"message": "Extravío reportado correctamente."}, status=status.HTTP_200_OK)

        except Estado.DoesNotExist:
            return Response({"detail": "Error crítico: Estado 'EXTRAVIADO' no configurado."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Helpers de Préstamos (Copiados de tu lógica web) ---

    def _registrar_perdida_en_prestamo(self, activo):
        """Busca préstamos activos y marca el ítem como extraviado."""
        detalles = PrestamoDetalle.objects.filter(
            activo=activo,
            prestamo__estado__in=[Prestamo.EstadoPrestamo.PENDIENTE, Prestamo.EstadoPrestamo.DEVUELTO_PARCIAL]
        )

        for detalle in detalles:
            detalle.cantidad_extraviada = 1 
            detalle.save()
            self._verificar_cierre_prestamo(detalle.prestamo)

    def _verificar_cierre_prestamo(self, prestamo):
        """Cierra el préstamo si todos los ítems están saldados (devueltos o extraviados)."""
        todos_saldados = all(d.esta_saldado for d in prestamo.items_prestados.all())
        
        if todos_saldados:
            prestamo.estado = Prestamo.EstadoPrestamo.COMPLETADO
            prestamo.save(update_fields=['estado', 'updated_at'])




class InventarioAjustarStockAPIView(AuditoriaMixin, APIView):
    """
    Endpoint para ajustar manualmente la cantidad de un Lote (Inventario Cíclico).
    
    URL: /api/v1/inventario/movimientos/ajustar/
    Method: POST
    Payload:
    {
        "id": "uuid-del-lote",
        "nueva_cantidad": 50,
        "notas": "Conteo cíclico semanal"
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarStockInterno]

    def post(self, request):
        estacion = request.estacion_activa
        
        # --- PUENTE AUDITORÍA ---
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        lote_id = request.data.get('id')
        nueva_cantidad = request.data.get('nueva_cantidad')
        notas = request.data.get('notas', '')

        # 1. Validaciones de Entrada
        if not lote_id or nueva_cantidad is None:
            return Response({"detail": "Faltan datos (id, nueva_cantidad)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            nueva_cantidad = int(nueva_cantidad)
            if nueva_cantidad < 0:
                raise ValueError
        except ValueError:
            return Response({"detail": "La cantidad debe ser un número entero no negativo."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Obtener Lote (Validando Estación)
        lote = get_object_or_404(LoteInsumo, id=lote_id, compartimento__ubicacion__estacion=estacion)

        # 3. Validar Estado (Regla de Negocio: Solo DISPONIBLE)
        if not lote.estado or lote.estado.nombre != 'DISPONIBLE':
            return Response(
                {"detail": f"Solo se puede ajustar stock de lotes 'DISPONIBLE'. Estado actual: {lote.estado.nombre if lote.estado else 'Nulo'}"}, 
                status=status.HTTP_409_CONFLICT
            )

        # 4. Cálculo de Diferencia
        cantidad_previa = lote.cantidad
        diferencia = nueva_cantidad - cantidad_previa

        if diferencia == 0:
            return Response({"message": "No hubo cambios en el stock."}, status=status.HTTP_200_OK)

        try:
            with transaction.atomic():
                # A. Actualizar Lote
                lote.cantidad = nueva_cantidad
                lote.save(update_fields=['cantidad', 'updated_at'])

                # B. Registrar Movimiento Técnico (AJUSTE)
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.AJUSTE,
                    usuario=request.user,
                    estacion=estacion,
                    compartimento_origen=lote.compartimento, # El origen es donde estaba
                    lote_insumo=lote,
                    cantidad_movida=diferencia,
                    notas=notas
                )

                # C. Auditoría de Sistema (Humana)
                tipo_ajuste = "aumentó" if diferencia > 0 else "disminuyó"
                nombre_prod = lote.producto.producto_global.nombre_oficial
                
                self.auditar(
                    verbo=f"ajustó manualmente el stock ({tipo_ajuste}) de",
                    objetivo=lote,
                    objetivo_repr=f"{nombre_prod} ({lote.codigo_lote})",
                    detalles={
                        'cantidad_previa': cantidad_previa,
                        'cantidad_nueva': nueva_cantidad,
                        'diferencia': diferencia,
                        'motivo': notas,
                        'origen_accion': 'APP MÓVIL'
                    }
                )

            return Response({
                "message": f"Stock ajustado correctamente: {cantidad_previa} -> {nueva_cantidad}.",
                "nueva_cantidad": nueva_cantidad
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class InventarioConsumirStockAPIView(AuditoriaMixin, APIView):
    """
    Endpoint para registrar consumo de stock (Salida de lotes).
    
    URL: /api/v1/inventario/movimientos/consumir/
    Method: POST
    Payload:
    {
        "id": "uuid-del-lote",
        "cantidad": 5,
        "notas": "Uso en ejercicio de la academia"
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarStockInterno]

    def post(self, request):
        estacion = request.estacion_activa
        
        # --- PUENTE AUDITORÍA ---
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        lote_id = request.data.get('id')
        cantidad_consumir = request.data.get('cantidad')
        notas = request.data.get('notas', '')

        # 1. Validaciones de Entrada
        if not lote_id or cantidad_consumir is None:
            return Response({"detail": "Faltan datos (id, cantidad)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cantidad_consumir = int(cantidad_consumir)
            if cantidad_consumir <= 0:
                raise ValueError
        except ValueError:
            return Response({"detail": "La cantidad a consumir debe ser mayor a 0."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Obtener Lote (Validando Estación)
        lote = get_object_or_404(LoteInsumo, id=lote_id, compartimento__ubicacion__estacion=estacion)

        # 3. Validar Estado (Regla de Negocio: DISPONIBLE o EN PRÉSTAMO EXTERNO)
        estados_permitidos = ['DISPONIBLE', 'EN PRÉSTAMO EXTERNO']
        if not lote.estado or lote.estado.nombre not in estados_permitidos:
            return Response(
                {"detail": f"El lote no está en un estado válido para consumo ({lote.estado.nombre if lote.estado else 'Nulo'}). Estados permitidos: {', '.join(estados_permitidos)}."}, 
                status=status.HTTP_409_CONFLICT
            )

        # 4. Validar Stock Suficiente
        if lote.cantidad < cantidad_consumir:
            return Response(
                {"detail": f"Stock insuficiente. Disponible: {lote.cantidad}, Solicitado: {cantidad_consumir}."}, 
                status=status.HTTP_409_CONFLICT
            )

        try:
            with transaction.atomic():
                # A. Actualizar Lote
                lote.cantidad -= cantidad_consumir
                lote.save(update_fields=['cantidad', 'updated_at'])

                # B. Registrar Movimiento Técnico (SALIDA)
                MovimientoInventario.objects.create(
                    tipo_movimiento=TipoMovimiento.SALIDA,
                    usuario=request.user,
                    estacion=estacion,
                    compartimento_origen=lote.compartimento,
                    lote_insumo=lote,
                    cantidad_movida=cantidad_consumir * -1, # Negativo para salidas
                    notas=notas
                )

                # C. Auditoría de Sistema (Humana)
                nombre_prod = lote.producto.producto_global.nombre_oficial
                
                self.auditar(
                    verbo=f"registró el consumo interno de {cantidad_consumir} unidad(es) de",
                    objetivo=lote,
                    objetivo_repr=f"{nombre_prod} ({lote.codigo_lote})",
                    detalles={
                        'cantidad_consumida': cantidad_consumir,
                        'cantidad_restante': lote.cantidad,
                        'motivo_uso': notas,
                        'origen_accion': 'APP MÓVIL'
                    }
                )

            return Response({
                "message": f"Consumo registrado correctamente. Nuevo stock: {lote.cantidad}.",
                "stock_restante": lote.cantidad
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




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
            estacion=estacion,
            estado__nombre__in=['DISPONIBLE', 'EN PRÉSTAMO EXTERNO', 'PENDIENTE REVISIÓN']
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

            # --- VALIDACIÓN DE ESTADO (Regla de Negocio) ---
            estados_permitidos = ['DISPONIBLE', 'EN PRÉSTAMO EXTERNO', 'PENDIENTE REVISIÓN']
            
            if not activo.estado or activo.estado.nombre not in estados_permitidos:
                estado_actual = activo.estado.nombre if activo.estado else "SIN ESTADO"
                return Response({
                    'status': 'error',
                    'message': f'No se puede agregar el activo al plan. Su estado es "{estado_actual}". Solo se permiten: {", ".join(estados_permitidos)}.'
                }, status=status.HTTP_400_BAD_REQUEST)
            # -----------------------------------------------

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




class MantenimientoCambiarEstadoOrdenAPIView(OrdenValidacionMixin, AuditoriaMixin, APIView):
    """
    Endpoint API (DRF) encargado de la orquestación del ciclo de vida de una Orden de Mantenimiento.
    
    Responsabilidades Técnicas:
    - Gestión de la máquina de estados de la orden (Iniciar, Finalizar, Cancelar, Asumir).
    - Validación estricta de integridad referencial antes del cierre (cobertura total de activos).
    - Sincronización automática del estado de los activos vinculados (ej. pasar a 'EN REPARACIÓN').
    - Control de seguridad multi-tenant (aislamiento por estación).
    """
    
    # --- Configuración de Seguridad ---
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request, pk):
        """
        Procesar la transición de estado solicitada.
        
        Flujo de Ejecución:
        1. Establecer contexto de auditoría (puente sesión-API).
        2. Recuperar y validar la orden dentro del alcance de la estación activa.
        3. Validar reglas de negocio específicas para la asignación de responsabilidad.
        4. Ejecutar la transición de estado dentro de un bloque transaccional atómico.
        5. Disparar efectos secundarios en los activos (cambio de estado masivo).
        """
        try:
            estacion = request.estacion_activa
            
            # --- Puente de Auditoría ---
            # Inyectar el ID de la estación en la sesión si no existe, garantizando
            # que el mixin AuditoriaMixin tenga el contexto necesario para registrar el evento.
            if not request.session.get('active_estacion_id'):
                request.session['active_estacion_id'] = estacion.id

            # Recuperación Segura (Tenant Isolation)
            # Garantizar que solo se manipulen órdenes pertenecientes a la estación del request.
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=estacion)
            
            accion = request.data.get('accion')
            verbo_auditoria = ""

            # Validación de Reglas de Negocio (Mixin)
            # Verificar si el usuario tiene privilegios para realizar la acción (especialmente 'asumir').
            self.validar_responsabilidad_orden(orden, request.user, accion=accion)

            # Inicio de Transacción Atómica
            with transaction.atomic():
                
                # CASO 1: ASUMIR RESPONSABILIDAD
                if accion == 'asumir':
                    orden.responsable = request.user
                    # Transición implícita: Si está pendiente, iniciar automáticamente para agilizar flujo UX.
                    if orden.estado == OrdenMantenimiento.EstadoOrden.PENDIENTE:
                        orden.estado = OrdenMantenimiento.EstadoOrden.EN_CURSO
                    
                    orden.save()
                    verbo_auditoria = "asumió la responsabilidad de la orden"

                # CASO 2: INICIAR EJECUCIÓN
                elif accion == 'iniciar':
                    # Validación de Precondiciones
                    if orden.estado != OrdenMantenimiento.EstadoOrden.PENDIENTE:
                        return Response({'message': 'La orden no está en estado pendiente.'}, status=status.HTTP_400_BAD_REQUEST)

                    if orden.activos_afectados.count() == 0:
                        return Response({'message': 'No se puede iniciar una orden sin activos asignados.'}, status=status.HTTP_400_BAD_REQUEST)

                    # Actualización de la Orden
                    orden.estado = OrdenMantenimiento.EstadoOrden.EN_CURSO
                    orden.save()
                    verbo_auditoria = "inició la ejecución de la Orden de Mantenimiento"

                    # Efecto Secundario: Bloqueo de Activos
                    # Marcar masivamente todos los activos involucrados como 'EN REPARACIÓN'
                    try:
                        estado_reparacion = Estado.objects.get(nombre__iexact="EN REPARACIÓN")
                        orden.activos_afectados.update(estado=estado_reparacion)
                    except Estado.DoesNotExist:
                        pass # Opcional: Loguear advertencia de configuración faltante

                # CASO 3: FINALIZAR ORDEN (Cierre Técnico)
                elif accion == 'finalizar':
                    if orden.estado != OrdenMantenimiento.EstadoOrden.EN_CURSO:
                        return Response({'message': 'Solo se pueden finalizar órdenes en curso.'}, status=status.HTTP_400_BAD_REQUEST)

                    # --- Validación de Integridad Operativa ---
                    # Regla Crítica: No permitir cierre si existen activos sin registro de trabajo asociado.
                    total_activos = orden.activos_afectados.count()

                    # Contar activos únicos que poseen al menos un registro de intervención.
                    activos_con_trabajo = orden.registros.values('activo_id').distinct().count()

                    if activos_con_trabajo < total_activos:
                        pendientes = total_activos - activos_con_trabajo
                        return Response({
                            'status': 'error', 
                            'message': f'Imposible finalizar: Faltan registros de mantenimiento en {pendientes} activo(s). Todos los activos deben ser procesados.'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    # --------------------------------

                    # Cierre de la Orden
                    orden.estado = OrdenMantenimiento.EstadoOrden.REALIZADA
                    orden.fecha_cierre = timezone.now()
                    orden.save()
                    verbo_auditoria = "finalizó exitosamente la Orden de Mantenimiento"

                    # Efecto Secundario: Liberación de Activos
                    # Retornar los activos al estado operativo 'DISPONIBLE'.
                    # Nota: En implementaciones complejas, esto podría depender del resultado individual de cada activo.
                    try:
                        estado_disponible = Estado.objects.get(nombre__iexact="DISPONIBLE")
                        orden.activos_afectados.update(estado=estado_disponible)
                    except Estado.DoesNotExist:
                        pass

                # CASO 4: CANCELAR ORDEN
                elif accion == 'cancelar':
                    orden.estado = OrdenMantenimiento.EstadoOrden.CANCELADA
                    orden.fecha_cierre = timezone.now()
                    orden.save()
                    verbo_auditoria = "canceló la Orden de Mantenimiento"

                    # Efecto Secundario: Liberación de Activos (Revertir bloqueo)
                    try:
                        estado_disponible = Estado.objects.get(nombre__iexact="DISPONIBLE")
                        orden.activos_afectados.update(estado=estado_disponible)
                    except Estado.DoesNotExist:
                        pass

                else:
                    return Response({'message': 'Acción no válida (use iniciar, finalizar, cancelar, asumir).'}, status=status.HTTP_400_BAD_REQUEST)

                # --- Registro de Auditoría ---
                self.auditar(
                    verbo=verbo_auditoria,
                    objetivo=orden,
                    objetivo_repr=f"Orden #{orden.id} ({orden.tipo_orden})",
                    detalles={
                        'nuevo_estado': orden.estado,
                        'origen_accion': 'APP MÓVIL / API'
                    }
                )

            return Response({'status': 'ok', 'message': 'Estado actualizado correctamente.'})
        
        except Exception as e:
            # Captura de errores críticos del servidor
            return Response({'error': f'Error procesando la orden: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MantenimientoRegistrarTareaAPIView(OrdenValidacionMixin, APIView):
    """
    Endpoint API encargado del registro granular de actividades de mantenimiento.
    
    Permite a los técnicos reportar el resultado (éxito/fallo) de la intervención
    sobre un activo específico dentro de una Orden de Mantenimiento.
    
    Lógica de Negocio Crítica:
    - Gestión de Concurrencia de Estados: Implementa un mecanismo de "bloqueo compartido"
      lógico. Un activo solo retorna al estado 'DISPONIBLE' si no existen otras órdenes
      de trabajo activas pendientes sobre el mismo recurso.
    - Sincronización con Planes Preventivos: Actualiza los contadores de mantenimiento
      (fecha, horómetro) para el recálculo de próximas fechas de vencimiento.
    """
    
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request, pk):
        """
        Procesar el reporte de una tarea de mantenimiento.
        
        Flujo de Ejecución:
        1. Validación de contexto (Estación, Responsabilidad del Técnico, Estado de la Orden).
        2. Validación de pertenencia del activo a la orden.
        3. Persistencia del registro de trabajo (Upsert).
        4. Evaluación y transición del estado del activo (Lógica de liberación condicional).
        5. Actualización de metadatos de planificación (si aplica).
        6. Auditoría incremental del avance.
        """
        try:
            estacion = request.estacion_activa
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=estacion)

            # 1. Validación de Seguridad y Reglas de Negocio
            # Verificar que el usuario solicitante sea el responsable asignado a la orden.
            self.validar_responsabilidad_orden(orden, request.user)

            # Verificar que la orden se encuentre en etapa de ejecución.
            if orden.estado != OrdenMantenimiento.EstadoOrden.EN_CURSO:
                return Response({'message': 'Debe INICIAR la orden antes de registrar tareas.'}, status=status.HTTP_400_BAD_REQUEST)

            # Extracción de datos del payload
            activo_id = request.data.get('activo_id')
            notas = request.data.get('notas')
            # Default a True si no se especifica, asumiendo éxito por defecto en flujo rápido
            fue_exitoso = request.data.get('exitoso', True)

            activo = get_object_or_404(Activo, pk=activo_id, estacion=estacion)

            # 2. Validación de Integridad Referencial
            # Asegurar que el activo reportado sea parte del alcance original de la orden.
            if not orden.activos_afectados.filter(pk=activo_id).exists():
                return Response({'status': 'error', 'message': 'El activo no pertenece a esta orden.'}, status=400)

            # 3. Persistencia del Registro (Upsert)
            # Utilizar update_or_create para permitir correcciones sobre un reporte existente
            # o la creación de uno nuevo.
            registro, created = RegistroMantenimiento.objects.update_or_create(
                orden_mantenimiento=orden,
                activo=activo,
                defaults={
                    'usuario_ejecutor': request.user,
                    'notas': notas,
                    'fue_exitoso': fue_exitoso,
                    'fecha_ejecucion': timezone.now()
                }
            )

            # 4. Gestión de Estado del Activo (State Machine)
            if fue_exitoso:
                # Lógica de Liberación Condicional (Concurrencia):
                # Antes de liberar el activo a 'DISPONIBLE', consultar si existen OTRAS órdenes
                # de mantenimiento activas (Pendientes o En Curso) que involucren este mismo recurso,
                # excluyendo la orden actual que se está procesando.
                otras_ordenes_activas = OrdenMantenimiento.objects.filter(
                    estacion=estacion,
                    activos_afectados=activo,
                    estado__in=[
                        OrdenMantenimiento.EstadoOrden.PENDIENTE, 
                        OrdenMantenimiento.EstadoOrden.EN_CURSO
                    ]
                ).exclude(id=orden.id).exists()

                if otras_ordenes_activas:
                    # CONCURRENCIA DETECTADA:
                    # No cambiar el estado. Se asume que el activo debe permanecer 'EN REPARACIÓN'
                    # o bloqueado hasta que se resuelvan las órdenes restantes.
                    pass 
                else:
                    # LIBERACIÓN:
                    # Si no hay dependencias pendientes, restaurar la operatividad del activo.
                    try:
                        estado_disponible = Estado.objects.get(nombre__iexact="DISPONIBLE")
                        activo.estado = estado_disponible
                    except Estado.DoesNotExist:
                        pass # Manejo silencioso si la configuración de estados es inconsistente
            else:
                # MANEJO DE FALLO:
                # Si la mantención no fue exitosa, el activo queda inoperativo ('EN REVISIÓN' o 'DAÑADO')
                # independientemente de otras órdenes, ya que su integridad física no está garantizada.
                try:
                    estado_malo = Estado.objects.get(nombre__iexact="EN REVISIÓN") 
                    activo.estado = estado_malo
                except Estado.DoesNotExist:
                    pass
            
            # Persistir cambio de estado del activo
            activo.save()

            # 5. Sincronización de Planificación
            # Si la orden deriva de un plan preventivo y la ejecución fue exitosa, actualizar
            # la fecha de última mantención y el horómetro registrado para reiniciar el ciclo de programación.
            if fue_exitoso and orden.plan_origen:
                PlanActivoConfig.objects.filter(
                    plan=orden.plan_origen, 
                    activo=activo
                ).update(
                    fecha_ultima_mantencion=timezone.now(),
                    horas_uso_en_ultima_mantencion=activo.horas_uso_totales
                )

            # 6. Auditoría Incremental
            # Registrar el avance específico sin saturar el log principal de la orden,
            # utilizando una descripción concisa de la acción.
            accion_txt = "Tarea exitosa" if fue_exitoso else "Falla reportada"

            auditar_modificacion_incremental(
                request=request,
                plan=orden, # Asociar el evento a la Orden como entidad padre
                accion_detalle=f"{accion_txt} en {activo.codigo_activo}"
            )

            return Response({'status': 'ok', 'message': 'Registro guardado.'})
        
        except Exception as e:
            # Captura de errores no controlados para respuesta estándar API
            return Response({'error': f'Error guardando tarea: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class MantenimientoBuscarActivoParaOrdenAPIView(APIView):
    """
    Endpoint de búsqueda especializado para identificar y seleccionar activos candidatos
    a ser incorporados en una Orden de Mantenimiento.
    
    Características de Filtrado:
    - Contexto: Solo busca activos dentro de la estación activa.
    - Estado Operativo: Filtra activos elegibles (Disponibles, En Préstamo o Pendientes de Revisión).
    - Exclusión Lógica: Omite activos que ya están vinculados a la orden actual para evitar duplicidad.
    - Búsqueda Textual: Coincidencia parcial por Código de Activo o Nombre del Producto Global.
    """
    
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def get(self, request, *args, **kwargs):
        """
        Procesar la solicitud de búsqueda de activos.
        
        Retorna una lista ligera (serialización manual optimizada) de los primeros 10 candidatos
        que coincidan con el criterio de búsqueda, incluyendo metadatos de ubicación para desambiguación.
        """
        query = request.GET.get('q', '').strip()
        orden_id = request.GET.get('orden_id')
        estacion = request.estacion_activa

        # Validación de entrada mínima para evitar consultas costosas vacías
        if not query or len(query) < 2:
            return Response({'results': []})

        # Recuperación segura de la orden contexto (Tenant Isolation)
        orden = get_object_or_404(OrdenMantenimiento, id=orden_id, estacion=estacion)
        
        # Construcción de la consulta compleja
        activos = Activo.objects.filter(
            estacion=estacion,
            # Regla de Negocio: Solo ciertos estados son válidos para iniciar mantenimiento
            estado__nombre__in=['DISPONIBLE', 'EN PRÉSTAMO EXTERNO', 'PENDIENTE REVISIÓN']
        ).filter(
            # Búsqueda OR: Código interno O Nombre comercial
            Q(codigo_activo__icontains=query) | 
            Q(producto__producto_global__nombre_oficial__icontains=query)
        ).exclude(
            # Excluir activos que ya forman parte de la relación ManyToMany de esta orden
            ordenes_mantenimiento=orden
        ).select_related(
            # Optimización Eager Loading
            'producto__producto_global', 
            'compartimento__ubicacion'
        )[:10] # Límite estricto para rendimiento de UI (Typeahead)

        # Serialización manual para respuesta JSON ligera
        results = []
        for activo in activos:
            # Formateo de ubicación jerárquica
            ubicacion_str = f"{activo.compartimento.ubicacion.nombre} > {activo.compartimento.nombre}" if activo.compartimento else "Sin ubicación"
            
            results.append({
                'id': activo.id,
                'codigo': activo.codigo_activo,
                'nombre': activo.producto.producto_global.nombre_oficial,
                'ubicacion': ubicacion_str,
                # Manejo seguro de URL de imagen con fallback implícito (None)
                'imagen_url': activo.producto.producto_global.imagen_thumb_small.url if activo.producto.producto_global.imagen_thumb_small else None
            })

        return Response({'results': results})




class MantenimientoAnadirActivoOrdenAPIView(OrdenValidacionMixin, APIView):
    """
    Endpoint para vincular un activo existente a una Orden de Mantenimiento en estado PENDIENTE.
    
    Validaciones Críticas:
    1. El usuario debe tener responsabilidad sobre la orden.
    2. La orden debe ser editable (Estado PENDIENTE).
    3. El activo debe encontrarse en un estado operativo compatible con la intervención.
    """
    
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request, pk):
        """
        Procesar la vinculación de un activo a la orden.
        
        Realiza validaciones de estado cruzadas (Orden vs Activo) y registra el evento
        en la auditoría incremental de la orden.
        """
        try:
            estacion = request.estacion_activa
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=estacion)

            # 1. Validación de Permisos y Responsabilidad
            self.validar_responsabilidad_orden(orden, request.user)

            # 2. Validación de Ciclo de Vida de la Orden
            if orden.estado != OrdenMantenimiento.EstadoOrden.PENDIENTE:
                return Response({'message': 'Solo se pueden agregar activos a órdenes PENDIENTES.'}, status=status.HTTP_400_BAD_REQUEST)

            activo_id = request.data.get('activo_id')
            activo = get_object_or_404(Activo, pk=activo_id, estacion=estacion)

            # 3. Validación de Estado del Activo
            # Impedir agregar activos dados de baja o en estados no operativos (ej. EXTRAVIADO)
            estados_permitidos = ['DISPONIBLE', 'EN PRÉSTAMO EXTERNO', 'PENDIENTE REVISIÓN']
            
            if not activo.estado or activo.estado.nombre not in estados_permitidos:
                estado_actual = activo.estado.nombre if activo.estado else "SIN ESTADO"
                return Response({
                    'status': 'error',
                    'message': f'No se puede agregar el activo. Su estado es "{estado_actual}". Solo se permiten: {", ".join(estados_permitidos)}.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 4. Persistencia (Relación Many-to-Many)
            orden.activos_afectados.add(activo)

            # 5. Auditoría Incremental
            # Registrar la modificación del alcance de la orden.
            auditar_modificacion_incremental(
                request=request,
                plan=orden, 
                accion_detalle=f"Añadió a la orden: {activo.codigo_activo}"
            )
            return Response({'status': 'ok', 'message': f"Activo {activo.codigo_activo} añadido."})
        
        except Exception as e:
            return Response({'error': f'Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MantenimientoQuitarActivoOrdenAPIView(OrdenValidacionMixin, APIView):
    """
    Endpoint para desvincular un activo de una Orden de Mantenimiento.
    
    Permite corregir el alcance de la orden antes de su inicio.
    Restringido exclusivamente a órdenes en estado PENDIENTE para asegurar la integridad
    de los registros de trabajo una vez iniciada la ejecución.
    """
    
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request, pk):
        """
        Procesar la desvinculación de un activo.
        """
        try:
            estacion = request.estacion_activa
            orden = get_object_or_404(OrdenMantenimiento, pk=pk, estacion=estacion)

            # 1. Validación de Permisos
            self.validar_responsabilidad_orden(orden, request.user)

            # 2. Validación de Ciclo de Vida
            # Una vez iniciada la orden, el alcance se congela para mantener trazabilidad histórica.
            if orden.estado != OrdenMantenimiento.EstadoOrden.PENDIENTE:
                return Response({'message': 'Solo se pueden quitar activos de órdenes PENDIENTES.'}, status=status.HTTP_400_BAD_REQUEST)

            activo_id = request.data.get('activo_id')
            activo = get_object_or_404(Activo, pk=activo_id, estacion=estacion)

            # 3. Persistencia (Eliminación de Relación)
            orden.activos_afectados.remove(activo)

            # 4. Auditoría Incremental
            auditar_modificacion_incremental(
                request=request,
                plan=orden, 
                accion_detalle=f"Quitó de la orden: {activo.codigo_activo}"
            )
            return Response({'status': 'ok', 'message': f"Activo {activo.codigo_activo} quitado."})
        
        except Exception as e:
            return Response({'error': f'Error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class MantenimientoOrdenListAPIView(APIView):
    """
    Bandeja de entrada de Órdenes de Trabajo para la App.
    Soporta pestañas de estado (Activos/Historial) y búsqueda.
    
    URL: /api/v1/mantenimiento/ordenes/?estado=activos&q=camion
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerOrdenes]

    def get(self, request):
        estacion = request.estacion_activa
        filtro_estado = request.query_params.get('estado', 'activos')
        query = request.query_params.get('q', '').strip()

        qs = OrdenMantenimiento.objects.filter(estacion=estacion).select_related(
            'plan_origen', 
            'responsable'
        )

        # Filtro de Estado usando las constantes del modelo
        if filtro_estado == 'historial':
            qs = qs.filter(estado__in=[
                OrdenMantenimiento.EstadoOrden.REALIZADA,
                OrdenMantenimiento.EstadoOrden.CANCELADA
            ]).order_by('-fecha_cierre', '-fecha_programada')
        else:
            qs = qs.filter(estado__in=[
                OrdenMantenimiento.EstadoOrden.PENDIENTE,
                OrdenMantenimiento.EstadoOrden.EN_CURSO
            ]).order_by('fecha_programada')

        # Búsqueda
        if query:
            if query.isdigit():
                qs = qs.filter(id=query)
            else:
                qs = qs.filter(
                    Q(plan_origen__nombre__icontains=query) | 
                    Q(tipo_orden__icontains=query)
                )

        data = []
        hoy = timezone.now().date()

        for orden in qs[:50]:
            # Corrección de tipos fecha (Datetime vs Date)
            es_vencido = False
            if orden.estado != OrdenMantenimiento.EstadoOrden.REALIZADA and orden.fecha_programada:
                f_prog = orden.fecha_programada
                if hasattr(f_prog, 'date'):
                    f_prog = f_prog.date()
                es_vencido = f_prog < hoy

            # Título dinámico basado estrictamente en campos existentes
            titulo = f"Orden #{orden.id}"
            if orden.plan_origen:
                titulo = orden.plan_origen.nombre # Asumiendo que PlanMantenimiento tiene 'nombre'
            elif orden.tipo_orden == OrdenMantenimiento.TipoOrden.CORRECTIVA:
                titulo = "Mantenimiento Correctivo"

            data.append({
                "id": orden.id,
                "titulo": titulo,
                "tipo": orden.get_tipo_orden_display(),
                "tipo_codigo": orden.tipo_orden,
                "estado": orden.get_estado_display(),
                "estado_codigo": orden.estado,
                "fecha_programada": orden.fecha_programada.strftime('%d/%m/%Y') if orden.fecha_programada else "Sin fecha",
                "responsable": orden.responsable.get_full_name if orden.responsable else "Sin asignar",
                "es_responsable": (orden.responsable == request.user),
                "es_vencido": es_vencido,
                "activos_count": orden.activos_afectados.count()
            })

        return Response(data, status=status.HTTP_200_OK)


class MantenimientoOrdenCorrectivaCreateAPIView(AuditoriaMixin, APIView):
    """
    Endpoint para crear una Orden de Mantenimiento Correctiva.
    
    URL: /api/v1/mantenimiento/ordenes/crear/
    Method: POST
    Payload:
    {
        "descripcion": "Fuga de aceite en motor",
        "fecha_programada": "2023-11-01" (Opcional, default hoy),
        "responsable_id": 5 (Opcional)
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanGestionarOrdenes]

    def post(self, request):
        estacion = request.estacion_activa
        
        # Puente Auditoría
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        data = request.data
        
        try:
            with transaction.atomic():
                orden = OrdenMantenimiento()
                orden.estacion = estacion
                orden.tipo_orden = OrdenMantenimiento.TipoOrden.CORRECTIVA
                orden.estado = OrdenMantenimiento.EstadoOrden.PENDIENTE
                
                # NO asignamos descripción porque el campo no existe en el modelo.
                
                if data.get('fecha_programada'):
                    orden.fecha_programada = parse_date(data.get('fecha_programada'))
                else:
                    orden.fecha_programada = timezone.now()

                if data.get('responsable_id'):
                    # User model import dinámico para evitar circular imports
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    responsable = get_object_or_404(User, id=data.get('responsable_id'))
                    orden.responsable = responsable
                else:
                    orden.responsable = request.user

                orden.save()

                # Auditoría
                self.auditar(
                    verbo="creó una nueva Orden de Mantenimiento Correctiva",
                    objetivo=orden,
                    objetivo_repr=f"Orden #{orden.id}",
                    detalles={
                        'origen_accion': 'APP MÓVIL',
                        'tipo': 'CORRECTIVA (Manual)'
                    }
                )

            return Response({
                "message": f"Orden #{orden.id} creada correctamente.",
                "id": orden.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class MantenimientoOrdenDetalleAPIView(APIView):
    """
    Endpoint de detalle de una Orden de Trabajo.
    Muestra el progreso y el estado de cada activo involucrado (Pendiente vs Realizado).
    
    URL: /api/v1/mantenimiento/ordenes/<int:pk>/detalle/
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerOrdenes]

    def get(self, request, pk):
        estacion = request.estacion_activa
        orden = get_object_or_404(OrdenMantenimiento, id=pk, estacion=estacion)

        # Activos y Registros
        activos = orden.activos_afectados.select_related(
            'producto__producto_global', 
            'compartimento__ubicacion'
        ).order_by('producto__producto_global__nombre_oficial')

        # Optimización: Mapa de registros existentes
        # Asume que el modelo RegistroMantenimiento tiene FK 'activo' y 'orden'
        registros_existentes = {
            reg.activo_id: reg for reg in orden.registros.all() 
        }

        lista_activos = []
        for activo in activos:
            registro = registros_existentes.get(activo.id)
            esta_completado = registro is not None

            lista_activos.append({
                "id": str(activo.id),
                "codigo": activo.codigo_activo,
                "nombre": activo.producto.producto_global.nombre_oficial,
                "ubicacion": f"{activo.compartimento.ubicacion.nombre} > {activo.compartimento.nombre}" if activo.compartimento else "Sin ubicación",
                "estado_trabajo": "COMPLETADO" if esta_completado else "PENDIENTE",
                "estado_color": "green" if esta_completado else "gray",
                "registro_id": registro.id if registro else None
            })

        total = len(activos)
        completados = len(registros_existentes)
        porcentaje = int((completados / total) * 100) if total > 0 else 0

        # Lógica de Descripción basada estrictamente en el modelo
        titulo = f"Orden #{orden.id}"
        descripcion_texto = "Sin descripción disponible"

        if orden.plan_origen:
            titulo = orden.plan_origen.nombre
            descripcion_texto = f"Generada por plan: {orden.plan_origen.nombre}"
        elif orden.tipo_orden == OrdenMantenimiento.TipoOrden.CORRECTIVA:
            titulo = "Mantenimiento Correctivo"
            descripcion_texto = "Orden generada manualmente"

        data = {
            "cabecera": {
                "id": orden.id,
                "titulo": titulo,
                "descripcion": descripcion_texto, # Variable calculada, no de BD
                "tipo": orden.get_tipo_orden_display(),
                "estado": orden.get_estado_display(),
                "estado_codigo": orden.estado,
                "fecha_programada": orden.fecha_programada.strftime('%d/%m/%Y'),
                "responsable": orden.responsable.get_full_name if orden.responsable else "Sin asignar",
                "es_responsable": (orden.responsable == request.user),
            },
            "progreso": {
                "total": total,
                "completados": completados,
                "porcentaje": porcentaje,
                "texto": f"{completados}/{total} Activos"
            },
            "items": lista_activos
        }

        return Response(data, status=status.HTTP_200_OK)




class UsuarioListAPIView(APIView):
    """
    Endpoint unificado para listar usuarios (Voluntarios) de la estación activa.
    Útil para: Directorio de voluntarios, selectores de Ficha Médica, Asignaciones, etc.
    
    Filtros:
    - ?q= : Busca por Nombre, Apellido, Email o RUT.
    - ?rol= : Filtra por ID de rol (opcional, útil si quieres buscar solo Oficiales).
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerUsuarios]

    def get(self, request):
        estacion = request.estacion_activa
        query = request.query_params.get('q', '').strip()
        rol_id = request.query_params.get('rol')

        # 1. Base Query: Miembros Activos/Inactivos de la estación (Excluye Finalizados)
        qs = Membresia.objects.filter(
            estacion=estacion,
            estado__in=[Membresia.Estado.ACTIVO, Membresia.Estado.INACTIVO]
        ).select_related('usuario').prefetch_related('roles')

        # 2. Búsqueda por Texto (Nombre, Apellido, Email, RUT)
        if query:
            qs = qs.filter(
                Q(usuario__first_name__icontains=query) |
                Q(usuario__last_name__icontains=query) |
                Q(usuario__email__icontains=query) |
                # Asumo que el campo en tu modelo Usuario se llama 'rut' o 'run'
                Q(usuario__rut__icontains=query) 
            )

        # 3. Filtro por Rol (Opcional)
        if rol_id and rol_id.isdigit():
            qs = qs.filter(roles__id=int(rol_id))

        # Ordenar alfabéticamente
        qs = qs.order_by('usuario__first_name', 'usuario__last_name').distinct()

        # 4. Serialización
        data = []
        for m in qs[:50]: # Límite de 50 para no saturar la lista móvil
            roles_nombres = [r.nombre for r in m.roles.all()]
            
            # Intentamos obtener avatar si existe
            avatar_url = None
            if hasattr(m.usuario, 'avatar') and m.usuario.avatar:
                avatar_url = m.usuario.avatar_thumb_small.url

            data.append({
                "usuario_id": m.usuario.id,
                "membresia_id": m.id,
                "nombre_completo": m.usuario.get_full_name,
                "rut": getattr(m.usuario, 'rut', 'N/A'), # Fallback si no existe el campo
                "email": m.usuario.email,
                "estado": m.get_estado_display(),
                "es_activo": m.estado == Membresia.Estado.ACTIVO,
                "roles": roles_nombres,
                "avatar_url": avatar_url,
                # Campo auxiliar para subtítulos en listas de la app
                "descripcion_corta": f"{', '.join(roles_nombres[:2])}" if roles_nombres else "Sin rol asignado"
            })

        return Response(data, status=status.HTTP_200_OK)




class UsuarioDetalleAPIView(APIView):
    """
    Obtiene el detalle de un usuario específico dentro de la estación.
    Equivale a la vista 'ver_usuario.html'.
    Busca la última membresía válida (Activa o Inactiva).
    
    URL: /api/v1/usuarios/<uuid:pk>/detalle/
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerUsuarios]

    def get(self, request, pk):
        estacion = request.estacion_activa
        
        try:
            # Buscamos la última membresía válida (no finalizada)
            membresia = Membresia.objects.filter(
                usuario_id=pk,
                estacion=estacion,
                estado__in=[Membresia.Estado.ACTIVO, Membresia.Estado.INACTIVO]
            ).select_related('usuario').prefetch_related('roles').latest('created_at')
            
        except Membresia.DoesNotExist:
            return Response(
                {"detail": "El usuario no tiene una membresía activa o inactiva en esta estación."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        usuario = membresia.usuario
        
        # Recopilación de roles
        roles = [r.nombre for r in membresia.roles.all()]

        # Serialización de datos (Mezcla de Usuario y Membresía)
        data = {
            "id": usuario.id,
            "membresia_id": membresia.id,
            "nombre_completo": usuario.get_full_name,
            "rut": getattr(usuario, 'rut', 'N/A'),
            "email": usuario.email,
            "avatar_url": usuario.avatar_thumb_medium.url if hasattr(usuario, 'avatar') and usuario.avatar_thumb_medium else None,
            
            # Datos de Membresía
            "estado": membresia.get_estado_display(),
            "estado_codigo": membresia.estado,
            "roles": roles,
            "roles_display": ", ".join(roles) if roles else "Sin rol asignado",
            "fecha_ingreso": membresia.created_at.strftime('%d/%m/%Y'),
            
            # Datos de Contacto (Defensivo por si los campos varían en tu modelo Usuario)
            "telefono": getattr(usuario, 'telefono', 'No registrado'),
            "direccion": getattr(usuario, 'direccion', 'No registrada'),
            "grupo_sanguineo": getattr(usuario, 'grupo_sanguineo', None), # Útil para ficha médica
        }

        return Response(data, status=status.HTTP_200_OK)




class VoluntarioHojaVidaAPIView(APIView):
    """
    Endpoint que retorna la Hoja de Vida completa de un voluntario.
    
    URL: /api/v1/voluntarios/<uuid:user_uuid>/hoja-vida/
    
    PAYLOAD DE RESPUESTA (Actualizado a models.py):
    {
        "perfil": {
            "nombre_completo": "Juan Pérez",
            "rut": "12.345.678-9",
            "fecha_nacimiento": "1990-01-01",
            "nacionalidad": "Chilena",  # Viene de Nacionalidad.gentilicio
            "estado_civil": "Soltero(a)",
            "profesion": "Ingeniero",
            "genero": "Masculino",
            "grupo_sanguineo": "Ver Ficha Médica" # No existe en modelo Voluntario
        },
        "contacto": {
            "telefono": "912345678", # Prioridad Voluntario > Usuario
            "email": "juan@example.com",
            "direccion": "Av. Principal 123", # Concatenación Calle + Número
            "comuna": "Iquique"
        },
        "institucional": {
            "fecha_ingreso": "2020-05-15", # fecha_primer_ingreso
            "estado_membresia": "ACTIVO",
            "numero_registro": "BV-105",   # numero_registro_bomberil
            "cargo_actual": "Teniente 1°"
        },
        "historial": {
            "cargos": [
                {
                    "cargo": "Ayudante", 
                    "inicio": "2021-01-01", 
                    "fin": "2022-01-01", 
                    "es_actual": false,
                    "ambito": "Compañía"
                }
            ],
            "premios": [
                {
                    "nombre": "5 Años de Servicio", # Tipo o Descripción Personalizada
                    "fecha": "2023-05-15", 
                    "motivo": "Cuerpo de Bomberos" # Usamos 'ambito'
                }
            ],
            "sanciones": [
                {
                    "tipo": "Suspensión", 
                    "fecha": "2021-08-20", 
                    "motivo": "Falta al reglamento..."
                }
            ]
        }
    }
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerHojaVida]

    def get(self, request, user_uuid):
        estacion = request.estacion_activa

        # 1. Validación de Seguridad (Igual a la Web)
        # Solo permite ver voluntarios que tengan membresía en la estación activa
        voluntario_check = get_object_or_404(
            Voluntario, 
            usuario__id=user_uuid, 
            usuario__membresias__estacion=estacion
        )

        # 2. Query Optimizada (Trae todo en 1-2 consultas)
        # Usamos prefetch_related para traer los historiales ordenados
        voluntario = Voluntario.objects.select_related(
            'usuario', 'nacionalidad', 'profesion', 'domicilio_comuna'
        ).prefetch_related(
            Prefetch('historial_cargos', queryset=HistorialCargo.objects.all().select_related('cargo').order_by('-fecha_inicio')),
            Prefetch('historial_reconocimientos', queryset=HistorialReconocimiento.objects.all().order_by('-fecha_evento')),
            Prefetch('historial_sanciones', queryset=HistorialSancion.objects.all().order_by('-fecha_evento')),
            # Filtramos la membresía solo de ESTA estación para saber su estado local
            Prefetch('usuario__membresias', queryset=Membresia.objects.filter(estacion=estacion), to_attr='membresia_local_list')
        ).get(pk=voluntario_check.pk) # pk del voluntario (que puede ser igual al uuid user)

        # 3. Procesamiento de Datos
        usuario = voluntario.usuario
        membresia = voluntario.usuario.membresia_local_list[0] if voluntario.usuario.membresia_local_list else None
        
        # Cargo actual (El que no tiene fecha fin)
        # Buscamos en la lista prefetecheada para no ir a la BD de nuevo
        cargo_actual_obj = next((c for c in voluntario.historial_cargos.all() if c.fecha_fin is None), None)
        cargo_actual_str = cargo_actual_obj.cargo.nombre if cargo_actual_obj else "Voluntario"

        # 4. Construcción del JSON (ADAPTADO A MODELS.PY)
        data = {
            "perfil": {
                "nombre_completo": usuario.get_full_name,
                "rut": getattr(usuario, 'rut', 'N/A'),
                "fecha_nacimiento": voluntario.fecha_nacimiento.strftime('%Y-%m-%d') if voluntario.fecha_nacimiento else None,
                # Usamos gentilicio o pais
                "nacionalidad": voluntario.nacionalidad.gentilicio if voluntario.nacionalidad else "No informada",
                "estado_civil": voluntario.get_estado_civil_display(),
                "profesion": voluntario.profesion.nombre if voluntario.profesion else "No informada",
                "genero": voluntario.get_genero_display(), # Agregado
                # Grupo sanguíneo no está en Voluntario, lo dejamos nulo o lo sacas de FichaMedica
                "grupo_sanguineo": "Ver Ficha Médica" 
            },
            "contacto": {
                "telefono": voluntario.telefono or getattr(usuario, 'telefono', ''), # Prioridad al del voluntario
                "email": usuario.email,
                "direccion": f"{voluntario.domicilio_calle or ''} {voluntario.domicilio_numero or ''}".strip(), #
                "comuna": voluntario.domicilio_comuna.nombre if voluntario.domicilio_comuna else ""
            },
            "institucional": {
                # fecha_primer_ingreso
                "fecha_ingreso": voluntario.fecha_primer_ingreso.strftime('%Y-%m-%d') if voluntario.fecha_primer_ingreso else None,
                "estado_membresia": membresia.get_estado_display() if membresia else "Desconocido",
                # numero_registro_bomberil
                "numero_registro": voluntario.numero_registro_bomberil,
                "cargo_actual": cargo_actual_str
            },
            "historial": {
                "cargos": [
                    {
                        "cargo": hc.cargo.nombre,
                        "inicio": hc.fecha_inicio.strftime('%Y-%m-%d'),
                        "fin": hc.fecha_fin.strftime('%Y-%m-%d') if hc.fecha_fin else None,
                        "es_actual": hc.fecha_fin is None,
                        "ambito": hc.ambito # Agregado útil
                    }
                    for hc in voluntario.historial_cargos.all()
                ],
                "premios": [
                    {
                        # Lógica dual: Tipo o Descripción personalizada
                        "nombre": hr.tipo_reconocimiento.nombre if hr.tipo_reconocimiento else hr.descripcion_personalizada,
                        "fecha": hr.fecha_evento.strftime('%Y-%m-%d'),
                        "motivo": hr.ambito # Usamos ámbito como contexto
                    }
                    for hr in voluntario.historial_reconocimientos.all()
                ],
                "sanciones": [
                    {
                        "tipo": hr.get_tipo_sancion_display(),
                        "fecha": hr.fecha_evento.strftime('%Y-%m-%d'),
                        "motivo": hr.descripcion
                    }
                    for hr in voluntario.historial_sanciones.all()
                ]
            }
        }

        return Response(data, status=status.HTTP_200_OK)




class UsuarioFichaMedicaAPIView(AuditoriaMixin, APIView):
    """
    Endpoint que retorna la Ficha Médica completa de un voluntario.
    
    URL: /api/v1/usuarios/<uuid:user_uuid>/ficha-medica/
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerFichaMedica]

    def get(self, request, user_uuid):
        estacion = request.estacion_activa

        # 1. Query Optimizada y Segura
        # Buscamos la ficha a través del UUID del usuario, validando que pertenezca a la estación.
        ficha = get_object_or_404(
            FichaMedica.objects.select_related(
                'voluntario', 
                'voluntario__usuario', 
                'grupo_sanguineo', 
                'sistema_salud'
            ).prefetch_related(
                # Usamos los related_names definidos en los modelos 'through'
                'alergias__alergia', 
                'enfermedades__enfermedad', 
                'medicamentos__medicamento', 
                'cirugias__cirugia', 
                'voluntario__contactos_emergencia'
            ),
            voluntario__usuario__id=user_uuid,
            voluntario__usuario__membresias__estacion=estacion
        )

        voluntario = ficha.voluntario
        usuario = voluntario.usuario

        # 2. Auditoría (Replicando lógica de la vista web)
        # --- PUENTE AUDITORÍA ---
        if not request.session.get('active_estacion_id'):
            request.session['active_estacion_id'] = estacion.id

        #self.auditar(
        #    verbo="consultó la ficha médica digital de",
        #    objetivo=usuario,
        #    objetivo_repr=usuario.get_full_name,
        #    detalles={'origen': 'APP MÓVIL'}
        #)

        # 3. Cálculo de Edad
        edad = "S/I"
        fecha_nac = voluntario.fecha_nacimiento
        if fecha_nac:
            today = date.today()
            edad = today.year - fecha_nac.year - ((today.month, today.day) < (fecha_nac.month, fecha_nac.day))

        # 4. Construcción del JSON
        data = {
            "paciente": {
                "nombre_completo": usuario.get_full_name,
                "rut": getattr(usuario, 'rut', 'N/A'),
                "edad": edad,
                "grupo_sanguineo": ficha.grupo_sanguineo.nombre if ficha.grupo_sanguineo else "No informado",
                "sistema_salud": ficha.sistema_salud.nombre if ficha.sistema_salud else "No informado"
            },
            "biometria": {
                "peso": f"{ficha.peso_kg} kg" if ficha.peso_kg else None,
                "altura": f"{ficha.altura_mts} mts" if ficha.altura_mts else None,
                "presion_arterial": f"{ficha.presion_arterial_sistolica}/{ficha.presion_arterial_diastolica}" 
                                    if (ficha.presion_arterial_sistolica and ficha.presion_arterial_diastolica) else None
            },
            "alertas": {
                "alergias": [
                    {
                        "nombre": item.alergia.nombre,
                        "observacion": item.observaciones
                    }
                    for item in ficha.alergias.all()
                ],
                "enfermedades": [
                    {
                        "nombre": item.enfermedad.nombre,
                        "observacion": item.observaciones
                    }
                    for item in ficha.enfermedades.all()
                ]
            },
            "tratamiento": {
                "medicamentos": [
                    {
                        "nombre": item.medicamento.nombre_completo, # Usamos la property del modelo Medicamento
                        "dosis": item.dosis_frecuencia
                    }
                    for item in ficha.medicamentos.all()
                ],
                "cirugias": [
                    {
                        "nombre": item.cirugia.nombre,
                        "fecha": item.fecha_cirugia.strftime('%d/%m/%Y') if item.fecha_cirugia else "Fecha desconocida",
                        "observacion": item.observaciones
                    }
                    for item in ficha.cirugias.all()
                ]
            },
            "contactos_emergencia": [
                {
                    "nombre": c.nombre_completo,
                    "relacion": c.parentesco,
                    "telefono": c.telefono
                }
                for c in voluntario.contactos_emergencia.all()
            ],
            "observaciones_generales": ficha.observaciones_generales
        }

        return Response(data, status=status.HTTP_200_OK)




class DocumentoHistoricoListAPIView(APIView):
    """
    Lista los documentos históricos de la estación para la biblioteca digital móvil.
    Incluye filtros por texto y tipo de documento.
    
    URL: /api/v1/documental/documentos/?q=acta&tipo=1
    """
    permission_classes = [IsAuthenticated, IsEstacionActiva, CanVerDocumentos]

    def get(self, request):
        try:
            estacion = request.estacion_activa
            query = request.query_params.get('q', '').strip()
            tipo_id = request.query_params.get('tipo') # ID del TipoDocumento

            # 1. Base Query (Filtrar por estación)
            qs = DocumentoHistorico.objects.filter(estacion=estacion).select_related('tipo_documento')

            # 2. Filtro por Tipo
            if tipo_id and tipo_id.isdigit():
                qs = qs.filter(tipo_documento_id=int(tipo_id))

            # 3. Filtro por Búsqueda (Título, Descripción, Palabras Clave, Ubicación)
            if query:
                qs = qs.filter(
                    Q(titulo__icontains=query) | 
                    Q(descripcion__icontains=query) |
                    Q(palabras_clave__icontains=query) |
                    Q(ubicacion_fisica__icontains=query)
                )

            # 4. Ordenamiento
            qs = qs.order_by('-fecha_documento')

            # 5. Serialización
            data = []
            for doc in qs[:50]: # Limitamos a 50 para no saturar la app (paginación simple)
                
                # Obtener URL del archivo (S3 genera la firma automática aquí si usas django-storages)
                archivo_url = doc.archivo.url if doc.archivo else None
                
                # Obtener URL de la preview (o una imagen por defecto si no existe)
                preview_url = doc.preview_imagen.url if doc.preview_imagen else None

                # Calcular peso del archivo (opcional, útil para UX en móvil)
                peso_mb = 0
                try:
                    if doc.archivo:
                        peso_mb = round(doc.archivo.size / (1024 * 1024), 2)
                except:
                    peso_mb = None

                data.append({
                    "id": doc.id,
                    "titulo": doc.titulo,
                    "fecha": doc.fecha_documento.strftime('%d/%m/%Y'),
                    "anio": doc.fecha_documento.year,
                    "tipo": doc.tipo_documento.nombre,
                    "descripcion": doc.descripcion or "",
                    "ubicacion_fisica": doc.ubicacion_fisica or "Digital",
                    "archivo_url": archivo_url,   # <--- Link de descarga S3
                    "preview_url": preview_url,   # <--- Miniatura para la lista
                    "peso_mb": f"{peso_mb} MB" if peso_mb else "N/A",
                    "es_confidencial": doc.es_confidencial
                })

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": f"Error al cargar documentos: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class DescargarHojaVidaPropiaAPIView(AuditoriaMixin, APIView):
    """
    [Opción Token-URL] Permite descargar PDF enviando el token como parámetro GET.
    URL: /api/v1/.../?token=eyJhbGci...
    """
    # 1. Quitamos IsAuthenticated automático porque el navegador no envía Header
    permission_classes = [] 

    def get(self, request):
        # 2. Autenticación Manual por Query Param
        token = request.query_params.get('token')
        if not token:
            return Response({'error': 'Token no proporcionado.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            # Validamos el JWT manualmente
            auth = JWTAuthentication()
            validated_token = auth.get_validated_token(token)
            user = auth.get_user(validated_token)
            request.user = user # Asignamos el usuario a la request
            
            # Verificar Estación Activa (Manual o vía lógica interna)
            # Como no hay sesión, asumimos la estación activa basada en membresía o parámetro
            # Para simplificar, obtenemos la estación del usuario si es necesario, 
            # o permitimos la descarga si el usuario es válido.
            
        except (InvalidToken, AuthenticationFailed):
             return Response({'error': 'Token inválido o expirado.'}, status=status.HTTP_401_UNAUTHORIZED)

        # 3. Lógica de Negocio (Igual que antes)
        try:
            voluntario = Voluntario.objects.get(usuario=request.user)
            membresia = Membresia.objects.filter(usuario=request.user, estado='ACTIVO').first()
            cargo_actual_obj = HistorialCargo.objects.filter(voluntario=voluntario, fecha_fin__isnull=True).first()

            context = {
                'voluntario': voluntario,
                'membresia': membresia,
                'cargo_actual': cargo_actual_obj,
                'request': request,
                'cargos': HistorialCargo.objects.filter(voluntario=voluntario).order_by('-fecha_inicio'),
                'reconocimientos': HistorialReconocimiento.objects.filter(voluntario=voluntario).order_by('-fecha_evento'),
                'sanciones': HistorialSancion.objects.filter(voluntario=voluntario).order_by('-fecha_evento'),
                'cursos': HistorialCurso.objects.filter(voluntario=voluntario).order_by('-fecha_curso'),
            }

            html_string = render_to_string("gestion_voluntarios/pages/hoja_vida_pdf.html", context)
            result = io.BytesIO()
            pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)

            if not pdf.err:
                self.auditar(
                    verbo="descargó su propia hoja de vida (PDF)",
                    objetivo=request.user,
                    detalles={'origen': 'APP MÓVIL (Browser)'}
                )
                response = HttpResponse(result.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="Hoja_Vida_{request.user.rut}.pdf"'
                return response
            
            return Response({'error': 'Error interno PDF.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Voluntario.DoesNotExist:
            return Response({'error': 'Sin perfil de voluntario.'}, status=status.HTTP_404_NOT_FOUND)


class DescargarFichaMedicaPropiaAPIView(AuditoriaMixin, APIView):
    """
    [Opción Token-URL] Genera y descarga el PDF de la Ficha Médica.
    Reutiliza la plantilla HTML de la web pero la convierte a PDF en el servidor.
    URL: /api/v1/perfil/ficha-medica/descargar/?token=xxxxx
    """
    permission_classes = [] # Seguridad manual para descarga por navegador

    def get(self, request):
        # ------------------------------------------------------------------
        # 1. AUTENTICACIÓN MANUAL (Token en URL)
        # ------------------------------------------------------------------
        token = request.query_params.get('token')
        if not token:
            return Response({'error': 'Token no proporcionado.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            auth = JWTAuthentication()
            validated_token = auth.get_validated_token(token)
            request.user = auth.get_user(validated_token)
        except (InvalidToken, TokenError, AuthenticationFailed):
             return Response({'error': 'Token inválido o expirado.'}, status=status.HTTP_401_UNAUTHORIZED)

        # ------------------------------------------------------------------
        # 2. OBTENCIÓN DE DATOS (Misma lógica que tu vista Web)
        # ------------------------------------------------------------------
        try:
            ficha = FichaMedica.objects.select_related(
                'voluntario', 'voluntario__usuario', 'voluntario__domicilio_comuna', 
                'grupo_sanguineo', 'sistema_salud'
            ).prefetch_related(
                'alergias__alergia', 'enfermedades__enfermedad', 'medicamentos__medicamento', 
                'cirugias__cirugia', 'voluntario__contactos_emergencia'
            ).get(voluntario__usuario=request.user)

            voluntario = ficha.voluntario
            
            # Cálculo de edad
            fecha_nac = voluntario.fecha_nacimiento or voluntario.usuario.birthdate # Fallback defensivo
            edad = "S/I"
            if fecha_nac: 
                today = date.today()
                # Corrección para evitar error si fecha_nac es datetime en lugar de date
                if hasattr(fecha_nac, 'date'):
                    fecha_nac = fecha_nac.date()
                edad = today.year - fecha_nac.year - ((today.month, today.day) < (fecha_nac.month, fecha_nac.day))

            context = {
                'ficha': ficha,
                'voluntario': voluntario,
                'edad': edad,
                'alergias': ficha.alergias.all(),
                'enfermedades': ficha.enfermedades.all(),
                'medicamentos': ficha.medicamentos.all(),
                'cirugias': ficha.cirugias.all(),
                'contactos': voluntario.contactos_emergencia.all(),
                'fecha_reporte': date.today(),
                'request': request # Importante para rutas de imágenes estáticas
            }

            # ------------------------------------------------------------------
            # 3. GENERACIÓN PDF (El paso extra necesario)
            # ------------------------------------------------------------------
            # Renderizamos el HTML a un string en memoria
            html_string = render_to_string("gestion_medica/pages/imprimir_ficha_pdf.html", context)
            
            # Convertimos ese string a PDF bytes
            result = io.BytesIO()
            pdf = pisa.pisaDocument(io.BytesIO(html_string.encode("UTF-8")), result)

            if not pdf.err:
                # Auditoría
                self.auditar(
                    verbo="descargó su propia ficha clínica (PDF)",
                    objetivo=request.user,
                    detalles={'origen': 'APP MÓVIL (Browser)'}
                )
                
                # Devolvemos el PDF binario
                response = HttpResponse(result.getvalue(), content_type='application/pdf')
                filename = f"Ficha_Medica_{request.user.rut}.pdf"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response

            return Response({'error': 'Error interno al generar el PDF.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except FichaMedica.DoesNotExist:
            return Response({'error': 'No tienes ficha médica creada.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Error inesperado: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)