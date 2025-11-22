from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Permission
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from .manager import CustomUserManager
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
    avatar = models.ImageField(upload_to="usuarios/avatar/main/", null=True, blank=True)
    avatar_thumb_small = models.ImageField(upload_to="usuarios/avatar/small/", null=True, blank=True)
    avatar_thumb_medium = models.ImageField(upload_to="usuarios/avatar/medium/", null=True, blank=True)
    
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
        ]


    def __str__(self):
        return self.get_full_name
    

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


            # === MÓDULO: GESTIÓN DE USUARIOS Y ROLES ===
            ("acceso_gestion_usuarios", "Puede acceder al módulo de Gestión de Usuarios"),
            ("accion_gestion_usuarios_crear_usuario", "Puede crear y registrar nuevos usuarios"),
            ("accion_gestion_usuarios_modificar_info", "Puede modificar la información personal de un usuario"),
            ("accion_gestion_usuarios_restablecer_pass", "Puede restablecer la contraseña de un usuario"),
            ("accion_gestion_usuarios_ver_roles", "Puede ver los roles y sus permisos"),
            ("accion_gestion_usuarios_gestionar_roles", "Puede crear, editar, eliminar y asignar permisos a los roles"),
            ("accion_gestion_usuarios_ver_compania", "Puede ver a los usuarios de la compañía"),
            ("accion_gestion_usuarios_ver_permisos", "Puede ver los permisos de los usuarios"),
            ("accion_gestion_usuarios_asignar_roles", "Puede asignar y cambiar roles a un usuario"),
            ("accion_gestion_usuarios_desactivar_cuenta", "Puede desactivar o reactivar la cuenta de un usuario"),
            ("accion_gestion_usuarios_finalizar_membresia", "Puede finalizar la membresía de un usuario"),
            ("accion_gestion_usuarios_ver_auditoria", "Puede ver el registro de actividad (auditoría) y el historial de membresías"),
            ("accion_gestion_usuarios_forzar_logout", "Puede forzar el cierre de sesión de los usuarios"),
            ("accion_gestion_usuarios_generar_reportes", "Puede generar reportes"),


            # === GESTIÓN DE INVENTARIO: CONFIGURACIÓN ===
            ("acceso_gestion_inventario", "Puede acceder al módulo de Gestión de Inventario"),
            
            # --- Permisos de Ubicaciones ---
            ("accion_gestion_inventario_ver_ubicaciones", "Puede ver la lista de Áreas, Vehículos y Compartimentos"),
            ("accion_gestion_inventario_gestionar_ubicaciones", "Puede crear, editar y eliminar Áreas, Vehículos y Compartimentos"),
            
            # --- Permisos de Proveedores ---
            ("accion_gestion_inventario_ver_proveedores", "Puede ver la lista de Proveedores y sus contactos"),
            ("accion_gestion_inventario_gestionar_proveedores", "Puede crear, editar y eliminar Proveedores y sus contactos"),
            
            # --- Permisos de Catálogo ---
            ("accion_gestion_inventario_ver_catalogos", "Puede ver el Catálogo Local de la estación y el Catálogo Global"),
            ("accion_gestion_inventario_gestionar_catalogo_local", "Puede añadir y administrar el Catálogo Local de productos"),
            ("accion_gestion_inventario_crear_producto_global", "Puede crear nuevos productos en el Catálogo Global"),

            # === GESTIÓN DE INVENTARIO: OPERACIONES DE STOCK ===
            ("accion_gestion_inventario_ver_stock", "Puede consultar el stock y ver el detalle de las existencias"),
            ("accion_gestion_inventario_recepcionar_stock", "Puede recepcionar y registrar nuevas existencias (stock)"),
            ("accion_gestion_inventario_gestionar_stock_interno", "Puede consumir, ajustar y transferir existencias internamente"),
            ("accion_gestion_inventario_gestionar_bajas_stock", "Puede dar de baja, anular o reportar extravío de existencias"),

            # === GESTIÓN DE INVENTARIO: FLUJOS EXTERNOS ===
            ("accion_gestion_inventario_ver_prestamos", "Puede ver el historial de préstamos y sus detalles"),
            ("accion_gestion_inventario_gestionar_prestamos", "Puede crear préstamos, gestionar devoluciones y administrar destinatarios"),
            ("accion_gestion_inventario_trasladar_stock_externo", "Puede trasladar existencias (stock) a otra estación"),

            # === GESTIÓN DE INVENTARIO: REPORTES Y UTILIDADES ===
            ("accion_gestion_inventario_ver_historial_movimientos", "Puede ver el historial de movimientos del inventario"),
            ("accion_gestion_inventario_imprimir_etiquetas_qr", "Puede generar e imprimir etiquetas QR"),
            ("accion_gestion_inventario_realizar_conteo_fisico", "Puede iniciar y gestionar un Conteo Físico (Inventario)"),
            ("accion_gestion_inventario_generar_reportes", "Puede generar reportes"),

            # === MÓDULO: GESTIÓN DE MANTENIMIENTO DE HERRAMIENTAS ===
            ("acceso_gestion_mantenimiento", "Puede acceder al módulo de Mantenimiento"),
            ("accion_gestion_mantenimiento_ver_ordenes", "Puede ver los planes de mantenimiento y las órdenes de trabajo"),
            ("accion_gestion_mantenimiento_gestionar_planes", "Puede gestionar los planes de mantenimiento"),
            ("accion_gestion_mantenimiento_gestionar_ordenes", "Puede gestionar las órdenes de trabajo y registrar tareas"),
            ("accion_gestion_mantenimiento_generar_reportes", "Puede generar reportes"),

            # === MÓDULO: GESTIÓN DE VOLUNTARIOS ===
            ("acceso_gestion_voluntarios", "Puede acceder al módulo de Voluntarios"),
            ("accion_gestion_voluntarios_ver_voluntarios", "Puede ver a los voluntarios de la compañía"),
            ("accion_gestion_voluntarios_gestionar_voluntarios", "Puede gestionar a los voluntarios de la compañía"),
            ("accion_gestion_voluntarios_generar_hoja_vida", "Puede generar la hoja de vida de un voluntario en PDF"),
            ("accion_gestion_voluntarios_gestionar_datos_normalizacion", "Puede gestionar los cargos y profesiones de la compañía"),
            ("accion_gestion_voluntarios_generar_reportes", "Puede generar reportes"),

            # === MÓDULO: GESTIÓN DE FICHAS MÉDICAS ===
            ("acceso_gestion_medica", "Puede acceder al módulo de Fichas médicas"),
            ("accion_gestion_medica_ver_fichas_medicas", "Puede ver las fichas médicas de los voluntarios de la compañía"),
            ("accion_gestion_medica_gestionar_fichas_medicas", "Puede gestionar las fichas médicas de los voluntarios de la compañía"),
            ("accion_gestion_medica_gestionar_datos_normalizacion", "Puede gestionar enfermedades, medicamentos, cirugías, etc."),
            ("accion_gestion_medica_generar_reportes", "Puede generar reportes"),

            # === MÓDULO: GESTIÓN DE DOCUMENTAL ===
            ("acceso_gestion_documental", "Puede acceder al módulo de Fichas médicas"),
            ("accion_gestion_documental_ver_documentos", "Puede ver los documentos de la compañía"),
            ("accion_gestion_documental_gestionar_documentos", "Puede gestionar los documentos de la compañía"),
            ("accion_gestion_documental_generar_reportes", "Puede generar reportes"),
        ]

    
    def __str__(self):
        return f'{self.usuario.get_full_name} en {self.estacion.nombre} ({self.estado})'




class RegistroActividad(models.Model):
    """
    Registra una acción legible por humanos para el feed de actividad
    de la estación (Ej: "Admin X" "modificó a" "Usuario Y").
    """
    id = models.BigAutoField(primary_key=True)
    
    # El "QUIÉN" (El usuario que hizo la acción)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Si se borra el admin, el log persiste
        null=True,
        related_name='acciones'
    )
    
    # El "QUÉ HIZO" (La acción en texto)
    verbo = models.CharField(max_length=255)
    
    # El "A QUIÉN/QUÉ" (El objeto que recibió la acción)
    # Usamos GenericForeignKey para que pueda ser un Usuario, un Rol, etc.
    objetivo_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    objetivo_object_id = models.PositiveIntegerField(null=True, blank=True)
    objetivo_generico = GenericForeignKey(
        'objetivo_content_type', 
        'objetivo_object_id'
    )
    
    # Un texto de respaldo por si el 'objetivo' se elimina
    objetivo_repr = models.CharField(max_length=200, blank=True, null=True)

    # El "DÓNDE" (Crucial para filtrar por estación)
    estacion = models.ForeignKey(
        Estacion, 
        on_delete=models.SET_NULL, # El log debe persistir si se borra la estación
        null=True, 
        blank=True
    )
    
    # El "CUÁNDO"
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Registro de Actividad"
        verbose_name_plural = "Registros de Actividad"
        ordering = ['-fecha']

        default_permissions = []

        permissions = [
            # Permisos de Sistema
            ("sys_view_registro_actividad", "System: Puede ver registros de actividad"),
            ("sys_add_registro_actividad", "System: Puede agregar registros de actividad"),
            ("sys_change_registro_actividad", "System: Puede cambiar registros de actividad"),
            ("sys_delete_registro_actividad", "System: Puede eliminar registros de actividad"),
        ]