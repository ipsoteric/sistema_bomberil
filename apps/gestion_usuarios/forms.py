from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import Usuario, Rol
from apps.common.mixins import ImageProcessingFormMixin, BomberilFormMixin
from apps.common.form_fields import RutField, NombrePropioField, TelefonoChileField
from apps.common.validators import validar_edad



class FormularioCrearUsuario(BomberilFormMixin, forms.Form):
    rut = RutField() 
    nombre = NombrePropioField(required=True)
    apellido = NombrePropioField(required=True)
    correo = forms.EmailField(
        required=True, 
        widget=forms.EmailInput(attrs={'placeholder': 'ejemplo@bomberos.cl'})
    )
    fecha_nacimiento = forms.DateField(
        required=False,
        validators=[validar_edad], # <--- AQUÍ ESTÁ LA REGLA
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    telefono = TelefonoChileField(required=False)




class FormularioEditarUsuario(BomberilFormMixin, ImageProcessingFormMixin, forms.ModelForm):
    # Campos Especiales (Reutilizamos tu lógica inteligente)
    first_name = NombrePropioField(required=True, label="Nombre")
    last_name = NombrePropioField(required=True, label="Apellido")
    phone = TelefonoChileField(required=False, label="Teléfono")

    # RUT: Solo lectura, visualización simple
    rut = forms.CharField(
        label='RUT',
        required=False,
        widget=forms.TextInput(attrs={
            'readonly': 'readonly',
            'tabindex': '-1',
            'class': 'text-muted' # El Mixin agregará form-control automáticamente
        })
    )

    class Meta:
        model = Usuario
        fields = ['rut', 'email', 'first_name', 'last_name', 'phone', 'birthdate', 'avatar']
        
        widgets = {
            'birthdate': forms.DateInput(attrs={'type': 'date'}),
            # email y avatar son manejados automáticamente por el Mixin
        }

    def __init__(self, *args, **kwargs):
        # 1. Extraemos la instancia antes de iniciar para pre-llenar datos custom
        instance = kwargs.get('instance')
        
        # 2. Inicializamos (El Mixin aquí inyectará estilos y sacará user/estacion)
        super().__init__(*args, **kwargs)
        
        # 3. Lógica específica de este form
        if instance:
            # Pre-llenar RUT visual (que no es parte del form editable)
            self.fields['rut'].initial = instance.rut
            
            # Si el email es vital para el login, a veces se bloquea también. 
            # Si permites editarlo, asegúrate que no choque con otro usuario.

    def clean_email(self):
        # Validación extra: Que el nuevo email no pertenezca a OTRO usuario
        email = self.cleaned_data.get('email')
        if self.instance and email:
            if Usuario.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Este correo electrónico ya está en uso por otro usuario.")
        return email

    def save(self, commit=True):
        usuario = super().save(commit=False)
        
        # Procesamiento de imagen (Avatar)
        self.process_image_upload(
            instance=usuario, 
            field_name='avatar',
            max_dim=(800, 800), # Avatar no necesita ser 4K
            crop=True,          # Avatar cuadrado se ve mejor
            image_prefix='avatar_user'
        )

        if commit:
            usuario.save()
            
        return usuario




# FORMULARIO PARA DJANGO ADMIN
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




# FORMULARIO PARA DJANGO ADMIN
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
        self.fields['nombre'].widget.attrs.update({'class': 'form-control form-control-sm text-base', 'autocomplete': 'off'})
        self.fields['descripcion'].widget.attrs.update({'class': 'form-control form-control-sm text-base', 'autocomplete': 'off', 'rows': 3})


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