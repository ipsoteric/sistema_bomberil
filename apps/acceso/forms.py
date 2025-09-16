from django import forms


class FormularioLogin(forms.Form):
    rut = forms.CharField(
        required=True, 
        widget=forms.TextInput(
            attrs={
                'id':'id_username',
                'name':'username',
                'class':'input_box__input fs_normal color_primario fondo_secundario_variante',
                'autocomplete':'off',
            }
        )
    )

    password = forms.CharField(
        required=True, 
        widget=forms.PasswordInput(
            attrs={
                'id':'id_password',
                'name':'password',
                'class':'input_box__input fs_normal color_primario fondo_secundario_variante',
                'autocomplete':'off'
            }
        )
    )