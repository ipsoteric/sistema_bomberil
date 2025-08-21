from django.shortcuts import redirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from PIL import Image

from apps.gestion_usuarios.models import Usuario, Membresia



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



def editar_avatar_usuario(request, id):
    # Solo aceptamos peticiones POST para esta vista de API
    if request.method == 'POST':
        usuario = get_object_or_404(Usuario, pk=id)
        nuevo_avatar = request.FILES.get('nuevo_avatar')

        if nuevo_avatar:
            # Intenta abrir la imagen para validarla
            try:
                img = Image.open(nuevo_avatar)
                img.verify()  # Verifica que no sea un archivo corrupto
            except (IOError, SyntaxError) as e:
                return JsonResponse({'success': False, 'error': 'El archivo de imagen no es válido.'}, status=400)
            
            usuario.avatar = nuevo_avatar
            usuario.save()
            return JsonResponse({'success': True, 'new_avatar_url': usuario.avatar.url})

    return JsonResponse({'success': False, 'error': 'Petición inválida'})