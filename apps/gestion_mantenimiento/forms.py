from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import PlanMantenimiento, OrdenMantenimiento

class PlanMantenimientoForm(forms.ModelForm):
    """
    Formulario para la creación y edición de Planes de Mantenimiento.
    Incluye validación cruzada para asegurar consistencia según el tipo de trigger.
    """
    class Meta:
        model = PlanMantenimiento
        fields = [
            'nombre', 
            'fecha_inicio',
            'tipo_trigger', 
            'frecuencia', 
            'intervalo', 
            'dia_semana',
            'horas_uso_trigger', 
            'activo_en_sistema'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control form-control-sm text-base', 
                'placeholder': 'Ej: Mantenimiento Preventivo Motosierras',
                'autocomplete': 'off'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control form-control-sm text-base',
                'type': 'date'
            }),
            'tipo_trigger': forms.Select(attrs={
                'class': 'form-select form-select-sm text-base',
                'id': 'id_tipo_trigger'
            }),
            'frecuencia': forms.Select(attrs={
                'class': 'form-select form-select-sm text-base',
                'id': 'id_frecuencia' # ID para JS
            }),
            'intervalo': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-base',
                'min': '1'
            }),
            'dia_semana': forms.Select(attrs={
                'class': 'form-select form-select-sm text-base',
                'id': 'id_dia_semana' # ID para JS
            }),
            'horas_uso_trigger': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-base',
                'placeholder': 'Ej: 50.0',
                'step': '0.1'
            }),
            'activo_en_sistema': forms.CheckboxInput(attrs={
                'class': 'form-check-input' # Los checkbox suelen heredar tamaño del contenedor o label
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # --- MEJORA VISUAL: Etiquetas legibles para Selects ---
        # Reemplazamos el "---------" por defecto de Django por textos de ayuda
        
        # Diccionario campo -> texto placeholder
        placeholders = {
            'tipo_trigger': 'Seleccione un disparador...',
            'frecuencia': 'Seleccione unidad de tiempo...',
            'dia_semana': 'Seleccione día (opcional)...',
        }

        for field_name, label in placeholders.items():
            if field_name in self.fields:
                field = self.fields[field_name]
                # Verificamos si el campo tiene opciones (choices)
                if hasattr(field, 'choices'):
                    # Convertimos a lista mutable
                    choices = list(field.choices)
                    # Si la primera opción es la vacía (valor '' o None)
                    if choices and choices[0][0] in [None, '']:
                        choices[0] = ('', label)
                        field.choices = choices

    def clean(self):
        """
        Validación cruzada robusta.
        Limpia campos innecesarios según el trigger seleccionado y
        valida requerimientos condicionales.
        """
        cleaned_data = super().clean()
        tipo_trigger = cleaned_data.get('tipo_trigger')
        
        if not tipo_trigger:
            return cleaned_data

        if tipo_trigger == PlanMantenimiento.TipoTrigger.TIEMPO:
            frecuencia = cleaned_data.get('frecuencia')
            intervalo = cleaned_data.get('intervalo')
            dia_semana = cleaned_data.get('dia_semana')

            if not frecuencia:
                self.add_error('frecuencia', 'Este campo es obligatorio cuando el trigger es por Tiempo.')
            if not intervalo:
                self.add_error('intervalo', 'Este campo es obligatorio cuando el trigger es por Tiempo.')
            
            # Si es SEMANAL, es recomendable (aunque no forzado, por flexibilidad) pedir el día
            if frecuencia == PlanMantenimiento.FrecuenciaTiempo.SEMANAL and dia_semana is None:
                # Podríamos hacerlo obligatorio o dejarlo opcional. 
                # Lo dejaremos pasar pero el cálculo usará la fecha de inicio por defecto.
                pass 

            # Limpieza de campos ajenos
            cleaned_data['horas_uso_trigger'] = None

        elif tipo_trigger == PlanMantenimiento.TipoTrigger.USO:
            horas = cleaned_data.get('horas_uso_trigger')
            if not horas or horas <= 0:
                self.add_error('horas_uso_trigger', 'Debe especificar las horas (> 0).')

            # Limpieza de campos ajenos
            cleaned_data['frecuencia'] = None
            cleaned_data['intervalo'] = 1
            cleaned_data['dia_semana'] = None

        return cleaned_data




class OrdenCorrectivaForm(forms.ModelForm):
    """
    Formulario simplificado para crear órdenes de mantenimiento correctivo (manuales).
    """
    class Meta:
        model = OrdenMantenimiento
        fields = ['fecha_programada', 'responsable']
        widgets = {
            'fecha_programada': forms.DateInput(attrs={
                'class': 'form-control form-control-sm text-base',
                'type': 'date'
            }),
            'responsable': forms.Select(attrs={
                'class': 'form-select form-select-sm text-base'
            }),
        }

    def __init__(self, *args, **kwargs):
        # 1. Extraemos la estación y la eliminamos de kwargs para evitar errores en super()
        estacion = kwargs.pop('estacion', None)
        
        super().__init__(*args, **kwargs)

        # 2. Si recibimos la estación, filtramos el QuerySet
        if estacion:
            User = get_user_model()
            
            # AQUÍ SE FILTRA:
            # Asumo que tu modelo de Usuario tiene una relación inversa 'membresia'
            # o similar que apunta a la estación. Ajusta 'membresia__estacion' 
            # según tus modelos reales.
            self.fields['responsable'].queryset = User.objects.filter(
                membresias__estacion=estacion,
                membresias__estado='ACTIVO',
                is_active=True # Buena práctica: filtrar solo usuarios activos
            ).distinct()

        # ... (el resto de tu configuración visual: fecha, labels, etc) ...
        if not self.initial.get('fecha_programada'):
             self.initial['fecha_programada'] = timezone.now().date()
        
        self.fields['fecha_programada'].label = "Fecha de Ejecución"
        self.fields['fecha_programada'].help_text = "Fecha estimada para realizar la reparación."

        # Mejora Visual: Placeholder para el select de responsable (ForeignKey)
        self.fields['responsable'].empty_label = "Seleccione un responsable..."