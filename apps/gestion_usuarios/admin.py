from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Rol, Membresia
from django.contrib.auth.models import Group


@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    search_fields = ('first_name', 'last_name', 'email')
    ordering = ("last_name", )
    list_display = ("first_name", "last_name" )

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'rut', 'phone', 'birthdate', 'estacion', 'avatar')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'groups', 'user_permissions')}),
        ('Fechas Importantes', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    # Campos que solo serán de lectura en el panel de admin
    readonly_fields = ('last_login', 'created_at', 'updated_at')
    
    # Campos necesarios para el formulario de creación de usuario
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'first_name', 'last_name', 'estacion', 'is_staff', 'is_superuser'),
        }),
    )



@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estacion')
    list_filter = ('estacion',)
    search_fields = ('nombre',)
    filter_horizontal = ('permisos',) # Facilita la asignación de permisos



@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'estacion', 'estado', 'fecha_inicio', 'fecha_fin')
    list_filter = ('estacion', 'estado', 'roles')
    search_fields = ('usuario__get_full_name', 'estacion__nombre')
    autocomplete_fields = ('usuario', 'estacion', 'roles') # Mejora la selección
    filter_horizontal = ('roles',)



admin.site.unregister(Group)