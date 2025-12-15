from django.contrib import admin
from django.utils.html import format_html
from apps.common.admin_mixins import SysPermissionMixin, ImagenPreviewMixin
from .models import TipoDocumento, DocumentoHistorico

@admin.register(TipoDocumento)
class TipoDocumentoAdmin(SysPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'cantidad_documentos')
    search_fields = ('nombre',)
    
    def cantidad_documentos(self, obj):
        return obj.documentos.count()
    cantidad_documentos.short_description = "Nº Documentos"

@admin.register(DocumentoHistorico)
class DocumentoHistoricoAdmin(SysPermissionMixin, ImagenPreviewMixin, admin.ModelAdmin):
    list_display = (
        'mostrar_preview', 
        'titulo', 
        'tipo_documento', 
        'fecha_documento', 
        'estacion', 
        'estado_confidencialidad', 
        'link_archivo'
    )
    list_filter = (
        'tipo_documento', 
        'estacion', 
        'es_confidencial', 
        'fecha_documento'
    )
    search_fields = (
        'titulo', 
        'descripcion', 
        'palabras_clave', 
        'ubicacion_fisica'
    )
    readonly_fields = (
        'preview_imagen', 
        'mostrar_preview_grande', 
        'fecha_creacion', 
        'fecha_modificacion'
    )
    autocomplete_fields = ['estacion', 'usuario_registra']
    date_hierarchy = 'fecha_documento'
    
    fieldsets = (
        ('Información Principal', {
            'fields': (
                ('titulo', 'es_confidencial'),
                ('tipo_documento', 'fecha_documento'),
                'descripcion',
                'palabras_clave'
            )
        }),
        ('Archivo Digital', {
            'fields': ('archivo', 'mostrar_preview_grande', 'preview_imagen'),
            'description': 'El sistema generará la vista previa automáticamente al guardar si el formato es compatible.'
        }),
        ('Ubicación y Origen', {
            'fields': ('estacion', 'ubicacion_fisica', 'usuario_registra')
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )

    def estado_confidencialidad(self, obj):
        """Muestra un icono o texto coloreado si es confidencial."""
        if obj.es_confidencial:
            return format_html(
                '<span style="color:white; background-color:#d9534f; padding:3px 6px; border-radius:3px; font-weight:bold;">CONFIDENCIAL</span>'
            )
        return format_html(
            '<span style="color:green;">Público</span>'
        )
    estado_confidencialidad.short_description = "Privacidad"
    estado_confidencialidad.admin_order_field = 'es_confidencial'

    def link_archivo(self, obj):
        """Botón para descargar el archivo original."""
        if obj.archivo:
            return format_html(
                '<a class="button" href="{}" target="_blank">Abrir Archivo</a>', 
                obj.archivo.url
            )
        return "-"
    link_archivo.short_description = "Archivo"

    def mostrar_preview_grande(self, obj):
        """Muestra la preview en tamaño grande dentro del formulario de edición."""
        if obj.preview_imagen:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 400px; border:1px solid #ddd; padding:5px;" />', 
                obj.preview_imagen.url
            )
        return "Sin vista previa disponible"
    mostrar_preview_grande.short_description = "Vista Actual"