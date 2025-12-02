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
    """4. Asignación de Medicamentos (Con Dosis Estructurada y Buscador)"""
    
    # --- Campos Virtuales (No existen en BD, solo en interfaz) ---
    cantidad = forms.IntegerField(
        min_value=1, 
        label="Cantidad",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'})
    )
    
    # Este es el campo que el JavaScript modificará automáticamente
    # En apps/gestion_medica/forms.py

    unidad = forms.ChoiceField(
        label="Unidad de Medida",
        choices=OPCIONES_UNIDADES, 
        widget=forms.Select(attrs={'class': 'form-select text-center fw-bold select-sin-flecha'})
    )
    
    # --- 2. FRECUENCIA (NUEVO CAMBIO) ---
    freq_numero = forms.IntegerField(
        min_value=1,
        label="Cada...",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'})
    )

    freq_tiempo = forms.ChoiceField(
        label="Unidad de Tiempo",
        choices=[
            ('horas', 'Horas'),
            ('dias', 'Días'),
            ('minutos', 'Minutos'),
            ('semanas', 'Semanas'),
            ('meses', 'Meses'),
            ('sos', 'S.O.S (Según necesidad)'),
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
        fields = ['medicamento'] # 'dosis_frecuencia' se construye internamente
        widgets = {
            'medicamento': forms.Select(attrs={
                'class': 'form-select select-busqueda', # CLAVE para el buscador
                'placeholder': 'Buscar medicamento...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Si estamos editando, bloqueamos el medicamento
        if self.instance and self.instance.pk:
            self.fields['medicamento'].disabled = True
            self.fields['medicamento'].widget.attrs['class'] += ' bg-light'
            
            # 2. RECUPERAR DATOS AL EDITAR
            # Intentamos separar el string "500 mg cada 8 horas" en sus partes
            # Formato esperado: "500 mg cada 8 horas (por 7 días)"
            texto = self.instance.dosis_frecuencia or ""
            
            try:
                # 1. Separar Dosis de Frecuencia usando la palabra clave " cada "
                if " cada " in texto:
                    parte_dosis, parte_freq = texto.split(" cada ", 1)
                    
                    # Parsear Dosis "500 mg"
                    d_datos = parte_dosis.split(' ')
                    if len(d_datos) >= 2:
                        self.fields['cantidad'].initial = d_datos[0]
                        self.fields['unidad'].initial = d_datos[1]

                    # Parsear Frecuencia "8 horas (notas)"
                    f_datos = parte_freq.split(' ', 2)
                    if len(f_datos) >= 2:
                        self.fields['freq_numero'].initial = f_datos[0]
                        self.fields['freq_tiempo'].initial = f_datos[1]
                        
                        # Si sobran cosas (notas/duración)
                        if len(f_datos) > 2:
                            # Limpiar paréntesis si los usamos al guardar
                            self.fields['duracion'].initial = f_datos[2].replace('(', '').replace(')', '')
                else:
                    # Si no cumple el formato nuevo, poner todo en notas para no perderlo
                    self.fields['duracion'].initial = texto
            except:
                self.fields['duracion'].initial = texto

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        c = self.cleaned_data.get('cantidad')
        u = self.cleaned_data.get('unidad')
        f = self.cleaned_data.get('frecuencia')

        # Formato final en BD: "500 mg cada 8 horas"
        # Ajustamos para evitar "None" si algún campo está vacío
        c_str = str(c) if c else ""
        u_str = str(u) if u else ""
        f_str = f"cada {f}" if f else ""
        
        fn = self.cleaned_data.get('freq_numero')
        ft = self.cleaned_data.get('freq_tiempo')
        dur = self.cleaned_data.get('duracion')
        
        # Caso especial SOS
        frecuencia_str = ""
        if ft == 'sos':
            frecuencia_str = "S.O.S"
        else:
            frecuencia_str = f"cada {fn} {ft}"

        # Construir string final
        # Ej: "500 mg cada 8 horas (por 5 dias)"
        final_str = f"{c} {u} {frecuencia_str}"
        
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
    """7. Formulario para CREAR/EDITAR Medicamentos (Catálogo Global)"""
    # --- Campos para construir el nombre estructurado ---
    nombre_base = forms.CharField(
        label="Nombre del Fármaco",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Paracetamol'})
    )
    
    concentracion = forms.IntegerField(
        label="Concentración",
        min_value=1,
        required=False, # Opcional por si es un jarabe simple
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '500'})
    )
    
    unidad = forms.ChoiceField(
        label="Unidad",
        choices=OPCIONES_UNIDADES,
        widget=forms.Select(attrs={'class': 'form-select text-center fw-bold'})
    )

    # --- CAMPO VIRTUAL DE RIESGO (No existe en BD) ---
    clasificacion_riesgo = forms.ChoiceField(
        label="Clasificación de Riesgo",
        choices=[
            ('', 'Neutro / Sin Alerta'), # Opción vacía por defecto
            ('ANTICOAGULANTE', '🔴 ANTICOAGULANTE (Alto Riesgo Hemorragia)'),
            ('COAGULANTE', '🔵 COAGULANTE / HEMOSTÁTICO'),
            ('ANTIPLAQUETARIO', '🟡 ANTIPLAQUETARIO (Aspirina, Clopidogrel)'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select fw-bold text-dark border-warning'})
    )

    class Meta:
        model = Medicamento
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # LÓGICA DE RECUPERACIÓN (LEER)
        if self.instance and self.instance.pk and self.instance.nombre:
            nombre_completo = self.instance.nombre
            
            # 1. Detectar si tiene etiqueta de riesgo al final (Ej: "... [ANTICOAGULANTE]")
            riesgo_detectado = ''
            if nombre_completo.endswith(']'):
                # Buscamos el último corchete de apertura
                inicio_tag = nombre_completo.rfind('[')
                if inicio_tag != -1:
                    # Extraemos el texto dentro de los corchetes: "ANTICOAGULANTE"
                    riesgo_detectado = nombre_completo[inicio_tag+1:-1]
                    # Limpiamos el nombre base quitándole la etiqueta
                    nombre_completo = nombre_completo[:inicio_tag].strip()
            
            # Asignamos el riesgo al selector
            self.fields['clasificacion_riesgo'].initial = riesgo_detectado

            # 2. Separar el resto del nombre (Nombre + Cantidad + Unidad)
            partes = nombre_completo.rsplit(' ', 2)
            if len(partes) == 3 and partes[1].isdigit():
                self.fields['nombre_base'].initial = partes[0]
                self.fields['concentracion'].initial = partes[1]
                self.fields['unidad'].initial = partes[2]
            else:
                self.fields['nombre_base'].initial = nombre_completo

    def clean(self):
        cleaned_data = super().clean()
        base = cleaned_data.get('nombre_base')
        conc = cleaned_data.get('concentracion')
        unit = cleaned_data.get('unidad')
        riesgo = cleaned_data.get('clasificacion_riesgo') # Obtenemos el riesgo
        
        if base:
            # Construir el nombre final: "Paracetamol 500 mg"
            if conc:
                nombre_final = f"{base.strip()} {conc} {unit}"
            else:
                nombre_final = base.strip() # Solo el nombre si no pone dosis
            
            # 2. Agregar la etiqueta de riesgo si existe
            # Resultado: "Warfarina 5 mg [ANTICOAGULANTE]"
            if riesgo:
                nombre_final = f"{nombre_final} [{riesgo}]"
            # Verificar si ya existe (para evitar duplicados como "Paracetamol 500 mg")
            # Excluimos la propia instancia si estamos editando
            qs = Medicamento.objects.filter(nombre__iexact=nombre_final)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError(f"El medicamento '{nombre_final}' ya existe en el catálogo.")
            
            # Inyectamos el nombre construido para que el modelo lo guarde
            self.instance.nombre = nombre_final
        
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