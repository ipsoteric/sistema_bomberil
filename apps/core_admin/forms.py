from django import forms
from django.core.exceptions import ValidationError

from apps.gestion_inventario.models import Estacion, Comuna, ProductoGlobal
from apps.gestion_usuarios.models import Usuario


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




class UsuarioCreationForm(forms.ModelForm):
    """
    Formulario para crear usuarios nuevos con validación de contraseña.
    """
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
        help_text="Mínimo 8 caracteres."
    )
    password_confirm = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'})
    )

    class Meta:
        model = Usuario
        fields = ['rut', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'is_staff']
        widgets = {
            'rut': forms.TextInput(attrs={'placeholder': '12.345.678-9'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'Ej: Juan'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Ej: Pérez'}),
            'email': forms.EmailInput(attrs={'placeholder': 'juan.perez@bomberos.cl'}),
            'phone': forms.TextInput(attrs={'placeholder': '9 1234 5678'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'rut': 'RUT (Identificador)',
            'is_active': 'Cuenta Activa',
            'is_staff': 'Es Staff (Acceso Admin)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estilos Bootstrap generales
        for field_name, field in self.fields.items():
            if field_name not in ['is_active', 'is_staff']: # Checkboxes tienen su propia clase
                field.widget.attrs['class'] = 'form-control'

    def clean_rut(self):
        # Normalizar RUT (opcional: quitar puntos y guion si tu lógica lo requiere)
        rut = self.cleaned_data.get('rut')
        if Usuario.objects.filter(rut=rut).exists():
            raise ValidationError("Ya existe un usuario registrado con este RUT.")
        return rut

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Las contraseñas no coinciden.")
        
        return cleaned_data

    def save(self, commit=True):
        # Interceptamos el guardado para hashear la contraseña
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user