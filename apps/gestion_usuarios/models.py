from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Group, Permission
from PIL import Image
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from .manager import CustomUserManager
from .funciones import generar_ruta_subida_avatar, recortar_y_redimensionar_avatar, generar_avatar_thumbnail
from apps.gestion_inventario.models import Estacion


class Usuario(AbstractBaseUser, PermissionsMixin):
    id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=100, unique=True, verbose_name="correo electrónico")
    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, verbose_name="Apellidos")
    rut = models.CharField(max_length=15, unique=True, blank=True, null=True)
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

    USERNAME_FIELD="email"
    REQUIRED_FIELDS= ["first_name", "last_name"]

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
        ]


    def __str__(self):
        return self.email
    

    @property
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'    


    def save(self, *args, **kwargs):
        # Guardamos la referencia al avatar actual si existe
        old_avatar = None
        if self.pk and self.avatar:
            old_avatar = Usuario.objects.get(pk=self.pk).avatar

        # Se guarda el objeto por primera vez para obtener su ID
        super().save(*args, **kwargs)

        # Si se subió un nuevo avatar
        if self.avatar and old_avatar != self.avatar:
            # Procesamos el archivo en memoria y lo guardamos con la ruta final en S3
            processed_file = recortar_y_redimensionar_avatar(self.avatar)
            final_avatar_path = f"usuarios/avatar/user_{self.id}/avatar.jpg"
            self.avatar.save(final_avatar_path, processed_file, save=False)

            # Reabrimos la imagen ya procesada desde S3 para generar los thumbnails
            with Image.open(self.avatar) as processed_image:
                thumb_40x40 = generar_avatar_thumbnail(processed_image, (40, 40), "_thumb_40")
                thumb_100x100 = generar_avatar_thumbnail(processed_image, (100, 100), "_thumb_100")
                
                thumb_40x40_path = f"usuarios/avatar/user_{self.id}/avatar_thumb_40.jpg"
                thumb_100x100_path = f"usuarios/avatar/user_{self.id}/avatar_thumb_100.jpg"
                
                self.avatar_thumb_small.save(thumb_40x40_path, thumb_40x40, save=False)
                self.avatar_thumb_medium.save(thumb_100x100_path, thumb_100x100, save=False)
            
            # Guardamos el modelo una vez más para actualizar las rutas de todos los archivos
            super().save(update_fields=['avatar', 'avatar_thumb_small', 'avatar_thumb_medium'])

            # Eliminar el archivo temporal y el viejo avatar si existe
            if old_avatar:
                old_avatar.delete(save=False)
            if 'temp' in self.avatar.name: # Si el archivo actual es el temporal, lo eliminamos
                self.avatar.delete(save=False)
    


#    def save(self, *args, **kwargs):
#        # Guardamos el objeto por primera vez para obtener el ID
#        super().save(*args, **kwargs)
#
#        # Solo si el avatar ha sido subido y está en la ruta temporal
#        if self.avatar and self.avatar.name.startswith("usuarios/avatar/temp_avatars/"):
#            # 1. Procesa y sobrescribe la imagen temporal
#            processed_file = recortar_y_redimensionar_avatar(self.avatar)
#            self.avatar.save(os.path.basename(self.avatar.name), processed_file, save=False)
#
#            # 2. Mueve el archivo a la ruta final
#            old_file_path = os.path.join(settings.MEDIA_ROOT, self.avatar.name)
#            new_path_dir = os.path.join(settings.MEDIA_ROOT, f"usuarios/avatar/user_{self.id}")
#            os.makedirs(new_path_dir, exist_ok=True)
#            new_file_path = os.path.join(new_path_dir, "avatar.jpg")
#            move(old_file_path, new_file_path)
#
#            # 3. Genera los thumbnails y los guarda en la ruta final
#            with Image.open(new_file_path) as processed_image:
#                thumb_40x40 = generar_avatar_thumbnail(processed_image, (40, 40), "_thumb_40")
#                thumb_100x100 = generar_avatar_thumbnail(processed_image, (100, 100), "_thumb_100")
#                
#                thumb_40x40_path = f"usuarios/avatar/user_{self.id}/avatar_thumb_40.jpg"
#                thumb_100x100_path = f"usuarios/avatar/user_{self.id}/avatar_thumb_100.jpg"
#                
#                self.avatar_thumb_small.save(thumb_40x40_path, thumb_40x40, save=False)
#                self.avatar_thumb_medium.save(thumb_100x100_path, thumb_100x100, save=False)
#
#            # 4. Actualiza los campos con las nuevas rutas y guarda todo
#            self.avatar.name = f"usuarios/avatar/user_{self.id}/avatar.jpg"
#            super().save(update_fields=['avatar', 'avatar_thumb_small', 'avatar_thumb_medium'])






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
            ("manage_custom_roles", "Puede gestionar roles personalizados"),
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
            ("assign_user_roles", "Puede asignar y cambiar roles a un usuario"),
            ("deactivate_user", "Puede desactivar o reactivar la cuenta de un usuario"),
            ("end_user_membership", "Puede finalizar la membresía de un usuario"),
        ]

    
    def __str__(self):
        return f'{self.usuario.get_full_name} en {self.estacion.nombre} ({self.estado})'