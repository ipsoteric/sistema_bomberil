from django.db import models
from django.core.validators import FileExtensionValidator

# Create your models here.
from django.db import models
from django.conf import settings
from apps.gestion_inventario.models import Estacion

# (Opcional: una función para generar rutas de subida ordenadas)
def ruta_archivo_historico(instance, filename):
    # El archivo se guardará en: MEDIA_ROOT/archivo_historico/<estacion_id>/<tipo_id>/<filename>
    return f'archivo_historico/{instance.estacion.id}/{instance.tipo_documento.nombre}/{filename}'


class TipoDocumento(models.Model):
    """
    (Catálogo) Define los tipos de documentos históricos que se pueden subir.
    Ej: "Libro de Actas", "Informe Anual", "Fotografía Histórica", "Planos".
    Cumple con el requisito RF10 de "Tipo de documento".
    """
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Tipo de Documento Histórico"
        verbose_name_plural = "Tipos de Documentos Históricos"
        ordering = ['nombre']

        default_permissions = []
        permissions = [
            ("sys_view_tipodocumento", "System: Puede ver Tipos de Documentos Históricos"),
            ("sys_add_tipodocumento", "System: Puede agregar Tipos de Documentos Históricos"),
            ("sys_change_tipodocumento", "System: Puede cambiar Tipos de Documentos Históricos"),
            ("sys_delete_tipodocumento", "System: Puede eliminar Tipos de Documentos Históricos"),
        ]

    def __str__(self):
        return self.nombre


class DocumentoHistorico(models.Model):
    """
    (Bitácora) Almacena los metadatos de un documento histórico digitalizado.
    El archivo físico se almacena en S3, como define la arquitectura.
    Cumple con el requisito funcional RF10.
    """
    titulo = models.CharField(max_length=255, help_text="Un título claro para el documento.")
    descripcion = models.TextField(blank=True, null=True, help_text="Breve descripción del contenido del documento.")
    
    fecha_documento = models.DateField(
        help_text="Fecha en que se emitió o creó el documento original."
    )
    
    tipo_documento = models.ForeignKey(
        TipoDocumento, 
        on_delete=models.PROTECT, 
        related_name="documentos",
        help_text="Clasificación del documento (ej. Libro de Actas)."
    )
    
    # El archivo físico (PDF, JPG, PNG) almacenado en S3.
    archivo = models.FileField(
        upload_to=ruta_archivo_historico,
        max_length=255,
        help_text="Archivo digitalizado (PDF, JPG, PNG).",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])]
    )
    
    # --- Campos de Trazabilidad ---
    estacion = models.ForeignKey(
        Estacion, 
        on_delete=models.PROTECT,
        help_text="Estación a la que pertenece este documento."
    )

    ubicacion_fisica = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Referencia topográfica del original (Ej. Estante A, Caja 3)."
    )
    
    palabras_clave = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Términos clave separados por comas para mejorar la búsqueda."
    )

    es_confidencial = models.BooleanField(
        default=False,
        verbose_name="Confidencial",
        help_text="Si se marca, el documento solo será visible para usuarios con permisos de gestión (Oficiales)."
    )
    
    usuario_registra = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Usuario que subió el documento al sistema."
    )

    # Campo para la vista previa
    preview_imagen = models.ImageField(
        upload_to="documentos/previews/", 
        null=True, 
        blank=True, 
        editable=False, # El usuario no la sube, el sistema la crea
        help_text="Imagen generada automáticamente de la primera página."
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Documento Histórico"
        verbose_name_plural = "Documentos Históricos"
        ordering = ['-fecha_documento'] # Ordenar por fecha del documento, del más nuevo al más viejo

        default_permissions = []
        permissions = [
            ("sys_view_documentohistorico", "System: Puede ver Documentos Históricos"),
            ("sys_add_documentohistorico", "System: Puede agregar Documentos Históricos"),
            ("sys_change_documentohistorico", "System: Puede cambiar Documentos Históricos"),
            ("sys_delete_documentohistorico", "System: Puede eliminar Documentos Históricos"),
        ]

    def __str__(self):
        return f"{self.titulo} ({self.fecha_documento.year})"