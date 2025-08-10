from django import forms


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