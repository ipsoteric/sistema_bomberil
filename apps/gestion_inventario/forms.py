from django import forms
from django.utils import timezone
from django.db.models import Q
from .models import (
    Region,
    Comuna,
    Estado,
    Ubicacion, 
    Vehiculo,
    TipoVehiculo,
    Compartimento, 
    Categoria, 
    Marca, 
    ProductoGlobal, 
    Producto, 
    Proveedor,
    ContactoProveedor,
    Activo,
    LoteInsumo,
    TipoMovimiento,
    Destinatario,
    Prestamo
)
from apps.gestion_usuarios.models import Usuario


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



class VehiculoUbicacionCreateForm(forms.ModelForm):
    """
    Formulario para la parte 'Ubicacion' al crear un Vehículo.
    Sigue el estilo de AreaForm (sin imagen, sin dirección).
    """
    class Meta:
        model = Ubicacion
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'input_box__input fs_normal color_primario fondo_secundario', 
                'placeholder': 'Nombre (Ej: "B-1", "Carro 1")'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'input_box__input fs_normal color_primario fondo_secundario', 
                'rows': 3,
                'placeholder': 'Descripción (opcional)'
            }),
        }



class VehiculoUbicacionEditForm(forms.ModelForm):
    """
    Formulario para editar la parte 'Ubicacion' de un vehículo.
    (nombre, descripción, imagen, etc.)
    """
    class Meta:
        model = Ubicacion
        # Usamos los mismos campos que AreaEditForm para consistencia
        fields = ['nombre', 'descripcion', 'imagen']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 'rows': 3}),
            'direccion': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
            'imagen': forms.FileInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
        }


class VehiculoDetalleEditForm(forms.ModelForm):
    """
    Formulario para editar la parte 'Vehiculo' (detalles técnicos).
    """
    class Meta:
        model = Vehiculo
        # Excluimos 'ubicacion' porque se manejará en la vista
        fields = ['tipo_vehiculo', 'patente', 'marca', 'modelo', 'anho', 'chasis']
        widgets = {
            'tipo_vehiculo': forms.Select(attrs={'class': 'form-select fs_normal color_primario fondo_secundario_variante border-0 tom-select-basic'}),
            'patente': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
            'marca': forms.Select(attrs={'class': 'form-select fs_normal color_primario fondo_secundario_variante border-0 tom-select-creatable'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
            'anho': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 'placeholder': 'Ej: 2023'}),
            'chasis': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Poblamos los QuerySets de los campos ForeignKey para que estén ordenados.
        """
        super().__init__(*args, **kwargs)
        self.fields['tipo_vehiculo'].queryset = TipoVehiculo.objects.order_by('nombre')
        self.fields['marca'].queryset = Marca.objects.order_by('nombre')



class CompartimentoForm(forms.ModelForm):
    class Meta:
        model = Compartimento
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 'placeholder': 'Nombre del compartimento'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 'rows': 3}),
        }




class CompartimentoEditForm(forms.ModelForm):
    """
    Formulario para editar los detalles de un compartimento.
    No permite cambiar la ubicación (Ubicacion) a la que pertenece.
    """
    class Meta:
        model = Compartimento
        fields = ['nombre', 'descripcion', 'imagen']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 
                'rows': 4
            }),
            'imagen': forms.FileInput(attrs={
                'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'
            }),
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




class RecepcionCabeceraForm(forms.Form):
    """ Formulario para los datos generales de la recepción """
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.none(), # Se poblará en la vista
        label="Proveedor",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm fs_normal'})
    )
    fecha_recepcion = forms.DateField(
        label="Fecha de Recepción",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm fs_normal'}),
        initial=timezone.now().date() 
    )
    notas = forms.CharField(
        label="Notas Adicionales (Opcional)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm fs_normal'})
    )

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        if estacion:
            # Filtra proveedores por la estación activa
            self.fields['proveedor'].queryset = Proveedor.objects.filter(estacion_creadora=estacion)




class RecepcionDetalleForm(forms.Form):
    """ Formulario para cada línea de producto en la recepción """
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.none(), # Se poblará en la vista
        label="Producto",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm producto-select fs_normal'}) # Clase para JS
    )
    compartimento_destino = forms.ModelChoiceField(
        queryset=Compartimento.objects.none(), # Se poblará en la vista
        label="Destino",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm fs_normal'})
    )
    
    # --- Campos Comunes ---
    costo_unitario = forms.DecimalField(
        label="Costo Unit.", 
        required=False, 
        max_digits=10, 
        decimal_places=0,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm fs_normal', 'step': '1'})
    )

    # --- Campos para INSUMOS (No Serializados) ---
    cantidad = forms.IntegerField(
        label="Cantidad", 
        min_value=1, 
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm insumo-field fs_normal', 'step': '1'}), # Clase para JS
        required=False # Lo hacemos no requerido inicialmente, validaremos en clean
    )
    numero_lote = forms.CharField(
        label="N° Lote", 
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm insumo-field fs_normal'}) # Clase para JS
    )
    fecha_vencimiento = forms.DateField(
        label="Fecha de Vencimiento", 
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm insumo-field fs_normal'}) # Clase para JS
    )
    numero_serie = forms.CharField(
        label="N° Serie Fab.", 
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm activo-field fs_normal'}) # Clase para JS
    )
    fecha_fabricacion = forms.DateField(
        label="Fecha de Fabricación", 
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm activo-field fs_normal'}) # Clase para JS
    )

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)

        if estacion:
            self.fields['producto'].queryset = Producto.objects.filter(estacion=estacion).select_related('producto_global')
            self.fields['compartimento_destino'].queryset = Compartimento.objects.filter(ubicacion__estacion=estacion).select_related('ubicacion')

        if 'producto' in self.fields:
            self.fields['producto'].label_from_instance = lambda obj: obj.producto_global.nombre_oficial

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        
        if producto:
            if producto.es_serializado:
                # Para Activos, N° Serie es usualmente requerido (ajusta según necesidad)
                # if not cleaned_data.get('numero_serie'):
                #     self.add_error('numero_serie', 'El número de serie es requerido para activos.')
                # Limpiamos campos de insumo si se ingresaron por error
                cleaned_data['cantidad'] = 1 # Los activos siempre tienen cantidad 1
                cleaned_data['numero_lote'] = None
                cleaned_data['fecha_vencimiento'] = None
            else:
                # Para Insumos, Cantidad es requerida
                if not cleaned_data.get('cantidad'):
                    self.add_error('cantidad', 'La cantidad es requerida para insumos.')
                # Fecha vencimiento puede ser requerida si el producto es expirable
                if producto.es_expirable and not cleaned_data.get('fecha_vencimiento'):
                     self.add_error('fecha_vencimiento', 'La fecha de vencimiento es requerida para este producto.')
                # Limpiamos campos de activo
                cleaned_data['numero_serie'] = None
                cleaned_data['fecha_fabricacion'] = None
        return cleaned_data

# Creamos el FormSet
RecepcionDetalleFormSet = forms.formset_factory(
    RecepcionDetalleForm, 
    extra=1, # Empieza con una línea vacía
    can_delete=True # Permite eliminar líneas
)




class ActivoSimpleCreateForm(forms.ModelForm):
    """
    Formulario rápido para crear un Activo y asignarlo a un compartimento.
    """

    def __init__(self, *args, **kwargs):
        # Recibimos el estacion_id desde la vista para filtrar
        estacion_id = kwargs.pop('estacion_id', None)
        super().__init__(*args, **kwargs)

        if estacion_id:
            # Filtramos productos: solo de esta estación Y que sean serializados
            self.fields['producto'].queryset = Producto.objects.filter(
                estacion_id=estacion_id, 
                es_serializado=True
            ).select_related('producto_global')
            
            # Filtramos proveedores: solo los de esta estación (basado en tu RecepcionCabeceraForm)
            self.fields['proveedor'].queryset = Proveedor.objects.filter(
                estacion_creadora=estacion_id
            ).order_by('nombre')
        
        # Ocultamos el campo compartimento, se asigna desde la vista
        if 'compartimento' in self.fields:
            self.fields['compartimento'].widget = forms.HiddenInput()
        
        # Ponemos la fecha de recepción por defecto
        if 'fecha_recepcion' in self.fields:
            self.fields['fecha_recepcion'].initial = timezone.now().date()
        
        # Aplicamos clases de estilo
        css_class = 'form-control fs_normal color_primario fondo_secundario_variante border-0'
        css_class_select = 'form-select fs_normal color_primario fondo_secundario_variante border-0'
        
        self.fields['producto'].widget.attrs.update({'class': css_class_select})
        self.fields['proveedor'].widget.attrs.update({'class': css_class_select})
        self.fields['numero_serie_fabricante'].widget.attrs.update({'class': css_class})
        self.fields['notas_adicionales'].widget.attrs.update({'class': css_class, 'rows': 3})
        
        date_widget_attrs = {'class': css_class, 'type': 'date'}
        self.fields['fecha_fabricacion'].widget = forms.DateInput(attrs=date_widget_attrs)
        self.fields['fecha_recepcion'].widget = forms.DateInput(attrs=date_widget_attrs)
        self.fields['fecha_expiracion'].widget = forms.DateInput(attrs=date_widget_attrs)


    class Meta:
        model = Activo
        # 'codigo_activo' se genera solo, 'estacion' se pasa en la vista
        fields = [
            'producto', 
            'compartimento', 
            'proveedor',
            'numero_serie_fabricante', 
            'fecha_recepcion', 
            'fecha_fabricacion',
            'fecha_expiracion',
            'notas_adicionales',
        ]




class LoteInsumoSimpleCreateForm(forms.ModelForm):
    """
    Formulario rápido para crear un Lote de Insumo y asignarlo a un compartimento.
    """
    
    def __init__(self, *args, **kwargs):
        # Recibimos el estacion_id desde la vista para filtrar
        estacion_id = kwargs.pop('estacion_id', None)
        super().__init__(*args, **kwargs)

        if estacion_id:
            # Filtramos productos: solo de esta estación Y que NO sean serializados
            self.fields['producto'].queryset = Producto.objects.filter(
                estacion_id=estacion_id, 
                es_serializado=False
            ).select_related('producto_global')

        # Ocultamos el campo compartimento, se asigna desde la vista
        if 'compartimento' in self.fields:
            self.fields['compartimento'].widget = forms.HiddenInput()

        # Ponemos la fecha de recepción por defecto
        if 'fecha_recepcion' in self.fields:
            self.fields['fecha_recepcion'].initial = timezone.now().date()

        # Aplicamos clases de estilo
        css_class = 'form-control fs_normal color_primario fondo_secundario_variante border-0'
        css_class_select = 'form-select fs_normal color_primario fondo_secundario_variante border-0'

        self.fields['producto'].widget.attrs.update({'class': css_class_select})
        self.fields['cantidad'].widget.attrs.update({'class': css_class, 'type': 'number', 'min': '1', 'step': '1'})
        self.fields['numero_lote_fabricante'].widget.attrs.update({'class': css_class})
        
        date_widget_attrs = {'class': css_class, 'type': 'date'}
        self.fields['fecha_recepcion'].widget = forms.DateInput(attrs=date_widget_attrs)
        self.fields['fecha_expiracion'].widget = forms.DateInput(attrs=date_widget_attrs)
        
    def clean(self):
        """
        Validación basada en la lógica de tu RecepcionDetalleForm:
        Si el producto 'es_expirable', la fecha de expiración es obligatoria.
        """
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        fecha_expiracion = cleaned_data.get('fecha_expiracion')

        if producto and producto.es_expirable and not fecha_expiracion:
            self.add_error('fecha_expiracion', 'La fecha de expiración es requerida para este producto.')
        
        return cleaned_data

    class Meta:
        model = LoteInsumo
        fields = [
            'producto', 
            'compartimento', 
            'cantidad', 
            'numero_lote_fabricante', 
            'fecha_recepcion', 
            'fecha_expiracion'
        ]




class LoteAjusteForm(forms.Form):
    """
    Formulario para ajustar la cantidad de un lote y registrar el motivo.
    """
    nueva_cantidad_fisica = forms.IntegerField(
        label="Nueva Cantidad Física",
        min_value=0, # Puede ajustarse a 0 si el lote se perdió
        widget=forms.NumberInput(attrs={
            'class': 'form-control fs_grande text-center', 
            'style': 'max-width: 200px; margin: 0 auto;' # Centrar y limitar ancho
        })
    )
    notas = forms.CharField(
        label="Motivo del Ajuste (Obligatorio)",
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 
            'rows': 3,
            'placeholder': 'Ej: Conteo físico 04/11/2025, se encontraron 2 unidades rotas.'
        })
    )




class MovimientoFilterForm(forms.Form):
    
    # Usamos required=False para que no sean obligatorios
    q = forms.CharField(
        label="Buscar", 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm fs_normal', 
            'placeholder': 'Producto, SKU, Lote, Notas...'
        })
    )
    
    tipo_movimiento = forms.ChoiceField(
        label="Tipo de Movimiento",
        required=False,
        choices=[('', '-- Todos --')] + TipoMovimiento.choices, # Añade "Todos"
        widget=forms.Select(attrs={'class': 'form-select form-select-sm fs_normal'})
    )
    
    usuario = forms.ModelChoiceField(
        label="Usuario",
        required=False,
        queryset=Usuario.objects.none(), # Se poblará en la vista
        widget=forms.Select(attrs={'class': 'form-select form-select-sm fs_normal'})
    )
    
    fecha_inicio = forms.DateField(
        label="Desde",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm fs_normal'})
    )
    
    fecha_fin = forms.DateField(
        label="Hasta",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm fs_normal'})
    )

    def __init__(self, *args, **kwargs):
        # Recibimos la estación desde la vista para filtrar el queryset de usuarios
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        
        if estacion:
            # CORRECCIÓN: Usamos la relación 'membresias' definida en tu modelo Membresia
            self.fields['usuario'].queryset = Usuario.objects.filter(
                membresias__estacion=estacion
            ).order_by('first_name').distinct()




class BajaExistenciaForm(forms.Form):
    """
    Formulario para registrar el motivo al dar de baja una existencia.
    """
    notas = forms.CharField(
        label="Motivo de la Baja (Obligatorio)",
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 
            'rows': 3,
            'placeholder': 'Ej: Fin de vida útil, casco roto en emergencia, lote vencido.'
        })
    )




class ExtraviadoExistenciaForm(forms.Form):
    """
    Formulario para registrar el motivo al reportar una existencia como extraviada.
    """
    notas = forms.CharField(
        label="Notas (Obligatorio)",
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 
            'rows': 3,
            'placeholder': 'Ej: No encontrado durante el inventario físico 05/11/2025.'
        })
    )




class LoteConsumirForm(forms.Form):
    """
    Formulario para consumir una cantidad específica de un lote.
    """
    cantidad_a_consumir = forms.IntegerField(
        label="Cantidad a Consumir",
        min_value=1, # Se debe consumir al menos 1
        widget=forms.NumberInput(attrs={
            'class': 'form-control fs_grande text-center', 
            'style': 'max-width: 200px; margin: 0 auto;'
        })
    )
    notas = forms.CharField(
        label="Motivo del Consumo (Obligatorio)",
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 
            'rows': 3,
            'placeholder': 'Ej: Usado en emergencia Av. Prat, Salida 10-2.'
        })
    )

    def __init__(self, *args, **kwargs):
        # Pasamos el 'lote' a la vista para validación
        self.lote = kwargs.pop('lote', None)
        super().__init__(*args, **kwargs)

    def clean_cantidad_a_consumir(self):
        """
        Valida que la cantidad a consumir no sea mayor
        que la cantidad disponible en el lote.
        """
        cantidad = self.cleaned_data.get('cantidad_a_consumir')
        if self.lote and cantidad > self.lote.cantidad:
            raise forms.ValidationError(
                f"No se puede consumir más de la cantidad disponible ({self.lote.cantidad})."
            )
        return cantidad




class TransferenciaForm(forms.Form):
    """
    Formulario para transferir una existencia (Activo o Lote)
    a un nuevo compartimento.
    """
    compartimento_destino = forms.ModelChoiceField(
        queryset=Compartimento.objects.none(), # Se poblará en la vista
        label="Compartimento de Destino",
        widget=forms.Select(attrs={
            'class': 'form-select fs_normal color_primario fondo_secundario_variante border-0 tom-select-basic'
        })
    )
    
    cantidad = forms.IntegerField(
        label="Cantidad a Mover",
        min_value=1,
        required=False, # No es requerido para Activos
        widget=forms.NumberInput(attrs={
            'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0'
        })
    )
    
    notas = forms.CharField(
        label="Notas (Opcional)",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control fs_normal color_primario fondo_secundario_variante border-0', 
            'rows': 3,
            'placeholder': 'Ej: Préstamo a B-2 para emergencia.'
        })
    )

    def __init__(self, *args, **kwargs):
        # Pasamos el 'item' (Activo o Lote) desde la vista
        self.item = kwargs.pop('item', None)
        self.estacion = kwargs.pop('estacion', None)
        
        super().__init__(*args, **kwargs)

        if self.estacion and self.item:
            # Filtramos el queryset para mostrar solo compartimentos de la misma estación,
            # excluyendo el compartimento actual.
            self.fields['compartimento_destino'].queryset = Compartimento.objects.filter(
                ubicacion__estacion=self.estacion
            ).exclude(
                id=self.item.compartimento.id
            ).select_related('ubicacion').order_by('ubicacion__nombre', 'nombre')

        # Si el ítem es un Activo, ocultamos y deshabilitamos 'cantidad'
        if self.item and self.item.producto.es_serializado:
            self.fields['cantidad'].widget = forms.HiddenInput()
            self.fields['cantidad'].disabled = True
        else:
            # Es un lote, hacemos 'cantidad' obligatoria
            self.fields['cantidad'].required = True

    def clean_cantidad(self):
        """
        Valida que la cantidad a mover no sea mayor que la disponible.
        """
        # Solo validamos si es un Lote
        if self.item and not self.item.producto.es_serializado:
            cantidad_a_mover = self.cleaned_data.get('cantidad')
            if cantidad_a_mover > self.item.cantidad:
                raise forms.ValidationError(
                    f"No se puede mover más de la cantidad disponible ({self.item.cantidad})."
                )
            return cantidad_a_mover
        
        # Si es un Activo, la cantidad será 1 (manejada en la vista)
        return self.cleaned_data.get('cantidad')




class EtiquetaFilterForm(forms.Form):
    """Formulario utilizado para imprimir etiquetas QR"""
    
    ubicacion = forms.ModelChoiceField(
        label="Filtrar por Ubicación",
        required=False,
        queryset=Ubicacion.objects.none(), # Se poblará en la vista
        widget=forms.Select(attrs={'class': 'form-select form-select-sm fs_normal'})
    )
    
    # (Podrías añadir más filtros si quisieras, ej: por producto)

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        
        if estacion:
            # Filtramos para mostrar solo ubicaciones operativas (no 'ADMINISTRATIVA')
            self.fields['ubicacion'].queryset = Ubicacion.objects.filter(
                estacion=estacion
            ).exclude(
                tipo_ubicacion__nombre='ADMINISTRATIVA'
            ).order_by('nombre')




class PrestamoCabeceraForm(forms.ModelForm):
    """ Formulario para los datos generales del préstamo """
    
    # Campo para crear un destinatario "al vuelo"
    nuevo_destinatario_nombre = forms.CharField(
        label="O crear nuevo destinatario",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm fs_normal',
            'placeholder': 'Nombre (Ej: Clínica XYZ)'
        })
    )
    nuevo_destinatario_contacto = forms.CharField(
        label="Contacto (Opcional)",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm fs_normal',
            'placeholder': 'Persona/Teléfono'
        })
    )

    class Meta:
        model = Prestamo
        fields = [
            'destinatario', 
            'fecha_devolucion_esperada', 
            'notas_prestamo',
            'nuevo_destinatario_nombre',
            'nuevo_destinatario_contacto'
        ]
        widgets = {
            'destinatario': forms.Select(attrs={'class': 'form-select form-select-sm fs_normal tom-select-basic'}),
            'fecha_devolucion_esperada': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm fs_normal'}),
            'notas_prestamo': forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm fs_normal'}),
        }

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        if estacion:
            self.fields['destinatario'].queryset = Destinatario.objects.filter(estacion=estacion).order_by('nombre_entidad')
            self.fields['destinatario'].required = False # Permitir seleccionar o crear

    def clean(self):
        cleaned_data = super().clean()
        destinatario = cleaned_data.get('destinatario')
        nuevo_nombre = cleaned_data.get('nuevo_destinatario_nombre')

        if not destinatario and not nuevo_nombre:
            raise forms.ValidationError("Debe seleccionar un destinatario existente o ingresar el nombre de uno nuevo.")
        if destinatario and nuevo_nombre:
            raise forms.ValidationError("No puede seleccionar un destinatario existente Y crear uno nuevo al mismo tiempo.")
        
        return cleaned_data




class PrestamoDetalleForm(forms.Form):
    """
    Formulario para cada línea de ítem en el préstamo.
    Usamos un forms.Form para manejar la lógica de selección Activo/Lote.
    """
    # Usamos un ModelChoiceField de Producto para filtrar
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.none(), # Se poblará en la vista
        label="Producto",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm fs_normal producto-select'})
    )
    
    # Campo para seleccionar un Activo (si es serializado)
    activo = forms.ModelChoiceField(
        queryset=Activo.objects.none(),
        label="ID Activo",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm fs_normal activo-select'})
    )
    
    # Campo para seleccionar un Lote (si es insumo)
    lote = forms.ModelChoiceField(
        queryset=LoteInsumo.objects.none(),
        label="Lote",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm fs_normal lote-select'})
    )
    
    cantidad = forms.IntegerField(
        label="Cantidad", 
        min_value=1, 
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm fs_normal cantidad-input'}),
        required=False # Se validará en 'clean'
    )

    def __init__(self, *args, **kwargs):
        self.estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        
        if self.estacion:
            # Filtra solo productos que TIENEN stock disponible
            productos_con_stock = Producto.objects.filter(
                Q(estacion=self.estacion) &
                (
                    Q(activo__estado__nombre='DISPONIBLE') |
                    Q(loteinsumo__estado__nombre='DISPONIBLE', loteinsumo__cantidad__gt=0)
                )
            ).distinct().select_related('producto_global')
            
            self.fields['producto'].queryset = productos_con_stock
            
            # Formateamos el label del producto
            self.fields['producto'].label_from_instance = lambda obj: f"{obj.producto_global.nombre_oficial} ({'Activo' if obj.es_serializado else 'Insumo'})"

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        
        if not producto:
            return cleaned_data # No hay nada que validar

        if producto.es_serializado:
            activo = cleaned_data.get('activo')
            if not activo:
                self.add_error('activo', "Debe seleccionar un Activo específico.")
            # Limpiar campos de lote
            cleaned_data['lote'] = None
            cleaned_data['cantidad'] = 1
        
        else: # Es Insumo
            lote = cleaned_data.get('lote')
            cantidad = cleaned_data.get('cantidad')
            
            if not lote:
                self.add_error('lote', "Debe seleccionar un Lote disponible.")
            if not cantidad:
                self.add_error('cantidad', "Debe ingresar una cantidad.")
            
            if lote and cantidad and cantidad > lote.cantidad:
                self.add_error('cantidad', f"No puede prestar más de {lote.cantidad} (stock actual del lote).")
            
            # Limpiar campo de activo
            cleaned_data['activo'] = None
            
        return cleaned_data


# Creamos el FormSet
PrestamoDetalleFormSet = forms.formset_factory(
    PrestamoDetalleForm, 
    extra=1, # Empieza con una línea vacía
    can_delete=True
)




class PrestamoFilterForm(forms.Form):
    """
    Formulario para filtrar el historial de préstamos.
    """
    destinatario = forms.ModelChoiceField(
        label='Destinatario',
        queryset=Destinatario.objects.none(), # Se setea en la vista
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    estado = forms.ChoiceField(
        label='Estado del Préstamo',
        choices=[('', 'Todos')] + Prestamo.EstadoPrestamo.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    start_date = forms.DateField(
        label='Fecha Desde',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    end_date = forms.DateField(
        label='Fecha Hasta',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        if estacion:
            # Filtra los destinatarios para mostrar solo los de la estación
            self.fields['destinatario'].queryset = Destinatario.objects.filter(estacion=estacion).order_by('nombre_entidad')