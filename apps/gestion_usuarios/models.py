from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Group, Permission
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .manager import CustomUserManager
from .funciones import generar_ruta_subida_avatar, recortar_y_redimensionar_avatar, generar_avatar_thumbnail
from apps.gestion_inventario.models import Estacion


class Usuario(AbstractBaseUser, PermissionsMixin):
    id = models.AutoField(primary_key=True)
    rut = models.CharField(max_length=15, unique=True, blank=True, null=True)
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name="correo electrónico")
    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, verbose_name="Apellidos")
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    birthdate = models.DateField(null=True, blank=True, verbose_name="Fecha Nacimiento")
    phone = models.CharField(max_length=9, null=True, blank=True, verbose_name="Teléfono")
    avatar = models.ImageField(upload_to=generar_ruta_subida_avatar, null=True, blank=True)
    avatar_thumb_small = models.ImageField(null=True, blank=True)
    avatar_thumb_medium = models.ImageField(null=True, blank=True)
    
    # Campos automáticos de fecha
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    user_permissions = models.ManyToManyField(Permission, related_name="custom_user_permissions", blank=True)

    USERNAME_FIELD="rut"
    REQUIRED_FIELDS= ["first_name", "last_name", "email"]

    objects= CustomUserManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

        default_permissions = []

        permissions = [
            # Permisos de Sistema
            ("sys_view_usuario", "System: Puede ver usuarios"),
            ("sys_add_usuario", "System: Puede agregar usuarios"),
            ("sys_change_usuario", "System: Puede cambiar usuarios"),
            ("sys_delete_usuario", "System: Puede eliminar usuarios"),

            # Permisos de Negocio
            ("create_user", "Puede crear y registrar nuevos usuarios"),
            ("change_user_personal_info", "Puede modificar la información personal de un usuario"),
            ("force_password_reset", "Puede restablecer la contraseña de un usuario")
        ]


    def __str__(self):
        return self.email
    

    @property
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'    








class Rol(models.Model):
    """
    Define un rol dentro del sistema. Puede ser universal (compartido por todas
    las compañías) o específico de una sola compañía.
    """
    nombre = models.CharField(_("nombre"), max_length=150)
    descripcion= models.TextField(verbose_name="(Descripción)", null=True, blank=True)
    
    # La clave del modelo híbrido. Si es Null, el rol es universal.
    estacion = models.ForeignKey(
        Estacion, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text=_("Dejar en blanco para crear un rol universal.")
    )

    # Vinculamos directamente a los permisos de Django
    permisos = models.ManyToManyField(
        Permission,
        verbose_name=_("permisos"),
        blank=True,
    )

    class Meta:
        verbose_name = "rol"
        verbose_name_plural = "roles"
        ordering = ['nombre']
        constraints = [
            # Regla 1: El par (nombre, estacion) debe ser único si la estación no es nula.
            models.UniqueConstraint(
                fields=['nombre', 'estacion'], 
                name='rol_unico_por_estacion'
            ),
            # Regla 2: El 'nombre' debe ser único SI la estación ES nula.
            models.UniqueConstraint(
                fields=['nombre'], 
                condition=Q(estacion__isnull=True), 
                name='rol_global_unico'
            )
        ]

        default_permissions = []

        permissions = [
            # Permisos de Sistema
            ("sys_view_rol", "System: Puede ver los roles "),
            ("sys_add_rol", "System: Puede agregar roles"),
            ("sys_change_rol", "System: Puede cambiar usuarios"),
            ("sys_delete_rol", "System: Puede eliminar usuarios"),

            # Permisos de Negocio
            ("view_roles", "Puede ver los roles y sus permisos"),
            ("manage_custom_roles", "Puede crear, editar, eliminar y asignar permisos a los roles"),
        ]


    def __str__(self):
        if self.estacion:
            return f'{self.nombre} ({self.estacion.nombre})'
        return f'{self.nombre} (Universal)'






class Membresia(models.Model):
    """
    Este modelo es el corazón del sistema.
    Vincula un Usuario a una Compañía y define sus roles dentro de esa compañía.
    """

    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'
        FINALIZADO = 'FINALIZADO', 'Finalizado'

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='membresias')
    estacion = models.ForeignKey(Estacion, on_delete=models.CASCADE, related_name='miembros')
    roles = models.ManyToManyField(Rol, related_name='asignaciones') 
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Membresía")
        verbose_name_plural = _("Membresías")
        # Restricción para evitar múltiples membresías activas del mismo usuario en la misma compañía
        constraints = [
            models.UniqueConstraint(
                fields=['usuario'], 
                condition=Q(estado='ACTIVO'), 
                name='membresia_activa_unica_por_usuario'
            )
        ]

        default_permissions = []

        permissions = [
            # Permisos de Sistema
            ("sys_view_membresia", "System: Puede ver membresías"),
            ("sys_add_membresia", "System: Puede agregar membresías"),
            ("sys_change_membresia", "System: Puede cambiar membresías"),
            ("sys_delete_membresia", "System: Puede eliminar membresías"),

            # Permisos de Negocio
            ("view_company_users", "Puede ver a los usuarios de la compañía"),
            ("view_user_permissions", "Puede ver los permisos de los usuarios"),
            ("assign_user_roles", "Puede asignar y cambiar roles a un usuario"),
            ("deactivate_user", "Puede desactivar o reactivar la cuenta de un usuario"),
            ("end_user_membership", "Puede finalizar la membresía de un usuario"),
        ]

    
    def __str__(self):
        return f'{self.usuario.get_full_name} en {self.estacion.nombre} ({self.estado})'