from django import forms
from apps.gestion_usuarios.models import Usuario


class EditarPerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'phone', 'birthdate']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control fs_normal'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control fs_normal'}),
            'phone': forms.TextInput(attrs={'class': 'form-control fs_normal'}),
            'birthdate': forms.DateInput(attrs={'class': 'form-control fs_normal', 'type': 'date'}),
        }
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'phone': 'Teléfono',
            'birthdate': 'Fecha de Nacimiento',
        }