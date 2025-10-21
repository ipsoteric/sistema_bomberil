import traceback
from django.shortcuts import redirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from PIL import Image
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser

from apps.gestion_usuarios.models import Usuario, Membresia
from apps.common.permissions import CanUpdateUserProfile
from apps.gestion_usuarios.funciones import generar_avatar_thumbnail, recortar_y_redimensionar_avatar
from apps.gestion_inventario.models import Comuna
from .serializers import ComunaSerializer



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
            # Guardar referencias a los archivos antiguos para su posterior eliminación
            old_avatar = usuario.avatar
            old_thumb_small = usuario.avatar_thumb_small
            old_thumb_medium = usuario.avatar_thumb_medium

            # Procesar la nueva imagen y sus thumbnails en memoria
            with Image.open(nuevo_avatar_file) as img:
                processed_avatar_content = recortar_y_redimensionar_avatar(nuevo_avatar_file)
                thumb_40_content = generar_avatar_thumbnail(img.copy(), (40, 40), "_thumb_40")
                thumb_100_content = generar_avatar_thumbnail(img.copy(), (100, 100), "_thumb_100")

            # 1. BORRAR PRIMERO: Eliminar los archivos antiguos del almacenamiento (S3)
            if old_avatar and old_avatar.name:
                old_avatar.delete(save=False)
            if old_thumb_small and old_thumb_small.name:
                old_thumb_small.delete(save=False)
            if old_thumb_medium and old_thumb_medium.name:
                old_thumb_medium.delete(save=False)

            # 2. GUARDAR DESPUÉS: Asignar y guardar los nuevos archivos
            usuario.avatar = processed_avatar_content
            usuario.avatar_thumb_small = thumb_40_content
            usuario.avatar_thumb_medium = thumb_100_content
            usuario.save()

            # Refrescar la instancia para asegurar que los campos de archivo están actualizados
            usuario.refresh_from_db()

            # Devolver la respuesta exitosa con la nueva URL
            return Response(
                {'success': True, 'new_avatar_url': usuario.avatar.url},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            # Capturar cualquier error inesperado durante el proceso
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