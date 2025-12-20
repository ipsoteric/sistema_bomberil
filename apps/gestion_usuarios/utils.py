import secrets
import string
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from core.settings import DEFAULT_FROM_EMAIL

from .models import Usuario, Rol, Membresia, RegistroActividad


def generar_contraseña_segura(longitud=12):
    """Genera una contraseña aleatoria y segura."""
    alfabeto = string.ascii_letters + string.digits + string.punctuation
    contraseña = ''.join(secrets.choice(alfabeto) for i in range(longitud))
    return contraseña




def registrar_actividad_tecnica(usuario, objeto_afectado, accion, mensaje):
    """
    Crea una entrada de LogEntry (auditoría) manualmente desde las vistas.
    
    :param usuario: El request.user que realiza la acción.
    :param objeto_afectado: La instancia del modelo (ej. el 'rol' que fue editado).
    :param accion: Constante (ADDITION, CHANGE, o DELETION).
    :param mensaje: El texto que describe la acción.
    """
    try:
        # Asegurarnos de que el objeto_afectado no sea None
        if objeto_afectado is None:
            print("Error de auditoría: Se intentó registrar una acción sobre un objeto 'None'.")
            return

        LogEntry.objects.create(
            user_id=usuario.id,
            content_type_id=ContentType.objects.get_for_model(objeto_afectado).id,
            object_id=objeto_afectado.pk,
            # force_str() es una utilidad de Django para obtener una
            # representación segura del objeto (como "Rol: Administrador")
            object_repr=force_str(objeto_afectado), 
            action_flag=accion,
            change_message=mensaje
        )
    except Exception as e:
        # ¡Importante! El registro de auditoría NUNCA debe
        # interrumpir la acción principal del usuario.
        print(f"Error al registrar auditoría: {e}")




def registrar_actividad(actor, verbo, objetivo, estacion):
    """
    Crea una entrada legible por humanos en el Registro de Actividad.

    :param actor: El request.user que realiza la acción.
    :param verbo: El string de la acción (ej: "modificó a", "eliminó el rol").
    :param objetivo: La instancia del modelo (ej. el 'usuario' editado o el 'rol').
    :param estacion: La 'estacion_activa' donde ocurrió la acción.
    """
    try:
        # --- LÓGICA DE REPRESENTACIÓN (REEMPLAZADA) ---
        # 2. Obtenemos el nombre "limpio" del objeto
        repr_texto = ""
        if isinstance(objetivo, Usuario):
            repr_texto = objetivo.get_full_name
        elif isinstance(objetivo, Rol):
            repr_texto = objetivo.nombre
        elif isinstance(objetivo, Membresia):
             # Ej. si el objetivo es la membresía en sí
            repr_texto = f"la membresía de {objetivo.usuario.get_full_name}"
        elif objetivo:
            # Opción de respaldo para otros modelos
            repr_texto = force_str(objetivo)
        # --- FIN DE LA LÓGICA ---

        # Lógica para el GenericForeignKey
        if objetivo:
            content_type = ContentType.objects.get_for_model(objetivo)
            object_id = objetivo.pk
        else:
            content_type = None
            object_id = None

        RegistroActividad.objects.create(
            actor=actor,
            verbo=verbo,
            objetivo_content_type=content_type,
            objetivo_object_id=object_id,
            objetivo_repr=repr_texto, # <-- 3. Usamos nuestro texto limpio
            estacion=estacion
        )
    except Exception as e:
        # El log nunca debe romper la vista
        print(f"Error al registrar actividad: {e}")




def servicio_crear_usuario_y_notificar(datos_usuario, estacion, request):
    """
    Servicio transaccional que crea el usuario, su membresía y 
    dispara el correo de activación.
    Retorna el usuario creado.
    Lanza excepciones si algo falla para que la vista las capture.
    """
    # Validamos que el email no venga vacío
    if not datos_usuario.get('correo'):
        raise ValueError("El correo electrónico es obligatorio para la activación.")

    with transaction.atomic():
        # 1. Crear Usuario (Sin password)
        nuevo_usuario = Usuario.objects.create_user(
            rut=datos_usuario.get('rut'),
            email=datos_usuario.get('correo'),
            first_name=datos_usuario.get('nombre'),
            last_name=datos_usuario.get('apellido'),
            birthdate=datos_usuario.get('fecha_nacimiento'),
            phone=datos_usuario.get('telefono'),
            avatar=datos_usuario.get('avatar'),
            password=None,
            is_active=True
        )

        # 2. Crear Membresía
        Membresia.objects.create(
            usuario=nuevo_usuario,
            estacion=estacion,
            estado=Membresia.Estado.ACTIVO,
            fecha_inicio=timezone.now().date()
        )

        # 3. Enviar Correo (Lógica extraída)
        _enviar_email_bienvenida(nuevo_usuario, request, estacion)
        
        return nuevo_usuario

def _enviar_email_bienvenida(usuario, request, estacion):
    """
    Método privado para manejar la construcción y envío del email.
    """
    # Generar Tokens
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    
    # Contexto para el template
    contexto = {
        'email': usuario.email,
        'domain': request.get_host(),
        'site_name': 'Bomberil System',
        'uid': uid,
        'user': usuario,
        'token': token,
        'protocol': 'https' if request.is_secure() else 'http',
        'estacion_nombre': estacion.nombre,
    }

    # Renderizar
    asunto = render_to_string('gestion_usuarios/emails/bienvenida_asunto.txt', context=contexto).strip()
    mensaje_texto = render_to_string('gestion_usuarios/emails/bienvenida_usuario.txt', context=contexto)
    mensaje_html = render_to_string('gestion_usuarios/emails/bienvenida_usuario.html', context=contexto)

    # Enviar (Fail loudly)
    send_mail(
        subject=asunto,
        message=mensaje_texto,
        from_email=DEFAULT_FROM_EMAIL, 
        recipient_list=[usuario.email],
        html_message=mensaje_html,
        fail_silently=False 
    )