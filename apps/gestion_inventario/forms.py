import os
import uuid

from django import forms
from django.utils import timezone
from django.db.models import Q
from PIL import Image
from .models import (
    Region,
    Comuna,
    TipoEstado,
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
from apps.common.utils import procesar_imagen_en_memoria, generar_thumbnail_en_memoria
from apps.common.mixins import ImageProcessingFormMixin


class AreaForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        # tipo_seccion y estacion no se exponen: tipo_seccion será 'AREA' y estacion se asigna desde la sesión
        # La imagen no se puede subir en la creación; sólo al editar
        fields = ['nombre', 'descripcion', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control form-control-sm text-base color_primario fondo_secundario', 
                'placeholder': 'Nombre del almacén'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control form-control-sm text-base color_primario fondo_secundario', 
                'rows': 3
            }),
            'direccion': forms.TextInput(attrs={
                'class': 'form-control form-control-sm text-base color_primario fondo_secundario', 
                'placeholder': 'Dirección (opcional)'
            }),
        }




class AreaEditForm(ImageProcessingFormMixin, forms.ModelForm):
    class Meta:
        model = Ubicacion
        fields = ['nombre', 'descripcion', 'direccion', 'imagen']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 3}),
            'direccion': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
            'imagen': forms.FileInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
        }

    def save(self, commit=True):
        area = super().save(commit=False)
        self.process_image_upload(instance=area, field_name='imagen', max_dim=(1024, 1024), crop=False, image_prefix='area')
        if commit:
            area.save()
        return area




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
                'class': 'form-control form-control-sm text-base color_primario fondo_secundario', 
                'placeholder': 'Nombre (Ej: "B-1", "Carro 1")'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control form-control-sm text-base color_primario fondo_secundario', 
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
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 3}),
            'imagen': forms.FileInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
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
            'tipo_vehiculo': forms.Select(attrs={'class': 'form-select form-select-sm text-base color_primario fondo_secundario_variante border-0 tom-select-basic'}),
            'patente': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
            'marca': forms.Select(attrs={'class': 'form-select form-select-sm text-base color_primario fondo_secundario_variante border-0 tom-select-creatable'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
            'anho': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'placeholder': 'Ej: 2023'}),
            'chasis': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Poblamos los QuerySets de los campos ForeignKey para que estén ordenados.
        """
        super().__init__(*args, **kwargs)
        self.fields['tipo_vehiculo'].queryset = TipoVehiculo.objects.order_by('nombre')
        self.fields['marca'].queryset = Marca.objects.order_by('nombre')
        
        # Textos legibles para selects
        self.fields['tipo_vehiculo'].empty_label = "Seleccione Tipo de Vehículo..."
        self.fields['marca'].empty_label = "Seleccione Marca..."




class CompartimentoForm(forms.ModelForm):
    class Meta:
        model = Compartimento
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'placeholder': 'Nombre del compartimento'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 3}),
        }




class CompartimentoEditForm(ImageProcessingFormMixin, forms.ModelForm):
    """
    Formulario para editar los detalles de un compartimento.
    No permite cambiar la ubicación (Ubicacion) a la que pertenece.
    """
    class Meta:
        model = Compartimento
        fields = ['nombre', 'descripcion', 'imagen']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 4}),
            'imagen': forms.FileInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'}),
        }

    def save(self, commit=True):
        compartimento = super().save(commit=False)
        self.process_image_upload(instance=compartimento, field_name='imagen', max_dim=(1024, 1024), crop=False, image_prefix='compartimento')
        if commit:
            compartimento.save()
        return compartimento




class ProductoGlobalForm(ImageProcessingFormMixin, forms.ModelForm):
    """
    Formulario para la creación de un nuevo Producto Global.
    La validación de marca/modelo vs. genérico se hereda del método .clean()
    que ya definimos en el modelo.
    """
    class Meta:
        model = ProductoGlobal
        fields = [
            'nombre_oficial', 'marca', 'modelo', 'categoria', 
            'descripcion_general', 'vida_util_recomendada_anos', 'imagen'
        ]
        widgets = {
            'nombre_oficial': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'marca': forms.Select(attrs={'class': 'form-select form-select-sm text-base fondo_secundario color_primario tom-select-creatable'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'categoria': forms.Select(attrs={'class': 'form-select form-select-sm text-base fondo_secundario color_primario'}),
            'descripcion_general': forms.Textarea(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario', 'rows': 3}),
            'vida_util_recomendada_anos': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
        }
        help_texts = {
            'nombre_oficial': 'Para productos genéricos, usa un nombre descriptivo. Ej: "Guantes Nitrilo".',
            'modelo': 'Si seleccionaste una marca, este campo es obligatorio.',
        }

    def __init__(self, *args, **kwargs):
        """
        Poblamos los QuerySets de los campos ForeignKey para que estén ordenados.
        """
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = Categoria.objects.order_by('nombre')
        self.fields['marca'].queryset = Marca.objects.order_by('nombre')
        
        # Textos legibles
        self.fields['categoria'].empty_label = "Seleccione Categoría..."
        self.fields['marca'].empty_label = "Seleccione Marca..."

    def save(self, commit=True):
        producto = super().save(commit=False)
        # 2. USAR EL MIXIN
        # Para productos: NO recortamos a cuadrado (crop=False) 
        # y usamos 1024x1024 o lo que definas.
        self.process_image_upload(instance=producto, field_name='imagen', max_dim=(1024, 1024), crop=False)
        if commit:
            producto.save()
        return producto




class ProductoLocalEditForm(forms.ModelForm):
    """
    Formulario para editar un Producto local (catálogo de la estación).
    Incluye lógica para deshabilitar 'es_serializado' si ya existe inventario.
    """
    class Meta:
        model = Producto
        fields = [
            'sku', 'es_serializado', 'es_expirable', 
            'proveedor_preferido', 'costo_compra',
            'vida_util_estacion_anos', 'stock_critico'
        ]
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'es_serializado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_expirable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'proveedor_preferido': forms.Select(attrs={'class': 'tom-select-basic form-select form-select-sm text-base fondo_secundario color_primario'}),
            'costo_compra': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'vida_util_estacion_anos': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'stock_critico': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-base color_primario'})
        }
        help_texts = {
            'sku': 'Código único interno de tu estación.',
            'es_serializado': 'Marcar si es un Activo rastreable individualmente.',
            'es_expirable': 'Marcar si requiere seguimiento de fecha de expiración.',
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

        if 'proveedor_preferido' in self.fields:
            self.fields['proveedor_preferido'].queryset = Proveedor.objects.all().order_by('nombre')
            #self.fields['proveedor_preferido'].empty_label = "Seleccione un Proveedor (Opcional)..."

        # Deshabilitar 'es_serializado' si se indica (Se mantiene igual)
        if disable_es_serializado and 'es_serializado' in self.fields:
            self.fields['es_serializado'].disabled = True
            self.fields['es_serializado'].help_text += " (No modificable con inventario existente)."

    def clean_es_serializado(self):
        """
        Asegura que si el campo está deshabilitado, no se intente cambiar su valor.
        """
        # Si el campo está deshabilitado, devolvemos el valor original de la instancia
        if self.fields['es_serializado'].disabled:
            return self.instance.es_serializado 
        return self.cleaned_data.get('es_serializado')




class GroupedEstadoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nombre

    def __init__(self, *args, **kwargs):
        tipo_estados = TipoEstado.objects.all().order_by('id')
        choices = [('', 'Todos los Estados')] # Texto legible ya definido
        
        for tipo in tipo_estados:
            estados_en_tipo = [
                (estado.id, self.label_from_instance(estado)) 
                for estado in tipo.estado_set.all().order_by('nombre')
            ]
            if estados_en_tipo:
                choices.append((tipo.nombre.upper(), estados_en_tipo))
                
        kwargs['choices'] = choices
        kwargs['queryset'] = Estado.objects.none()
        super().__init__(*args, **kwargs)




class ProductoStockDetalleFilterForm(forms.Form):
    """
    Formulario para filtrar el stock en la página de detalle del producto.
    """
    estado = forms.ModelChoiceField(
        label='Filtrar por Estado',
        queryset=Estado.objects.all().order_by('tipo_estado__id', 'nombre'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base'})
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop('es_serializado', None)
        super().__init__(*args, **kwargs)
        self.fields['estado'].choices = [('', 'Todos los Estados')] + list(self.fields['estado'].choices)




class ProveedorForm(forms.ModelForm):
    """Formulario para los datos principales del Proveedor."""
    class Meta:
        model = Proveedor
        fields = ['nombre', 'rut']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario'}),
            'rut': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario', 'placeholder': 'Ej: 12345678-9'}),
        }




class ContactoProveedorForm(forms.ModelForm):
    """Formulario para los datos del Contacto (principal o secundario)."""
    # Añadimos un campo para seleccionar la región para el filtro dependiente
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        label="Región",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base color_primario fondo_secundario'})
    )

    class Meta:
        model = ContactoProveedor
        fields = ['nombre_contacto', 'direccion', 'region', 'comuna', 'telefono', 'email', 'notas']
        widgets = {
            'nombre_contacto': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'comuna': forms.Select(attrs={'class': 'form-select form-select-sm text-base fondo_secundario color_primario'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'email': forms.EmailInput(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario'}),
            'notas': forms.Textarea(attrs={'class': 'form-control form-control-sm text-base fondo_secundario color_primario', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos que el queryset de comuna esté vacío al principio. Se llenará con JS.
        self.fields['region'].empty_label = "Seleccione Región..."
        self.fields['comuna'].empty_label = "Seleccione Comuna..."
        self.fields['comuna'].queryset = Comuna.objects.none()

        if 'region' in self.data:
            try:
                region_id = int(self.data.get('region'))
                self.fields['comuna'].queryset = Comuna.objects.filter(region_id=region_id).order_by('nombre')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.comuna:
             self.fields['comuna'].queryset = self.instance.comuna.region.comuna_set.order_by('nombre')




class RecepcionCabeceraForm(forms.Form):
    """ Formulario para los datos generales de la recepción """
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.none(),
        label="Proveedor",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base'})
    )
    fecha_recepcion = forms.DateField(
        label="Fecha de Recepción",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm text-base'}),
    )
    notas = forms.CharField(
        label="Notas Adicionales (Opcional)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm text-base'})
    )

    def __init__(self, *args, **kwargs):
        # Extraemos 'estacion' para evitar errores en super(), aunque ya no filtraremos por ella
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        self.fields['proveedor'].queryset = Proveedor.objects.all().order_by('nombre')
        self.fields['proveedor'].empty_label = "Seleccione Proveedor..."
        self.fields['fecha_recepcion'].initial = timezone.now().date()




class RecepcionDetalleForm(forms.Form):
    """ Formulario para cada línea de producto en la recepción """
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.none(),
        label="Producto",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base producto-select'})
    )
    compartimento_destino = forms.ModelChoiceField(
        queryset=Compartimento.objects.none(),
        label="Destino",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base'})
    )
    # --- Campos Comunes ---
    costo_unitario = forms.DecimalField(
        label="Costo Unit.", required=False, max_digits=10, decimal_places=0,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm text-base', 'step': '1'})
    )

    # Campos Insumos
    cantidad = forms.IntegerField(
        label="Cantidad", min_value=1, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm text-base insumo-field', 'step': '1'})
    )
    numero_lote = forms.CharField(
        label="N° Lote", max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm text-base insumo-field'})
    )
    fecha_vencimiento = forms.DateField(
        label="Fecha de Vencimiento", required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm text-base insumo-field'})
    )
    
    # Campos Activos
    numero_serie = forms.CharField(
        label="N° Serie Fab.", max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm text-base activo-field'})
    )
    fecha_fabricacion = forms.DateField(
        label="Fecha de Fabricación", required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm text-base activo-field'})
    )

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)

        if estacion:
            self.fields['producto'].queryset = Producto.objects.filter(estacion=estacion).select_related('producto_global')
            self.fields['compartimento_destino'].queryset = Compartimento.objects.filter(ubicacion__estacion=estacion).select_related('ubicacion')

        self.fields['producto'].empty_label = "Seleccione Producto..."
        self.fields['compartimento_destino'].empty_label = "Seleccione Ubicación..."

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
                cleaned_data['cantidad'] = 1
                cleaned_data['numero_lote'] = None
                cleaned_data['fecha_vencimiento'] = None
            else:
                # Para Insumos, Cantidad es requerida
                if not cleaned_data.get('cantidad'):
                    self.add_error('cantidad', 'La cantidad es requerida para insumos.')
                # Fecha vencimiento puede ser requerida si el producto es expirable
                if producto.es_expirable and not cleaned_data.get('fecha_vencimiento'):
                     self.add_error('fecha_vencimiento', 'La fecha de vencimiento es requerida.')
                cleaned_data['numero_serie'] = None
                cleaned_data['fecha_fabricacion'] = None
        return cleaned_data

RecepcionDetalleFormSet = forms.formset_factory(RecepcionDetalleForm, extra=1, can_delete=True)




class ActivoSimpleCreateForm(forms.ModelForm):
    """
    Formulario rápido para crear un Activo y asignarlo a un compartimento.
    """
    def __init__(self, *args, **kwargs):
        estacion_id = kwargs.pop('estacion_id', None)
        super().__init__(*args, **kwargs)

        if estacion_id:
            self.fields['producto'].queryset = Producto.objects.filter(estacion_id=estacion_id, es_serializado=True).select_related('producto_global')
            self.fields['proveedor'].queryset = Proveedor.objects.filter(estacion_creadora=estacion_id).order_by('nombre')
        
        if 'compartimento' in self.fields:
            self.fields['compartimento'].widget = forms.HiddenInput()
        if 'fecha_recepcion' in self.fields:
            self.fields['fecha_recepcion'].initial = timezone.now().date()
        
        # Textos legibles
        self.fields['producto'].empty_label = "Seleccione Producto..."
        self.fields['proveedor'].empty_label = "Seleccione Proveedor..."

        # Estilos
        css_class = 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'
        css_class_select = 'form-select form-select-sm text-base color_primario fondo_secundario_variante border-0'
        
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
        fields = ['producto', 'compartimento', 'proveedor', 'numero_serie_fabricante', 'fecha_recepcion', 'fecha_fabricacion', 'fecha_expiracion', 'notas_adicionales']




class LoteInsumoSimpleCreateForm(forms.ModelForm):
    """
    Formulario rápido para crear un Lote de Insumo y asignarlo a un compartimento.
    """
    def __init__(self, *args, **kwargs):
        estacion_id = kwargs.pop('estacion_id', None)
        super().__init__(*args, **kwargs)

        if estacion_id:
            self.fields['producto'].queryset = Producto.objects.filter(estacion_id=estacion_id, es_serializado=False).select_related('producto_global')

        if 'compartimento' in self.fields:
            self.fields['compartimento'].widget = forms.HiddenInput()
        if 'fecha_recepcion' in self.fields:
            self.fields['fecha_recepcion'].initial = timezone.now().date()

        self.fields['producto'].empty_label = "Seleccione Producto..."

        css_class = 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'
        css_class_select = 'form-select form-select-sm text-base color_primario fondo_secundario_variante border-0'

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
        fields = ['producto', 'compartimento', 'cantidad', 'numero_lote_fabricante', 'fecha_recepcion', 'fecha_expiracion']




class LoteAjusteForm(forms.Form):
    """
    Formulario para ajustar la cantidad de un lote y registrar el motivo.
    """
    nueva_cantidad_fisica = forms.IntegerField(
        label="Nueva Cantidad Física", min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm text-xl text-center fw-bold', 'style': 'max-width: 200px; margin: 0 auto;'})
    )
    notas = forms.CharField(
        label="Motivo del Ajuste (Obligatorio)", required=True,
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 3, 'placeholder': 'Ej: Conteo físico 04/11/2025, se encontraron 2 unidades rotas.'})
    )




class MovimientoFilterForm(forms.Form):
    q = forms.CharField(
        label="Buscar", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm text-base', 'placeholder': 'Producto, SKU, Lote, Notas...'})
    )
    tipo_movimiento = forms.ChoiceField(
        label="Tipo de Movimiento", required=False,
        choices=[('', 'Todos los Tipos')] + TipoMovimiento.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base'})
    )
    usuario = forms.ModelChoiceField(
        label="Usuario", required=False, queryset=Usuario.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base'})
    )
    fecha_inicio = forms.DateField(
        label="Desde", required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm text-base'})
    )
    fecha_fin = forms.DateField(
        label="Hasta", required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm text-base'})
    )

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        self.fields['usuario'].empty_label = "Todos los Usuarios"
        if estacion:
            self.fields['usuario'].queryset = Usuario.objects.filter(membresias__estacion=estacion).order_by('first_name').distinct()




class BajaExistenciaForm(forms.Form):
    """
    Formulario para registrar el motivo al dar de baja una existencia.
    """
    notas = forms.CharField(
        label="Motivo de la Baja (Obligatorio)", required=True,
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 3, 'placeholder': 'Ej: Fin de vida útil, casco roto en emergencia, lote vencido.'})
    )




class ExtraviadoExistenciaForm(forms.Form):
    """
    Formulario para registrar el motivo al reportar una existencia como extraviada.
    """
    notas = forms.CharField(
        label="Notas (Obligatorio)", required=True,
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 3, 'placeholder': 'Ej: No encontrado durante el inventario físico.'})
    )




class LoteConsumirForm(forms.Form):
    """
    Formulario para consumir una cantidad específica de un lote.
    """
    cantidad_a_consumir = forms.IntegerField(
        label="Cantidad a Consumir", min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm text-xl text-center fw-bold', 'style': 'max-width: 200px; margin: 0 auto;'})
    )
    notas = forms.CharField(
        label="Motivo del Consumo (Obligatorio)", required=True,
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 3, 'placeholder': 'Ej: Usado en emergencia.'})
    )

    def __init__(self, *args, **kwargs):
        self.lote = kwargs.pop('lote', None)
        super().__init__(*args, **kwargs)

    def clean_cantidad_a_consumir(self):
        """
        Valida que la cantidad a consumir no sea mayor
        que la cantidad disponible en el lote.
        """
        cantidad = self.cleaned_data.get('cantidad_a_consumir')
        if self.lote and cantidad > self.lote.cantidad:
            raise forms.ValidationError(f"No se puede consumir más de la cantidad disponible ({self.lote.cantidad}).")
        return cantidad




class TransferenciaForm(forms.Form):
    """
    Formulario para transferir una existencia (Activo o Lote)
    a un nuevo compartimento.
    """
    compartimento_destino = forms.ModelChoiceField(
        queryset=Compartimento.objects.none(),
        label="Compartimento de Destino",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base color_primario fondo_secundario_variante border-0 tom-select-basic'})
    )
    cantidad = forms.IntegerField(
        label="Cantidad a Mover", min_value=1, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'})
    )
    notas = forms.CharField(
        label="Notas (Opcional)", required=False,
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 'rows': 3, 'placeholder': 'Ej: Préstamo a B-2.'})
    )

    def __init__(self, *args, **kwargs):
        self.item = kwargs.pop('item', None)
        self.estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)

        self.fields['compartimento_destino'].empty_label = "Seleccione Destino..."

        if self.estacion and self.item:
            self.fields['compartimento_destino'].queryset = Compartimento.objects.filter(
                ubicacion__estacion=self.estacion
            ).exclude(id=self.item.compartimento.id).select_related('ubicacion').order_by('ubicacion__nombre', 'nombre')

        # Si el ítem es un Activo, ocultamos y deshabilitamos 'cantidad'
        if self.item and self.item.producto.es_serializado:
            self.fields['cantidad'].widget = forms.HiddenInput()
            self.fields['cantidad'].disabled = True
        else:
            self.fields['cantidad'].required = True

    def clean_cantidad(self):
        """
        Valida que la cantidad a mover no sea mayor que la disponible.
        """
        # Solo validamos si es un Lote
        if self.item and not self.item.producto.es_serializado:
            cantidad_a_mover = self.cleaned_data.get('cantidad')
            if cantidad_a_mover > self.item.cantidad:
                raise forms.ValidationError(f"No se puede mover más de la cantidad disponible ({self.item.cantidad}).")
            return cantidad_a_mover
        # Si es un Activo, la cantidad será 1 (manejada en la vista)
        return self.cleaned_data.get('cantidad')




class RegistroUsoForm(forms.Form):
    """
    Formulario para registrar uso con desglose amigable de Horas y Minutos.
    Convierte internamente a decimal para la BD.
    """
    fecha_uso = forms.DateTimeField(
        label="Fecha y Hora del Uso",
        required=True,
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local', 
            'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0'
        })
    )
    
    # Campos separados para mejor UX
    horas_enteras = forms.IntegerField(
        label="Horas",
        min_value=0,
        initial=0,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg text-center fw-bold text-primary border-0', 
            'placeholder': '00',
            'style': 'font-size: 2rem;'
        })
    )
    
    minutos = forms.IntegerField(
        label="Minutos",
        min_value=0,
        max_value=59,
        initial=0,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg text-center fw-bold text-primary border-0', 
            'placeholder': '00',
            'style': 'font-size: 2rem;'
        })
    )

    notas = forms.CharField(
        label="Detalles / Observaciones (Opcional)",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control form-control-sm text-base color_primario fondo_secundario_variante border-0', 
            'rows': 3, 
            'placeholder': 'Ej: Práctica de incendio estructural...'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_uso'].initial = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        """
        Convierte las horas y minutos a formato decimal para compatibilidad con el modelo.
        """
        cleaned_data = super().clean()
        horas = cleaned_data.get('horas_enteras', 0)
        minutos = cleaned_data.get('minutos', 0)

        if horas == 0 and minutos == 0:
            raise forms.ValidationError("Debe registrar al menos 1 minuto de uso.")

        # Conversión a Decimal: Horas + (Minutos / 60)
        total_decimal = float(horas) + (float(minutos) / 60.0)
        
        # Inyectamos 'horas' en cleaned_data para que la Vista lo encuentre como si fuera el campo original
        cleaned_data['horas'] = round(total_decimal, 2)
        
        return cleaned_data




class EtiquetaFilterForm(forms.Form):
    """Formulario utilizado para imprimir etiquetas QR"""
    ubicacion = forms.ModelChoiceField(
        label="Filtrar por Ubicación", required=False, queryset=Ubicacion.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base'})
    )

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        self.fields['ubicacion'].empty_label = "Todas las Ubicaciones"
        if estacion:
            # Filtramos para mostrar solo ubicaciones operativas (no 'ADMINISTRATIVA')
            self.fields['ubicacion'].queryset = Ubicacion.objects.filter(estacion=estacion).exclude(tipo_ubicacion__nombre='ADMINISTRATIVA').order_by('nombre')




class PrestamoCabeceraForm(forms.ModelForm):
    """ Formulario para los datos generales del préstamo """
    nuevo_destinatario_nombre = forms.CharField(
        label="O crear nuevo destinatario", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm text-base', 'placeholder': 'Nombre (Ej: Clínica XYZ)'})
    )
    nuevo_destinatario_contacto = forms.CharField(
        label="Contacto (Opcional)", required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm text-base', 'placeholder': 'Persona/Teléfono'})
    )

    class Meta:
        model = Prestamo
        fields = ['destinatario', 'fecha_devolucion_esperada', 'notas_prestamo', 'nuevo_destinatario_nombre', 'nuevo_destinatario_contacto']
        widgets = {
            'destinatario': forms.Select(attrs={'class': 'form-select form-select-sm text-base tom-select-basic'}),
            'fecha_devolucion_esperada': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm text-base'}),
            'notas_prestamo': forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm text-base'}),
        }

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        if estacion:
            self.fields['destinatario'].queryset = Destinatario.objects.filter(estacion=estacion).order_by('nombre_entidad')
            self.fields['destinatario'].required = False
            self.fields['destinatario'].empty_label = "Seleccione Destinatario..."

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
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.none(), label="Producto",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base producto-select'})
    )
    activo = forms.ModelChoiceField(
        queryset=Activo.objects.none(), label="ID Activo", required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base activo-select'})
    )
    lote = forms.ModelChoiceField(
        queryset=LoteInsumo.objects.none(), label="Lote", required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base lote-select'})
    )
    cantidad = forms.IntegerField(
        label="Cantidad", min_value=1, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm text-base cantidad-input'})
    )

    def __init__(self, *args, **kwargs):
        self.estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        
        # Textos legibles
        self.fields['producto'].empty_label = "Seleccione Producto..."
        self.fields['activo'].empty_label = "Seleccione Activo..."
        self.fields['lote'].empty_label = "Seleccione Lote..."

        if self.estacion:
            # Filtra solo productos que TIENEN stock disponible
            productos_con_stock = Producto.objects.filter(
                Q(estacion=self.estacion) &
                (Q(activo__estado__nombre='DISPONIBLE') | Q(loteinsumo__estado__nombre='DISPONIBLE', loteinsumo__cantidad__gt=0))
            ).distinct().select_related('producto_global')
            
            self.fields['producto'].queryset = productos_con_stock
            self.fields['producto'].label_from_instance = lambda obj: f"{obj.producto_global.nombre_oficial} ({'Activo' if obj.es_serializado else 'Insumo'})"

    def clean(self):
        cleaned_data = super().clean()
        producto = cleaned_data.get('producto')
        if not producto:
            return cleaned_data

        if producto.es_serializado:
            activo = cleaned_data.get('activo')
            if not activo:
                self.add_error('activo', "Debe seleccionar un Activo específico.")
            cleaned_data['lote'] = None
            cleaned_data['cantidad'] = 1
        else:
            lote = cleaned_data.get('lote')
            cantidad = cleaned_data.get('cantidad')
            if not lote:
                self.add_error('lote', "Debe seleccionar un Lote disponible.")
            if not cantidad:
                self.add_error('cantidad', "Debe ingresar una cantidad.")
            if lote and cantidad and cantidad > lote.cantidad:
                self.add_error('cantidad', f"No puede prestar más de {lote.cantidad} (stock actual del lote).")
            cleaned_data['activo'] = None
        return cleaned_data

PrestamoDetalleFormSet = forms.formset_factory(PrestamoDetalleForm, extra=1, can_delete=True)




class PrestamoFilterForm(forms.Form):
    """
    Formulario para filtrar el historial de préstamos.
    """
    destinatario = forms.ModelChoiceField(
        label='Destinatario', queryset=Destinatario.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base'})
    )
    estado = forms.ChoiceField(
        label='Estado del Préstamo',
        choices=[('', 'Todos los Estados')] + Prestamo.EstadoPrestamo.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm text-base'})
    )
    start_date = forms.DateField(
        label='Fecha Desde', required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm text-base', 'type': 'date'})
    )
    end_date = forms.DateField(
        label='Fecha Hasta', required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm text-base', 'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        estacion = kwargs.pop('estacion', None)
        super().__init__(*args, **kwargs)
        self.fields['destinatario'].empty_label = "Todos los Destinatarios"
        if estacion:
            # Filtra los destinatarios para mostrar solo los de la estación
            self.fields['destinatario'].queryset = Destinatario.objects.filter(estacion=estacion).order_by('nombre_entidad')




class DestinatarioForm(forms.ModelForm):
    """
    Formulario (simplificado) para crear y editar Destinatarios.
    No incluye 'is_active'.
    """
    class Meta:
        model = Destinatario
        fields = ['nombre_entidad', 'rut_entidad', 'nombre_contacto', 'telefono_contacto']
        widgets = {
            'nombre_entidad': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base'}),
            'rut_entidad': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base'}),
            'nombre_contacto': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base'}),
            'telefono_contacto': forms.TextInput(attrs={'class': 'form-control form-control-sm text-base'}),
        }




class DestinatarioFilterForm(forms.Form):
    """
    Formulario (simplificado) para filtrar la lista de Destinatarios.
    Solo busca por texto.
    """
    q = forms.CharField(
        label='Buscar (Nombre, RUT o Contacto)', required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm text-base', 'placeholder': 'Buscar...'})
    )