from django import forms
from .models import (
    Ubicacion, 
    Compartimento, 
    Categoria, 
    Marca, 
    ProductoGlobal, 
    Producto, 
    Proveedor,
    ContactoProveedor,
    Region,
    Comuna
    )


class AreaForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        # tipo_seccion y estacion no se exponen: tipo_seccion será 'AREA' y estacion se asigna desde la sesión
        # La imagen no se puede subir en la creación; sólo al editar
        fields = ['nombre', 'descripcion', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'input_box__input fs_normal color_primario fondo_secundario', 'placeholder': 'Nombre del almacén'}),
            'descripcion': forms.Textarea(attrs={'class': 'input_box__input fs_normal color_primario fondo_secundario', 'rows': 3}),
            'direccion': forms.TextInput(attrs={'class': 'input_box__input fs_normal color_primario fondo_secundario', 'placeholder': 'Dirección (opcional)'}),
        }



class AreaEditForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        fields = ['nombre', 'descripcion', 'direccion', 'imagen']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control fs_normal  color_primario fondo_secundario_variante border-0', 'rows': 3}),
            'direccion': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
            'imagen': forms.FileInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
        }



class CompartimentoForm(forms.ModelForm):
    class Meta:
        model = Compartimento
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 'placeholder': 'Nombre del compartimento'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 'rows': 3}),
        }




class ProductoGlobalForm(forms.ModelForm):
    """
    Formulario para la creación de un nuevo Producto Global.
    La validación de marca/modelo vs. genérico se hereda del método .clean()
    que ya definimos en el modelo.
    """
    class Meta:
        model = ProductoGlobal
        fields = [
            'nombre_oficial', 
            'marca', 
            'modelo', 
            'categoria', 
            'descripcion_general', 
            'vida_util_recomendada_anos', 
            'imagen'
        ]
        widgets = {
            'nombre_oficial': forms.TextInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
            'marca': forms.Select(attrs={'class': 'form-select fs_normal fondo_secundario color_primario tom-select-creatable'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
            'categoria': forms.Select(attrs={'class': 'form-select fs_normal fondo_secundario color_primario'}),
            'descripcion_general': forms.Textarea(attrs={'class': 'form-control fs_normal fondo_secundario color_primario', 'rows': 3}),
            'vida_util_recomendada_anos': forms.NumberInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
        }
        help_texts = {
            'nombre_oficial': 'Para productos genéricos (sin marca/modelo), usa un nombre descriptivo y único. Ej: "Guantes de Nitrilo Talla M".',
            'modelo': 'Si seleccionaste una marca, este campo es obligatorio.',
        }

    def __init__(self, *args, **kwargs):
        """
        Poblamos los QuerySets de los campos ForeignKey para que estén ordenados.
        """
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = Categoria.objects.order_by('nombre')
        self.fields['marca'].queryset = Marca.objects.order_by('nombre')




class ProductoLocalEditForm(forms.ModelForm):
    """
    Formulario para editar un Producto local (catálogo de la estación).
    Incluye lógica para deshabilitar 'es_serializado' si ya existe inventario.
    """
    class Meta:
        model = Producto
        fields = [
            'sku', 
            'es_serializado', 
            'es_expirable', 
            'proveedor_preferido', 
            'costo_compra'
        ]
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
            'es_serializado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_expirable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'proveedor_preferido': forms.Select(attrs={'class': 'form-select fs_normal fondo_secundario color_primario'}),
            'costo_compra': forms.NumberInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
        }
        help_texts = {
            'sku': 'Código único interno de tu estación para este producto.',
            'es_serializado': 'Marcar si es un Activo rastreable individualmente (ej: Casco). Desmarcado si es Insumo (ej: Guantes).',
            'es_expirable': 'Marcar si este insumo requiere seguimiento de fecha de expiración.',
        }

    def __init__(self, *args, **kwargs):
        """
        Sobrescribimos __init__ para:
        1. Poblar el queryset de proveedor_preferido.
        2. Recibir la estación y si el campo 'es_serializado' debe estar deshabilitado.
        """
        # Extraemos argumentos personalizados antes de llamar al super()
        estacion_actual = kwargs.pop('estacion', None)
        disable_es_serializado = kwargs.pop('disable_es_serializado', False) 
        
        super().__init__(*args, **kwargs)

        # Filtrar proveedores para mostrar solo los de la estación actual (si aplica)
        # O podrías querer mostrar todos los proveedores globales. Ajusta según necesidad.
        if estacion_actual and 'proveedor_preferido' in self.fields:
             # Asumiendo que Proveedor tiene un campo 'estacion_creadora' o similar
             # Si los proveedores son globales, elimina este filtro.
            self.fields['proveedor_preferido'].queryset = Proveedor.objects.filter(estacion_creadora=estacion_actual).order_by('nombre')
        elif 'proveedor_preferido' in self.fields:
             self.fields['proveedor_preferido'].queryset = Proveedor.objects.order_by('nombre')


        # Deshabilitar 'es_serializado' si se indica
        if disable_es_serializado and 'es_serializado' in self.fields:
            self.fields['es_serializado'].disabled = True
            self.fields['es_serializado'].help_text += " (No se puede modificar porque ya existe inventario registrado para este producto)."

    def clean_es_serializado(self):
        """
        Asegura que si el campo está deshabilitado, no se intente cambiar su valor.
        """
        # Si el campo está deshabilitado, devolvemos el valor original de la instancia
        if self.fields['es_serializado'].disabled:
            return self.instance.es_serializado 
        # Si no, devolvemos el valor enviado en el formulario
        return self.cleaned_data.get('es_serializado')




class ProveedorForm(forms.ModelForm):
    """Formulario para los datos principales del Proveedor."""
    class Meta:
        model = Proveedor
        fields = ['nombre', 'rut'] # Los demás campos se manejarán en la vista o en el contacto
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario'}),
            'rut': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario', 'placeholder': 'Ej: 12345678-9'}),
        }




class ContactoProveedorForm(forms.ModelForm):
    """Formulario para los datos del Contacto (principal o secundario)."""
    # Añadimos un campo para seleccionar la región para el filtro dependiente
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        label="Región",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select fs_normal color_primario fondo_secundario'})
    )

    class Meta:
        model = ContactoProveedor
        fields = [
            'nombre_contacto', 
            'direccion', 
            'region', # El nuevo campo
            'comuna', 
            'telefono', 
            'email', 
            'notas'
        ]
        widgets = {
            'nombre_contacto': forms.TextInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
            'comuna': forms.Select(attrs={'class': 'form-select fs_normal fondo_secundario color_primario'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
            'email': forms.EmailInput(attrs={'class': 'form-control fs_normal fondo_secundario color_primario'}),
            'notas': forms.Textarea(attrs={'class': 'form-control fs_normal fondo_secundario color_primario', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos que el queryset de comuna esté vacío al principio. Se llenará con JS.
        self.fields['comuna'].queryset = Comuna.objects.none()

        if 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['comuna'].queryset = Comuna.objects.filter(region_id=region_id).order_by('nombre')
            except (ValueError, TypeError):
                pass  # Ignorar si la región no es válida
        elif self.instance.pk and self.instance.comuna:
             self.fields['comuna'].queryset = self.instance.comuna.region.comuna_set.order_by('nombre')