from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import TipoDocumento, DocumentoHistorico

@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)

@admin.register(DocumentoHistorico)
class DocumentoHistoricoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo_documento', 'fecha_documento', 'estacion')
    list_filter = ('tipo_documento', 'estacion', 'fecha_documento')
    search_fields = ('titulo', 'descripcion')
    raw_id_fields = ('usuario_registra',) # Mejor rendimiento para buscar usuarios
    date_hierarchy = 'fecha_documento'