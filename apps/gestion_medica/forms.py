from django import forms
# Importamos TODOS los modelos necesarios UNA SOLA VEZ aquí arriba
from .models import (
    FichaMedica, 
    ContactoEmergencia, 
    FichaMedicaAlergia, 
    FichaMedicaEnfermedad, 
    FichaMedicaMedicamento, 
    FichaMedicaCirugia,
    Medicamento,
    Alergia,
    Cirugia,
    Enfermedad
)

OPCIONES_UNIDADES = [
    ('mg', 'mg (Miligramos)'),
    ('ml', 'ml (Mililitros)'),
    ('gr', 'gr (Gramos)'),
    ('mcg', 'mcg (Microgramos)'),
    ('g/ml', 'g/ml'),
    ('mg/ml', 'mg/ml'),
    ('ui', 'UI (Unidades Int.)'),
    ('%', '% (Porcentaje)'),
    ('puff', 'Puff/Inhalación'),
    ('comp', 'Comprimido(s)'),
    ('cap', 'Cápsula(s)'),
    ('gotas', 'Gotas'),
    ('amp', 'Ampolla'),
    ('unid', 'Unidad(es)'),
]

# ==============================================================================
# 1. FORMULARIOS DE ENTIDAD (FICHA MÉDICA PRINCIPAL y CONTACTOS)
# ==============================================================================

class FichaMedicaForm(forms.ModelForm):
    """1. Formulario de la Ficha Principal (Datos Fisiológicos, Grupos Sanguíneos)"""
    class Meta:
        model = FichaMedica
        fields = [
            'peso_kg', 'altura_mts', 'presion_arterial_sistolica',
            'presion_arterial_diastolica', 'grupo_sanguineo', 
            'sistema_salud', 'observaciones_generales',
        ]
        widgets = {
            'peso_kg': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 75.5'}),
            'altura_mts': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1.78'}),
            'presion_arterial_sistolica': forms.NumberInput(attrs={'class': 'form-control'}),
            'presion_arterial_diastolica': forms.NumberInput(attrs={'class': 'form-control'}),
            'grupo_sanguineo': forms.Select(attrs={'class': 'form-select'}),
            'sistema_salud': forms.Select(attrs={'class': 'form-select'}),
            'observaciones_generales': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class ContactoEmergenciaForm(forms.ModelForm):
    """2. Formulario de Contactos de Emergencia (incluye validación de teléfono)"""
    def __init__(self, *args, **kwargs):
        # Extraemos el usuario que se pasa desde la vista (si existe)
        self.usuario_dueno = kwargs.pop('usuario_dueno', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = ContactoEmergencia
        fields = ['nombre_completo', 'parentesco', 'telefono']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre completo del contacto'}),
            'parentesco': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Madre, Hermano, Vecino'}),
            # El teléfono lo manejaremos con una clase especial para el JS
            'telefono': forms.TextInput(attrs={
                'class': 'form-control telefono-input', 
                'placeholder': '9 1234 5678',
                'maxlength': '9'
            }),
        }

    def clean_telefono(self):
        """Valida que el teléfono tenga el formato correcto (9 dígitos en Chile)"""
        telefono = self.cleaned_data.get('telefono')
        
        # 1. Limpiar espacios si el usuario los pone
        telefono = telefono.replace(" ", "").strip()

        # 2. Validar que sean solo números
        if not telefono.isdigit():
            raise forms.ValidationError("El teléfono solo debe contener números.")

        # 3. Validar largo (Chile estándar móvil: 9 dígitos)
        if len(telefono) != 9:
            raise forms.ValidationError("El número debe tener 9 dígitos (Ej: 912345678).")

        return telefono

    def clean(self):
        """Validación cruzada: Compara con el número del usuario"""
        cleaned_data = super().clean()
        telefono_emergencia = cleaned_data.get('telefono')

        # Si tenemos al usuario dueño y su teléfono cargado
        if self.usuario_dueno and self.usuario_dueno.phone:
            telefono_usuario = self.usuario_dueno.phone.replace(" ", "").strip()
            
            # 4. Validar que no sea el mismo número
            if telefono_emergencia == telefono_usuario:
                # Agregamos el error al campo específico 'telefono'
                self.add_error('telefono', "El número de emergencia no puede ser el mismo que el del voluntario.")
        
        return cleaned_data


# ==============================================================================
# 2. FORMULARIOS DE RELACIÓN (Asignación de antecedentes al Paciente)
# ==============================================================================

class FichaMedicaAlergiaForm(forms.ModelForm):
    """3. Asignación de Alergias (Relación Many-to-Many)"""
    class Meta:
        model = FichaMedicaAlergia
        fields = ['alergia', 'observaciones']
        widgets = {
            'alergia': forms.Select(attrs={'class': 'form-select select-busqueda', 'placeholder': 'Buscar alergia...'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Reacción grave'}),
        }

class FichaMedicaMedicamentoForm(forms.ModelForm):
    """
    REFACTORIZADO: Formulario optimizado.
    La unidad se obtiene del medicamento padre, no del input del usuario.
    """
    
    # --- 1. CANTIDAD (Solo el número) ---
    cantidad = forms.IntegerField(
        min_value=1, 
        label="Cantidad",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'})
    )
    
    # --- 2. FRECUENCIA ---
    freq_numero = forms.IntegerField(
        min_value=1,
        label="Cada...",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'})
    )

    freq_tiempo = forms.ChoiceField(
        label="Unidad de Tiempo",
        choices=[
            ('horas', 'Horas'), ('dias', 'Días'), ('minutos', 'Minutos'),
            ('semanas', 'Semanas'), ('meses', 'Meses'), ('sos', 'S.O.S'),
        ],
        widget=forms.Select(attrs={'class': 'form-select text-center fw-bold'}) 
    )

    # --- 3. DURACIÓN / NOTAS ---
    duracion = forms.CharField(
        required=False,
        label="Duración / Notas",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: por 7 días / con comidas'})
    )

    class Meta:
        model = FichaMedicaMedicamento
        fields = ['medicamento'] 
        widgets = {
            'medicamento': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Buscar medicamento...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # A) Configuración del Select (Buscador)
        self.fields['medicamento'].queryset = Medicamento.objects.filter(
            concentracion__isnull=False
        ).order_by('nombre')
        self.fields['medicamento'].empty_label = "" # Vital para el placeholder
        
        # B) Lógica de Edición (Recuperar datos al abrir el form)
        if self.instance and self.instance.pk:
            self.fields['medicamento'].disabled = True
            
            # Intentamos parsear el string "500 mg cada 8 horas"
            # Solo nos interesa recuperar la CANTIDAD y la FRECUENCIA.
            # La unidad la ignoramos porque la sacaremos del medicamento padre.
            texto = self.instance.dosis_frecuencia or ""
            try:
                if " cada " in texto:
                    parte_dosis, parte_freq = texto.split(" cada ", 1)
                    
                    # Parsear Cantidad (asumiendo formato "500 mg")
                    d_datos = parte_dosis.split(' ')
                    if len(d_datos) >= 1 and d_datos[0].isdigit():
                        self.fields['cantidad'].initial = d_datos[0]

                    # Parsear Frecuencia
                    f_datos = parte_freq.split(' ', 2)
                    if len(f_datos) >= 2:
                        self.fields['freq_numero'].initial = f_datos[0]
                        self.fields['freq_tiempo'].initial = f_datos[1]
                        if len(f_datos) > 2:
                            self.fields['duracion'].initial = f_datos[2].replace('(', '').replace(')', '')
                else:
                    self.fields['duracion'].initial = texto
            except:
                self.fields['duracion'].initial = texto

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # --- LÓGICA NUEVA ---
        # 1. Obtenemos el medicamento limpio
        med = self.cleaned_data.get('medicamento')
        
        # 2. Obtenemos la unidad DIRECTAMENTE de la base de datos (Medicamento)
        #    Esto evita cualquier manipulación o error del frontend.
        unidad_real = med.unidad if med else ""

        # 3. Obtenemos los datos del formulario
        c = self.cleaned_data.get('cantidad')
        fn = self.cleaned_data.get('freq_numero')
        ft = self.cleaned_data.get('freq_tiempo')
        dur = self.cleaned_data.get('duracion')

        # 4. Construimos el string final
        # Formato: "500 mg cada 8 horas"
        frecuencia_str = "S.O.S" if ft == 'sos' else f"cada {fn} {ft}"
        
        final_str = f"{c} {unidad_real} {frecuencia_str}"
        
        if dur:
            final_str += f" ({dur})"
        
        instance.dosis_frecuencia = final_str
        
        if commit:
            instance.save()
        return instance
    
class FichaMedicaEnfermedadForm(forms.ModelForm):
    """5. Asignación de Enfermedades (Relación Many-to-Many)"""
    class Meta:
        model = FichaMedicaEnfermedad
        fields = ['enfermedad', 'observaciones']
        widgets = {
            'enfermedad': forms.Select(attrs={'class': 'form-select select-busqueda', 'placeholder': 'Buscar enfermedad...'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: En tratamiento...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si la instancia ya tiene un ID (es decir, estamos editando un registro existente)
        if self.instance and self.instance.pk:
            # Deshabilitamos el campo enfermedad
            self.fields['enfermedad'].disabled = True
            # Opcional: Añadimos un estilo visual para que se note bloqueado
            self.fields['enfermedad'].widget.attrs['class'] += ' bg-light'

class FichaMedicaCirugiaForm(forms.ModelForm):
    """6. Asignación de Cirugías (Relación Many-to-Many)"""
    class Meta:
        model = FichaMedicaCirugia
        fields = ['cirugia', 'fecha_cirugia', 'observaciones']
        widgets = {
            'cirugia': forms.Select(attrs={'class': 'form-select select-busqueda', 'placeholder': 'Buscar cirugía...'}),
            'fecha_cirugia': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Detalles...'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando, bloqueamos el tipo de cirugía
        if self.instance and self.instance.pk:
            self.fields['cirugia'].disabled = True
            self.fields['cirugia'].widget.attrs['class'] += ' bg-light'


# ==============================================================================
# 3. FORMULARIOS DE CATÁLOGO (Mantenedores Globales)
# ==============================================================================

class MedicamentoForm(forms.ModelForm):
    """
    Formulario para CREAR/EDITAR Medicamentos.
    """
    class Meta:
        model = Medicamento
        fields = ['nombre', 'concentracion', 'unidad', 'clasificacion_riesgo']
        
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Ej: Paracetamol'
            }),
            'concentracion': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '500',
                'min': '1'
            }),
            'unidad': forms.Select(attrs={
                'class': 'form-select text-center fw-bold'
            }),
            'clasificacion_riesgo': forms.Select(attrs={
                'class': 'form-select fw-bold text-dark border-warning'
            })
        }
        
        labels = {
            'nombre': 'Nombre del Fármaco',
            'clasificacion_riesgo': 'Alerta de Riesgo (Opcional)'
        }

    def clean(self):
        cleaned_data = super().clean()
        
        # Obtenemos los datos limpios
        nombre_input = cleaned_data.get('nombre')
        conc = cleaned_data.get('concentracion')
        unit = cleaned_data.get('unidad')
        riesgo = cleaned_data.get('clasificacion_riesgo')

        if nombre_input:
            # LÓGICA CORREGIDA:
            # Buscamos si existe un registro con ESTA EXACTA COMBINACIÓN.
            # No concatenamos strings para buscar, usamos los campos atómicos.
            
            qs = Medicamento.objects.filter(
                nombre__iexact=nombre_input.strip(),
                concentracion=conc,
                unidad=unit,
                clasificacion_riesgo=riesgo
            )

            # Excluir al propio objeto si estamos editando
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                # Construimos el string solo para mostrar el mensaje de error bonito
                nombre_mostrar = f"{nombre_input} {conc if conc else ''} {unit}".strip()
                if riesgo:
                    nombre_mostrar += f" [{riesgo}]"
                
                raise forms.ValidationError(
                    f"El medicamento '{nombre_mostrar}' ya existe en el catálogo."
                )
        
        return cleaned_data
        

class AlergiaForm(forms.ModelForm):
    """8. Formulario para CREAR/EDITAR Alergias (Catálogo Global)"""
    class Meta:
        model = Alergia
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Penicilina'}),
        }

class EnfermedadForm(forms.ModelForm):
    """9. Formulario para CREAR/EDITAR Enfermedades (Catálogo Global)"""
    class Meta:
        model = Enfermedad
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Diabetes Tipo 2'}),
        }

class CirugiaForm(forms.ModelForm):
    """10. Formulario para CREAR/EDITAR Cirugías (Catálogo Global)"""
    class Meta:
        model = Cirugia
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Apendicectomía'}),
        }