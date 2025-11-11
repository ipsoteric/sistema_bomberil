from django import forms
from apps.gestion_usuarios.models import Usuario
from .models import Voluntario

class UsuarioForm(forms.ModelForm):
    """
    Formulario para editar los campos del modelo Usuario
    (Datos de contacto y acceso)
    """
    class Meta:
        model = Usuario
        # Campos de Usuario que quieres que sean editables
        fields = ['first_name', 'last_name', 'rut', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'rut': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'rut': 'RUT',
            'email': 'Correo Electrónico',
            'phone': 'Teléfono',
        }

class VoluntarioForm(forms.ModelForm):
    """
    Formulario para editar los campos del perfil Voluntario
    (Datos personales y bomberiles)
    """
    # Hacemos que los campos de fecha usen el widget de Fecha de HTML5
    fecha_nacimiento = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Fecha de Nacimiento",
        required=False
    )
    fecha_primer_ingreso = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Fecha Primer Ingreso",
        help_text="Fecha de ingreso a su primera estación (para calcular antigüedad total)",
        required=False
    )

    class Meta:
        model = Voluntario
        # Campos de Voluntario que quieres que sean editables
        fields = [
            'nacionalidad', 'profesion', 'lugar_nacimiento', 'fecha_nacimiento',
            'genero', 'estado_civil', 'domicilio_comuna', 'domicilio_calle',
            'domicilio_numero', 'fecha_primer_ingreso', 'numero_registro_bomberil'
        ]
        # Aplicamos la clase 'form-control' (o la que uses) a todos los widgets
        widgets = {
            'nacionalidad': forms.Select(attrs={'class': 'form-control'}),
            'profesion': forms.Select(attrs={'class': 'form-control'}),
            'lugar_nacimiento': forms.TextInput(attrs={'class': 'form-control'}),
            'genero': forms.Select(attrs={'class': 'form-control'}),
            'estado_civil': forms.Select(attrs={'class': 'form-control'}),
            'domicilio_comuna': forms.Select(attrs={'class': 'form-control'}),
            'domicilio_calle': forms.TextInput(attrs={'class': 'form-control'}),
            'domicilio_numero': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_registro_bomberil': forms.TextInput(attrs={'class': 'form-control'}),
        }