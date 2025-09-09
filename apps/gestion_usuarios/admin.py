from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from .models import Usuario, Rol, Membresia
from .forms import CustomUserCreationForm, CustomUserChangeForm



@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    fieldsets = UserAdmin.fieldsets

    # ---- CONFIGURACIÓN PARA LA VISTA DE LISTA ----
    list_display = ("email", "first_name", "last_name", "is_staff" )
    search_fields = ('first_name', 'last_name', 'email', 'rut')
    ordering = ("last_name", )
    readonly_fields = ('last_login', 'created_at', 'updated_at')

    # ---- CONFIGURACIÓN PARA LA VISTA DE CREACIÓN (ADD FORM) ----
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )

    # ---- CONFIGURACIÓN PARA LA VISTA DE EDICIÓN (CHANGE FORM) ----
    fieldsets = (
        (None, {'fields': ('email',)}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'rut', 'phone', 'birthdate', 'avatar')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas Importantes', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_view_usuario')

    def has_add_permission(self, request):
        return request.user.has_perm('gestion_usuarios.sys_add_usuario')

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_change_usuario')

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_delete_usuario')



@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estacion')
    list_filter = ('estacion',)
    search_fields = ('nombre',)
    filter_horizontal = ('permisos',) # Facilita la asignación de permisos

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_view_rol')

    def has_add_permission(self, request):
        return request.user.has_perm('gestion_usuarios.sys_add_rol')

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_change_rol')

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_delete_rol')



@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'estacion', 'estado', 'fecha_inicio', 'fecha_fin')
    list_filter = ('estacion', 'estado', 'roles')
    search_fields = ('usuario__get_full_name', 'estacion__nombre')
    autocomplete_fields = ('usuario', 'estacion', 'roles') # Mejora la selección
    filter_horizontal = ('roles',)

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_view_membresia')

    def has_add_permission(self, request):
        return request.user.has_perm('gestion_usuarios.sys_add_membresia')

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_change_membresia')

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm('gestion_usuarios.sys_delete_membresia')



admin.site.unregister(Group)