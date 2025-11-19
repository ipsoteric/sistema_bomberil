from django import forms
from apps.gestion_inventario.models import Estacion, Comuna, ProductoGlobal

class EstacionForm(forms.ModelForm):
    class Meta:
        model = Estacion
        fields = ['nombre', 'descripcion', 'es_departamento', 'direccion', 'comuna', 'logo', 'imagen']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'es_departamento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Aplicar clases de Bootstrap a todos los campos visibles
        for field_name, field in self.fields.items():
            if field_name != 'es_departamento': # El checkbox tiene su propia clase
                field.widget.attrs['class'] = 'form-control'
        
        # 2. Optimizar el selector de Comunas (ordenar y mostrar región)
        # [cite_start]Esto evita que salgan desordenadas. [cite: 11]
        self.fields['comuna'].queryset = Comuna.objects.select_related('region').order_by('region__nombre', 'nombre')
        
        # 3. Etiquetas personalizadas si hacen falta
        self.fields['comuna'].empty_label = "Seleccione una Comuna..."




class ProductoGlobalForm(forms.ModelForm):
    class Meta:
        model = ProductoGlobal
        fields = [
            'nombre_oficial', 'categoria', 'marca', 'modelo', 
            'gtin', 'vida_util_recomendada_anos', 'descripcion_general', 'imagen'
        ]
        widgets = {
            'descripcion_general': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describa las características técnicas principales...'}),
            'nombre_oficial': forms.TextInput(attrs={'placeholder': 'Ej: Hacha de Bombero Flathead'}),
            'modelo': forms.TextInput(attrs={'placeholder': 'Ej: G1, 4.5, AirPak...'}),
            'gtin': forms.TextInput(attrs={'placeholder': 'Código de barras / EAN'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Aplicar estilos Bootstrap a todos los campos
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

        # Mejorar la UX de los selectores
        self.fields['categoria'].empty_label = "Seleccione Categoría..."
        self.fields['marca'].empty_label = "Sin Marca (Genérico)"
        
        # Etiquetas más claras para el admin
        self.fields['vida_util_recomendada_anos'].label = "Vida Útil Estándar (Años)"