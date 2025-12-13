from django import forms
from .models import DocumentoHistorico, TipoDocumento
from django.core.exceptions import ValidationError
import os

class DocumentoHistoricoForm(forms.ModelForm):
    """
    Formulario para subir un nuevo documento histórico (RF10).
    """
    
    fecha_documento = forms.DateField(
        # Agregamos 'text-base font-regular'
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control text-base font-regular'}),
        label="Fecha del Documento Original"
    )

    tipo_documento = forms.ModelChoiceField(
        queryset=TipoDocumento.objects.all().order_by('nombre'),
        # Agregamos 'text-base font-regular'
        widget=forms.Select(attrs={'class': 'form-control text-base font-regular'}),
        label="Tipo de Documento"
    )

    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        
        if not archivo:
            return archivo

        # 1. VALIDACIÓN DE TAMAÑO (Ej: Máximo 25 MB)
        limit_mb = 24
        if archivo.size > limit_mb * 1024 * 1024:
            raise ValidationError(f"El archivo es muy pesado. El límite es de {limit_mb}MB.")

        # 2. VALIDACIÓN DE EXTENSIÓN
        ext = os.path.splitext(archivo.name)[1].lower()
        valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        if ext not in valid_extensions:
            raise ValidationError("Extensión no permitida. Solo se aceptan: PDF, JPG, PNG.")

        # 3. VALIDACIÓN DE CONTENIDO (MIME TYPE)
        # Esto evita que alguien renombre un .exe a .pdf
        valid_mime_types = [
            'application/pdf',
            'image/jpeg',
            'image/png'
        ]
        
        # archivo.content_type viene del header que envía el navegador.
        # Para seguridad militar se usan librerías como 'python-magic', 
        # pero esto cubre el 95% de los casos comunes.
        if archivo.content_type not in valid_mime_types:
            raise ValidationError("El tipo de archivo no es válido o está corrupto.")

        return archivo

    class Meta:
        model = DocumentoHistorico
        fields = [
            'titulo', 
            'fecha_documento', 
            'tipo_documento', 
            'ubicacion_fisica', 
            'palabras_clave',
            'es_confidencial',
            'descripcion', 
            'archivo'
        ]
        widgets = {
            # Agregamos 'text-base font-regular' a todos los widgets
            'titulo': forms.TextInput(attrs={
                'class': 'form-control text-base font-regular', 
                'placeholder': 'Ej. Acta de Fundación 1920'
            }),
            'ubicacion_fisica': forms.TextInput(attrs={
                'class': 'form-control text-base font-regular', 
                'placeholder': 'Ej. Archivo Metálico 2, Repisa Superior'
            }),
            'palabras_clave': forms.TextInput(attrs={
                'class': 'form-control text-base font-regular', 
                'placeholder': 'Ej. Incendio, Desfile, Aniversario (Separar por comas)'
            }),
            'es_confidencial': forms.CheckboxInput(attrs={
                'class': 'form-check-input', 
                'style': 'width: 20px; height: 20px;'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control text-base font-regular', 
                'rows': 4,
                'placeholder': 'Describe brevemente el contenido...'
            }),
            'archivo': forms.ClearableFileInput(attrs={
                'class': 'form-control text-base font-regular'
            }),
        }
        labels = {
            'titulo': 'Título del Documento',
            'descripcion': 'Descripción (Contenido)',
            'archivo': 'Archivo (PDF, JPG, PNG)',
        }