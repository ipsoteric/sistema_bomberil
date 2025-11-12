from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import Usuario, Rol



class FormularioCrearUsuario(forms.Form):
    correo = forms.EmailField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                # Reemplazamos las clases por las de Bootstrap + tu clase de fuente
                'class': 'form-control form-control-sm fs_normal',
                'autocomplete': 'off',
                'placeholder': 'ejemplo@correo.com' # (Recomendado)
            }
        )
    )
    nombre = forms.CharField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                'class': 'form-control form-control-sm fs_normal',
                'autocomplete': 'off',
            }
        )
    )
    apellido = forms.CharField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                'class': 'form-control form-control-sm fs_normal',
                'autocomplete': 'off',
            }
        )
    )
    rut = forms.CharField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                'class': 'form-control form-control-sm fs_normal',
                'autocomplete': 'off',
                'placeholder': '12.345.678-9' # (Recomendado)
            }
        )
    )
    fecha_nacimiento = forms.DateField(
        required=False, 
        widget=forms.DateInput(
            attrs={
                'type': 'date', # Mantenemos esto
                'class': 'form-control form-control-sm fs_normal',
                'autocomplete': 'off',
            }
        )
    )
    telefono = forms.CharField(
        required=False, 
        widget=forms.TextInput(
            attrs={
                'class': 'form-control form-control-sm fs_normal',
                'autocomplete': 'off',
            }
        )
    )
    avatar = forms.ImageField(
        required=False, 
        widget=forms.ClearableFileInput(
            attrs={
                # Bootstrap estiliza los inputs de archivo con 'form-control'
                'class': 'form-control form-control-sm fs_normal',
                'autocomplete': 'off',
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




class FormularioRol(forms.ModelForm):
    '''Formulario para roles personalizados'''

    class Meta:
        model = Rol
        # Campos editables
        fields = ['nombre', 'descripcion']


    def __init__(self, *args, **kwargs):
        # 1. Obtener la 'estacion' que viene desde la vista.
        self.estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)

        # Personaliza otros campos si es necesario
        self.fields['nombre'].widget.attrs.update({'class': 'form-control form-control-sm fs_normal', 'autocomplete': 'off'})
        self.fields['descripcion'].widget.attrs.update({'class': 'form-control form-control-sm fs_normal', 'autocomplete': 'off', 'rows': 3})


    def save(self, commit=True):
        # Sobrescribir el método save. Obtener la instancia del rol antes de guardarla en la BD.
        instance = super().save(commit=False)

        # 4. Asignar la estación si el rol es nuevo
        if self.estacion and not self.instance.pk:
            instance.estacion = self.estacion

        if commit:
            instance.save()
            # self.save_m2m() # Necesario si el form manejara campos ManyToMany
        return instance



