from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import Usuario



class FormularioCrearUsuario(forms.Form):
    correo = forms.EmailField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                'id':'LoginInputCorreo',
                'class':'input_box__input fs_normal color_primario fondo_secundario',
                'autocomplete':'off',
            }
        )
    )
    nombre = forms.CharField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                'id':'UsuarioInputNombre',
                'class':'input_box__input fs_normal color_primario fondo_secundario',
                'autocomplete':'off',
            }
        )
    )
    apellido = forms.CharField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                'id':'UsuarioInputApellido',
                'class':'input_box__input fs_normal color_primario fondo_secundario',
                'autocomplete':'off',
            }
        )
    )
    rut = forms.CharField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                'id':'UsuarioInputRut',
                'class':'input_box__input fs_normal color_primario fondo_secundario',
                'autocomplete':'off',
            }
        )
    )
    fecha_nacimiento = forms.DateField(
        required=False, 
        widget=forms.DateInput(
            attrs={
                'type':'date',
                'id':'UsuarioInputFechaNacimiento',
                'class':'input_box__input fs_normal color_primario fondo_secundario',
                'autocomplete':'off',
            }
        )
    )
    telefono = forms.CharField(
        required=False, 
        widget=forms.TextInput(
            attrs={
                'id':'UsuarioInputTelefono',
                'class':'input_box__input fs_normal color_primario fondo_secundario',
                'autocomplete':'off',
            }
        )
    )
    avatar = forms.ImageField(
        required=False, 
        widget=forms.ClearableFileInput(
            attrs={
                'id':'UsuarioInputAvatar',
                'class':'input_box__input-file fs_normal color_primario fondo_secundario',
                'autocomplete':'off',
            }
        )
    )



class FormularioEditarUsuario(forms.ModelForm):
    class Meta:
        model = Usuario
        # Campos editables
        fields = ['first_name', 'last_name', 'phone', 'birthdate', 'avatar']

    # Campos de solo lectura
    rut = forms.CharField(
        label='RUT',
        widget=forms.TextInput(attrs={
                'id':'UsuarioInputRut',
                'class':'input_box__input fs_normal color_primario_variante fondo_secundario',
                'autocomplete':'off',
                'readonly':'readonly'
            })
    )
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
                'id':'UsuarioInputCorreo',
                'class':'input_box__input fs_normal color_primario_variante fondo_secundario',
                'autocomplete':'off',
                'readonly':'readonly'
            })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # El `instance` es el usuario que estamos editando
        if self.instance:
            self.fields['rut'].initial = self.instance.rut
            self.fields['email'].initial = self.instance.email

        # Personaliza otros campos si es necesario
        self.fields['first_name'].widget.attrs.update({'class':'input_box__input fs_normal color_primario fondo_secundario'})
        self.fields['last_name'].widget.attrs.update({'class':'input_box__input fs_normal color_primario fondo_secundario'})
        self.fields['birthdate'].widget.attrs.update({'class':'input_box__input fs_normal color_primario fondo_secundario'})
        self.fields['phone'].widget.attrs.update({'class':'input_box__input fs_normal color_primario fondo_secundario'})



class CustomUserCreationForm(UserCreationForm):
    """
    Formulario para crear nuevos usuarios. Hereda de UserCreationForm
    y se adapta al modelo Usuario personalizado.
    """
    class Meta(UserCreationForm.Meta):
        model = Usuario
        # Incluye los campos que quieres en el formulario de creación.
        # El password se maneja automáticamente por UserCreationForm.
        fields = ('email', 'first_name', 'last_name', 'birthdate')

    
    # --- MÉTODO DE DEPURACIÓN AÑADIDO ---
    def is_valid(self):
        # Llama al is_valid() original primero
        valid = super().is_valid()

        # Si el formulario no es válido, imprime los errores en la consola
        if not valid:
            print("--- ERRORES DE VALIDACIÓN DEL FORMULARIO ---")
            print(self.errors.as_json())
            print("-----------------------------------------")
            
        return valid
    

    def clean(self):
        # Llama a la validación original primero
        cleaned_data = super().clean()
        is_superuser = cleaned_data.get("is_superuser")
        
        # Aquí va el nombre de tu campo, por ejemplo 'rut'
        rut = cleaned_data.get("rut")

        # Si no es superusuario y el campo está vacío, lanza un error
        if not is_superuser and not rut:
            self.add_error('rut', 'Este campo es obligatorio para usuarios regulares.')
        
        return cleaned_data



class CustomUserChangeForm(UserChangeForm):
    """
    Formulario para modificar usuarios existentes. Hereda de UserChangeForm
    y se adapta al modelo Usuario personalizado.
    """
    class Meta:
        model = Usuario
        # __all__ es una opción, pero es mejor ser explícito con los campos.
        fields = ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')