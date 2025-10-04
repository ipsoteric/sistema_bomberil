from django import forms
from .models import Seccion


class AlmacenForm(forms.ModelForm):
    class Meta:
        model = Seccion
        # tipo_seccion y estacion no se exponen: tipo_seccion será 'AREA' y estacion se asigna desde la sesión
        # La imagen no se puede subir en la creación; sólo al editar
        fields = ['nombre', 'descripcion', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'input_box__input fs_normal color_primario fondo_secundario', 'placeholder': 'Nombre del almacén'}),
            'descripcion': forms.Textarea(attrs={'class': 'input_box__input fs_normal color_primario fondo_secundario', 'rows': 3}),
            'direccion': forms.TextInput(attrs={'class': 'input_box__input fs_normal color_primario fondo_secundario', 'placeholder': 'Dirección (opcional)'}),
        }
