from django import forms
from django.core.exceptions import ValidationError
from .models import PlanMantenimiento

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
                'class': 'form-control', 
                'placeholder': 'Ej: Mantenimiento Preventivo Motosierras'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'tipo_trigger': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_tipo_trigger'
            }),
            'frecuencia': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_frecuencia' # ID para JS
            }),
            'intervalo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'dia_semana': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_dia_semana' # ID para JS
            }),
            'horas_uso_trigger': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 50.0',
                'step': '0.1'
            }),
            'activo_en_sistema': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

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