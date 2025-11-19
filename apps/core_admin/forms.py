from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.gestion_inventario.models import Estacion, Comuna, ProductoGlobal
from apps.gestion_usuarios.models import Usuario, Rol, Membresia


class EstacionForm(forms.ModelForm):
    class Meta:
        model = Estacion
        fields = ['nombre', 'descripcion', 'es_departamento', 'direccion', 'comuna', 'logo', 'imagen']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'es_departamento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Aplicar clases de Bootstrap a todos los campos visibles
        for field_name, field in self.fields.items():
            if field_name != 'es_departamento': # El checkbox tiene su propia clase
                field.widget.attrs['class'] = 'form-control'
        
        # 2. Optimizar el selector de Comunas (ordenar y mostrar región)
        # [cite_start]Esto evita que salgan desordenadas. [cite: 11]
        self.fields['comuna'].queryset = Comuna.objects.select_related('region').order_by('region__nombre', 'nombre')
        
        # 3. Etiquetas personalizadas si hacen falta
        self.fields['comuna'].empty_label = "Seleccione una Comuna..."




class ProductoGlobalForm(forms.ModelForm):
    class Meta:
        model = ProductoGlobal
        fields = [
            'nombre_oficial', 'categoria', 'marca', 'modelo', 
            'gtin', 'vida_util_recomendada_anos', 'descripcion_general', 'imagen'
        ]
        widgets = {
            'descripcion_general': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describa las características técnicas principales...'}),
            'nombre_oficial': forms.TextInput(attrs={'placeholder': 'Ej: Hacha de Bombero Flathead'}),
            'modelo': forms.TextInput(attrs={'placeholder': 'Ej: G1, 4.5, AirPak...'}),
            'gtin': forms.TextInput(attrs={'placeholder': 'Código de barras / EAN'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Aplicar estilos Bootstrap a todos los campos
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

        # Mejorar la UX de los selectores
        self.fields['categoria'].empty_label = "Seleccione Categoría..."
        self.fields['marca'].empty_label = "Sin Marca (Genérico)"
        
        # Etiquetas más claras para el admin
        self.fields['vida_util_recomendada_anos'].label = "Vida Útil Estándar (Años)"




class UsuarioCreationForm(forms.ModelForm):
    """
    Formulario para crear usuarios nuevos con validación de contraseña.
    """
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
        help_text="Mínimo 8 caracteres."
    )
    password_confirm = forms.CharField(
        label="Confirmar Contraseña",
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'})
    )

    class Meta:
        model = Usuario
        fields = ['rut', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'is_staff']
        widgets = {
            'rut': forms.TextInput(attrs={'placeholder': '12.345.678-9'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'Ej: Juan'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Ej: Pérez'}),
            'email': forms.EmailInput(attrs={'placeholder': 'juan.perez@bomberos.cl'}),
            'phone': forms.TextInput(attrs={'placeholder': '9 1234 5678'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'rut': 'RUT (Identificador)',
            'is_active': 'Cuenta Activa',
            'is_staff': 'Es Staff (Acceso Admin)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estilos Bootstrap generales
        for field_name, field in self.fields.items():
            if field_name not in ['is_active', 'is_staff']: # Checkboxes tienen su propia clase
                field.widget.attrs['class'] = 'form-control'

    def clean_rut(self):
        # Normalizar RUT (opcional: quitar puntos y guion si tu lógica lo requiere)
        rut = self.cleaned_data.get('rut')
        if Usuario.objects.filter(rut=rut).exists():
            raise ValidationError("Ya existe un usuario registrado con este RUT.")
        return rut

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Las contraseñas no coinciden.")
        
        return cleaned_data

    def save(self, commit=True):
        # Interceptamos el guardado para hashear la contraseña
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user




class UsuarioChangeForm(forms.ModelForm):
    """
    Formulario para EDITAR usuarios existentes.
    No maneja contraseñas, pero permite gestionar permisos sensibles.
    """
    class Meta:
        model = Usuario
        fields = ['rut', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'is_staff', 'is_superuser']
        widgets = {
            'rut': forms.TextInput(attrs={'readonly': 'readonly'}), # El RUT suele ser inmutable, o editable con cuidado
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Estilos Bootstrap
        for field_name, field in self.fields.items():
            if field_name not in ['is_active', 'is_staff', 'is_superuser']:
                field.widget.attrs['class'] = 'form-control'

        # Validar si el usuario que edita se está editando a sí mismo (para evitar auto-bloqueos)
        # Esto se maneja mejor en la vista, pero aquí podemos poner warnings en los help_text
        self.fields['is_superuser'].help_text = "<strong>¡Cuidado!</strong> Otorga acceso total al sistema y evita todas las restricciones de permisos."
        self.fields['rut'].help_text = "El identificador (RUT) no se puede modificar libremente para mantener la integridad histórica."




class AsignarMembresiaForm(forms.ModelForm):
    # Campo extra para seleccionar roles (M2M) en el formulario
    roles_seleccionados = forms.ModelMultipleChoiceField(
        queryset=Rol.objects.none(), # Se poblará dinámicamente
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '8'}),
        label="Roles a Asignar",
        help_text="Mantén presionada la tecla Ctrl (o Cmd) para seleccionar múltiples roles."
    )

    class Meta:
        model = Membresia
        fields = ['usuario', 'estacion', 'fecha_inicio']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'usuario': forms.Select(attrs={'class': 'form-select'}),
            'estacion': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si hay datos (POST), cargamos los roles válidos para validar la entrada
        if 'estacion' in self.data:
            try:
                estacion_id = int(self.data.get('estacion'))
                self.fields['roles_seleccionados'].queryset = Rol.objects.filter(
                    Q(estacion__isnull=True) | Q(estacion_id=estacion_id)
                )
            except (ValueError, TypeError):
                pass  # Entrada inválida, el clean lo manejará
        elif self.instance.pk:
            # Lógica para edición (si quisieras reutilizarlo)
            self.fields['roles_seleccionados'].queryset = self.instance.estacion.roles.all() # Simplificado

    def clean(self):
        cleaned_data = super().clean()
        usuario = cleaned_data.get('usuario')
        
        # --- VALIDACIÓN BLOQUEANTE ---
        if usuario:
            # Buscamos si tiene CUALQUIER membresía activa
            # Usamos .exclude(pk=self.instance.pk) por si en el futuro usas esto para editar
            otras_activas = Membresia.objects.filter(
                usuario=usuario, 
                estado='ACTIVO'
            ).exclude(pk=self.instance.pk)

            if otras_activas.exists():
                # Obtenemos la estación actual para dar un mensaje claro
                estacion_actual = otras_activas.first().estacion.nombre
                
                raise ValidationError(
                    f"OPERACIÓN DENEGADA: El usuario {usuario} ya se encuentra ACTIVO en la estación '{estacion_actual}'. "
                    "Debe finalizar esa membresía antes de asignarle una nueva."
                )
        
        return cleaned_data