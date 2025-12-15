from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

# Importamos tus mixins comunes
from apps.common.admin_mixins import SysPermissionMixin, ImagenPreviewMixin

from .models import Usuario, Rol, Membresia, RegistroActividad
from .forms import CustomUserCreationForm, CustomUserChangeForm

# --- USUARIO ---

@admin.register(Usuario)
class UsuarioAdmin(SysPermissionMixin, ImagenPreviewMixin, BaseUserAdmin):
    """
    Administrador de usuarios personalizado.
    Combina la lógica de BaseUserAdmin (seguridad de passwords) con:
    1. SysPermissionMixin: Manejo automático de permisos 'sys_'.
    2. ImagenPreviewMixin: Visualización de avatares.
    3. CustomForms: Validaciones específicas para RUT y campos obligatorios.
    """
    # Vinculamos los formularios personalizados
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    # Configuración de la lista
    list_display = ('rut', 'email', 'get_full_name', 'is_active', 'is_staff', 'mostrar_avatar')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'is_verified')
    search_fields = ('rut', 'email', 'first_name', 'last_name')
    ordering = ('rut',)
    
    # Campos de solo lectura
    readonly_fields = ('last_login', 'created_at', 'updated_at', 'avatar_thumb_small')

    # ---- VISTA DE CREACIÓN (ADD FORM) ----
    # Es crucial incluir 'rut' aquí si es tu USERNAME_FIELD
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('rut', 'email', 'first_name', 'last_name', 'birthdate'),
        }),
        ('Permisos Iniciales', {
             'classes': ('collapse',),
             'fields': ('is_staff', 'is_superuser', 'is_active'),
        }),
    )

    # ---- VISTA DE EDICIÓN (CHANGE FORM) ----
    fieldsets = (
        (None, {
            'fields': ('rut', 'password')
        }),
        (_('Información Personal'), {
            'fields': (
                ('first_name', 'last_name'),
                ('email', 'phone'),
                'birthdate',
                'avatar',
                'is_verified'
            )
        }),
        (_('Permisos'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        (_('Fechas Importantes'), {
            'fields': ('last_login', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def mostrar_avatar(self, obj):
        if obj.avatar_thumb_small:
            return format_html('<img src="{}" width="35" height="35" style="border-radius:50%; object-fit:cover;" />', obj.avatar_thumb_small.url)
        elif obj.avatar:
            return format_html('<img src="{}" width="35" height="35" style="border-radius:50%; object-fit:cover;" />', obj.avatar.url)
        return "-"
    mostrar_avatar.short_description = "Avatar"


# --- ROL ---

@admin.register(Rol)
class RolAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'get_ambito', 'descripcion', 'cantidad_permisos')
    list_filter = ('estacion',)
    search_fields = ('nombre', 'descripcion')
    filter_horizontal = ('permisos',) # Widget de doble caja para permisos
    autocomplete_fields = ['estacion']

    def get_ambito(self, obj):
        if obj.estacion:
            return f"Estación: {obj.estacion.nombre}"
        return format_html('<span style="color:green; font-weight:bold;">Universal</span>')
    get_ambito.short_description = "Ámbito"
    get_ambito.admin_order_field = 'estacion'

    def cantidad_permisos(self, obj):
        return obj.permisos.count()
    cantidad_permisos.short_description = "Nº Permisos"


# --- MEMBRESÍA ---

@admin.register(Membresia)
class MembresiaAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('usuario', 'estacion', 'estado_coloreado', 'fecha_inicio', 'fecha_fin')
    list_filter = ('estado', 'estacion', 'fecha_inicio')
    search_fields = ('usuario__rut', 'usuario__first_name', 'usuario__last_name', 'estacion__nombre')
    autocomplete_fields = ['usuario', 'estacion']
    filter_horizontal = ('roles',) # Widget doble caja para roles
    
    fieldsets = (
        ('Vinculación', {
            'fields': ('usuario', 'estacion')
        }),
        ('Estado y Roles', {
            'fields': ('estado', 'roles')
        }),
        ('Vigencia', {
            'fields': ('fecha_inicio', 'fecha_fin')
        }),
    )

    def estado_coloreado(self, obj):
        colors = {
            'ACTIVO': 'green',
            'INACTIVO': 'gray',
            'FINALIZADO': 'red',
        }
        color = colors.get(obj.estado, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_coloreado.short_description = "Estado"
    estado_coloreado.admin_order_field = 'estado'


# --- REGISTRO DE ACTIVIDAD (AUDITORÍA) ---

@admin.register(RegistroActividad)
class RegistroActividadAdmin(SysPermissionMixin, admin.ModelAdmin):
    """
    Admin de solo lectura para auditar las acciones del sistema.
    """
    list_display = ('fecha', 'actor', 'verbo', 'objetivo_repr', 'estacion')
    list_filter = ('fecha', 'estacion', 'verbo')
    search_fields = ('actor__rut', 'actor__first_name', 'objetivo_repr', 'detalles')
    date_hierarchy = 'fecha'
    
    # Todo readonly para preservar la integridad del log
    readonly_fields = [field.name for field in RegistroActividad._meta.fields]

    # Forzamos permisos restrictivos extras al mixin para que nadie edite logs
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


# Opcional: Desregistrar el modelo Group si no lo usas directamente
# ya que usas tus propios Roles
admin.site.unregister(Group)