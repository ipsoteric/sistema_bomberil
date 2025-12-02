from django import forms


class RutSplitWidget(forms.TextInput):
    template_name = 'common/widgets/rut_split_widget.html'

    def value_from_datadict(self, data, files, name):
        cuerpo = data.get(f'{name}_cuerpo')
        dv = data.get(f'{name}_dv')
        
        # Caso 1: Usuario completó ambos (Validación estricta)
        if cuerpo and dv:
            return f"{cuerpo}-{dv}"
            
        # Caso 2: Usuario solo puso el cuerpo (Para cálculo automático)
        # Esto permite que RutField.to_python reciba el número y calcule el DV
        if cuerpo and not dv:
            return cuerpo
            
        # Caso 3: Campo vacío
        return None




class TelefonoChileWidget(forms.TextInput):
    template_name = 'common/widgets/telefono_widget.html'

    def value_from_datadict(self, data, files, name):
        # El widget solo maneja la parte "cuerpo" (912345678).
        # El prefijo +56 se agrega en el form_field.py
        return data.get(name)