from django import forms
from apps.gestion_usuarios.models import Usuario


class EditarPerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'phone', 'birthdate']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control text-base'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control text-base'}),
            'phone': forms.TextInput(attrs={'class': 'form-control text-base'}),
            'birthdate': forms.DateInput(attrs={'class': 'form-control text-base', 'type': 'date'}),
        }
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'phone': 'Teléfono',
            'birthdate': 'Fecha de Nacimiento',
        }