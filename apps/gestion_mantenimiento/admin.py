from django.contrib import admin
from django.utils.html import format_html
from apps.common.admin_mixins import SysPermissionMixin
from .models import (
    PlanMantenimiento, PlanActivoConfig, 
    OrdenMantenimiento, RegistroMantenimiento
)

# --- INLINES ---

class PlanActivoConfigInline(SysPermissionMixin, admin.TabularInline):
    """
    Permite agregar activos a un plan y ver su última mantención
    directamente desde la pantalla del Plan de Mantenimiento.
    """
    model = PlanActivoConfig
    extra = 1
    autocomplete_fields = ['activo']
    fields = ('activo', 'fecha_ultima_mantencion', 'horas_uso_en_ultima_mantencion')
    readonly_fields = ('fecha_ultima_mantencion', 'horas_uso_en_ultima_mantencion')
    
    def has_change_permission(self, request, obj=None):
        # Permitimos agregar/borrar, pero editar la fecha histórica aquí podría ser peligroso
        # Se recomienda que esto se actualice vía órdenes de trabajo.
        return super().has_change_permission(request, obj)


class RegistroMantenimientoInline(SysPermissionMixin, admin.StackedInline):
    """
    Permite ver o agregar los registros de ejecución (logs)
    dentro de la misma Orden de Mantenimiento.
    """
    model = RegistroMantenimiento
    extra = 0
    autocomplete_fields = ['activo', 'usuario_ejecutor']
    classes = ['collapse']


# --- ADMINS PRINCIPALES ---

@admin.register(PlanMantenimiento)
class PlanMantenimientoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = (
        'nombre', 
        'tipo_trigger', 
        'mostrar_frecuencia', 
        'estacion', 
        'activo_en_sistema',
        'cantidad_activos'
    )
    list_filter = (
        'tipo_trigger', 
        'frecuencia', 
        'estacion', 
        'activo_en_sistema'
    )
    search_fields = ('nombre', 'estacion__nombre')
    autocomplete_fields = ['estacion']
    inlines = [PlanActivoConfigInline]
    
    fieldsets = (
        ('Configuración General', {
            'fields': ('nombre', 'estacion', 'activo_en_sistema', 'fecha_inicio')
        }),
        ('Detonante (Trigger)', {
            'fields': ('tipo_trigger',),
            'description': 'Seleccione si el mantenimiento se basa en tiempo o en uso.'
        }),
        ('Configuración por Tiempo', {
            'fields': ('frecuencia', 'intervalo', 'dia_semana'),
            'classes': ('collapse',), # Oculto por defecto para no ensuciar si es por USO
            'description': 'Complete solo si el trigger es TIEMPO.'
        }),
        ('Configuración por Uso', {
            'fields': ('horas_uso_trigger',),
            'classes': ('collapse',),
            'description': 'Complete solo si el trigger es USO.'
        })
    )

    def mostrar_frecuencia(self, obj):
        if obj.tipo_trigger == PlanMantenimiento.TipoTrigger.TIEMPO:
            return f"{obj.intervalo} x {obj.get_frecuencia_display()}"
        else:
            return f"Cada {obj.horas_uso_trigger} horas"
    mostrar_frecuencia.short_description = "Frecuencia"

    def cantidad_activos(self, obj):
        return obj.activos.count()
    cantidad_activos.short_description = "Nº Activos"


@admin.register(OrdenMantenimiento)
class OrdenMantenimientoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = (
        'id', 
        'tipo_orden', 
        'estado_coloreado', 
        'fecha_programada', 
        'estacion', 
        'responsable'
    )
    list_filter = (
        'estado', 
        'tipo_orden', 
        'fecha_programada', 
        'estacion'
    )
    search_fields = ('id', 'estacion__nombre', 'responsable__username')
    autocomplete_fields = ['plan_origen', 'estacion', 'responsable', 'activos_afectados']
    date_hierarchy = 'fecha_programada'
    inlines = [RegistroMantenimientoInline]
    
    fieldsets = (
        ('Cabecera de la Orden', {
            'fields': (
                ('tipo_orden', 'estado'),
                ('fecha_programada', 'fecha_cierre'),
                'estacion',
                'responsable'
            )
        }),
        ('Origen y Alcance', {
            'fields': ('plan_origen', 'activos_afectados')
        }),
    )

    def estado_coloreado(self, obj):
        colors = {
            'PENDIENTE': 'orange',
            'EN_CURSO': '#17a2b8', # Info blue
            'REALIZADA': 'green',
            'CANCELADA': 'red',
        }
        color = colors.get(obj.estado, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_coloreado.short_description = "Estado"
    estado_coloreado.admin_order_field = 'estado'


@admin.register(RegistroMantenimiento)
class RegistroMantenimientoAdmin(SysPermissionMixin, admin.ModelAdmin):
    """
    Admin para consultar el historial completo de mantenimientos (Logs).
    """
    list_display = (
        'activo', 
        'fecha_ejecucion', 
        'orden_link', 
        'usuario_ejecutor', 
        'fue_exitoso'
    )
    list_filter = (
        'fecha_ejecucion', 
        'fue_exitoso', 
        'usuario_ejecutor'
    )
    search_fields = (
        'activo__codigo_activo', 
        'orden_mantenimiento__id', 
        'notas'
    )
    autocomplete_fields = ['orden_mantenimiento', 'activo', 'usuario_ejecutor']
    date_hierarchy = 'fecha_ejecucion'

    def orden_link(self, obj):
        return format_html(
            '<a href="/admin/mantenimiento/ordenmantenimiento/{}/change/">Orden #{}</a>',
            obj.orden_mantenimiento.id,
            obj.orden_mantenimiento.id
        )
    orden_link.short_description = "Orden Ref."