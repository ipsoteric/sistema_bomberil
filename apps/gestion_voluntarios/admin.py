from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.common.admin_mixins import SysPermissionMixin, ImagenPreviewMixin

from .models import (
    Nacionalidad, Profesion, TipoCargo, Cargo, TipoReconocimiento,
    Voluntario, HistorialPertenencia, HistorialCargo, 
    HistorialReconocimiento, HistorialSancion, HistorialCurso, 
    AnotacionHojaVida
)

# --- INLINES (HISTORIAL INTEGRADO) ---
# Usamos Inlines para que la ficha del Voluntario sea una verdadera "Hoja de Vida"

class HistorialPertenenciaInline(SysPermissionMixin, admin.TabularInline):
    model = HistorialPertenencia
    extra = 0
    autocomplete_fields = ['estacion', 'estacion_registra']
    classes = ['collapse']
    verbose_name = "Registro de Pertenencia"
    verbose_name_plural = "Historial de Pertenencias (Altas/Bajas)"

class HistorialCargoInline(SysPermissionMixin, admin.TabularInline):
    model = HistorialCargo
    extra = 0
    autocomplete_fields = ['cargo', 'estacion_registra']
    classes = ['collapse']
    verbose_name = "Cargo Ocupado"
    verbose_name_plural = "Historial de Cargos y Rangos"

class HistorialReconocimientoInline(SysPermissionMixin, admin.TabularInline):
    model = HistorialReconocimiento
    extra = 0
    autocomplete_fields = ['estacion_registra', 'tipo_reconocimiento']
    classes = ['collapse']
    verbose_name = "Premio / Distinción"
    verbose_name_plural = "Historial de Reconocimientos"

class HistorialSancionInline(SysPermissionMixin, admin.TabularInline):
    model = HistorialSancion
    extra = 0
    autocomplete_fields = ['estacion_registra', 'estacion_evento']
    classes = ['collapse']
    verbose_name = "Sanción Disciplinaria"
    verbose_name_plural = "Historial de Sanciones"
    
    def get_readonly_fields(self, request, obj=None):
        # Por seguridad, una sanción histórica no debería editarse tan fácil
        if obj:
            return ('fecha_evento', 'tipo_sancion')
        return ()

class HistorialCursoInline(SysPermissionMixin, admin.TabularInline):
    model = HistorialCurso
    extra = 0
    autocomplete_fields = ['estacion_registra']
    classes = ['collapse']
    verbose_name = "Curso / Capacitación"
    verbose_name_plural = "Historial Académico"


# --- TABLAS MAESTRAS (CATÁLOGOS) ---

@admin.register(Nacionalidad)
class NacionalidadAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('gentilicio', 'pais', 'iso_nac')
    search_fields = ('gentilicio', 'pais')

@admin.register(Profesion)
class ProfesionAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(TipoCargo)
class TipoCargoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Cargo)
class CargoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'tipo_cargo')
    list_filter = ('tipo_cargo',)
    search_fields = ('nombre',)

@admin.register(TipoReconocimiento)
class TipoReconocimientoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


# --- VOLUNTARIO (PERFIL PRINCIPAL) ---

@admin.register(Voluntario)
class VoluntarioAdmin(SysPermissionMixin, ImagenPreviewMixin, admin.ModelAdmin):
    list_display = (
        'mostrar_avatar',
        'get_nombre_completo',
        'numero_registro_bomberil',
        'profesion',
        'telefono',
        'fecha_primer_ingreso'
    )
    list_filter = (
        'profesion',
        'nacionalidad',
        'genero',
        'estado_civil',
        'domicilio_comuna'
    )
    search_fields = (
        'usuario__first_name', 
        'usuario__last_name', 
        'usuario__rut', 
        'numero_registro_bomberil'
    )
    autocomplete_fields = ['usuario', 'nacionalidad', 'profesion', 'domicilio_comuna']
    
    # Aquí integramos toda la hoja de vida
    inlines = [
        HistorialPertenenciaInline,
        HistorialCargoInline,
        HistorialCursoInline,
        HistorialReconocimientoInline,
        HistorialSancionInline
    ]
    
    fieldsets = (
        ('Identidad', {
            'fields': (
                'usuario', 
                ('numero_registro_bomberil', 'fecha_primer_ingreso'),
                ('imagen', 'imagen_thumb_medium')
            )
        }),
        ('Información Civil', {
            'fields': (
                ('nacionalidad', 'profesion'),
                ('fecha_nacimiento', 'lugar_nacimiento'),
                ('genero', 'estado_civil')
            )
        }),
        ('Contacto y Domicilio', {
            'fields': (
                ('telefono', 'domicilio_comuna'),
                ('domicilio_calle', 'domicilio_numero')
            )
        }),
    )
    
    readonly_fields = ('imagen_thumb_medium', 'imagen_thumb_small', 'fecha_creacion')

    def get_nombre_completo(self, obj):
        return obj.usuario.get_full_name
    get_nombre_completo.short_description = "Nombre Completo"
    get_nombre_completo.admin_order_field = 'usuario__last_name'

    def mostrar_avatar(self, obj):
        if obj.imagen_thumb_small:
            return format_html('<img src="{}" width="40" height="40" style="border-radius:50%; object-fit:cover;" />', obj.imagen_thumb_small.url)
        return "-"
    mostrar_avatar.short_description = "Foto"


# --- ADMINS INDIVIDUALES PARA HISTORIALES (OPCIONAL) ---
# Aunque están como inlines, a veces es útil tener una vista global de todos los premios o sanciones del cuerpo

@admin.register(HistorialCargo)
class HistorialCargoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('voluntario', 'cargo', 'fecha_inicio', 'fecha_fin', 'estacion_registra')
    list_filter = ('cargo', 'fecha_inicio', 'estacion_registra')
    search_fields = ('voluntario__usuario__last_name', 'cargo__nombre')
    autocomplete_fields = ['voluntario', 'cargo', 'estacion_registra']

@admin.register(HistorialSancion)
class HistorialSancionAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('voluntario', 'tipo_sancion', 'fecha_evento', 'estacion_evento')
    list_filter = ('tipo_sancion', 'fecha_evento')
    search_fields = ('voluntario__usuario__last_name',)
    autocomplete_fields = ['voluntario', 'estacion_registra', 'estacion_evento']