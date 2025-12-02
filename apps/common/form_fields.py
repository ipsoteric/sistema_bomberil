from django import forms
from django.core.exceptions import ValidationError
from .utils import calcular_dv
from .validators import validar_solo_letras, validar_celular_chileno
from .widgets import RutSplitWidget, TelefonoChileWidget


class RutField(forms.CharField):
    """
    Campo inteligente para RUT Chileno.
    - Normaliza formato (XX.XXX.XXX-X -> XXXXXXXX-X)
    - Si el usuario omite el DV, lo calcula automáticamente (Requisito Académico).
    - Si el usuario incluye el DV, valida que corresponda (Integridad de Datos).
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'RUT')
        kwargs.setdefault('max_length', 12)
        kwargs['widget'] = RutSplitWidget()

        super().__init__(*args, **kwargs)


    def to_python(self, value):
        # 1. Ejecutar lógica base de CharField
        value = super().to_python(value)
        if value in self.empty_values:
            return value

        # 2. Limpieza agresiva: Fuera puntos, espacios y guiones
        #    "12.345.678-k" -> "12345678K"
        val_limpio = value.replace('.', '').replace(' ', '').replace('-', '').upper()

        if not val_limpio.isalnum():
             raise ValidationError("El RUT contiene caracteres inválidos.")

        # 3. Detección de Intención: ¿Trae DV o no?
        #    Analizamos el input ORIGINAL (con guiones) para saber la intención del usuario.
        
        cuerpo = ""
        dv_usuario = None
        
        if '-' in value:
            # Caso A: Usuario explícito (111-K). Validamos.
            if len(val_limpio) < 2:
                raise ValidationError("Formato incorrecto.")
            cuerpo = val_limpio[:-1]
            dv_usuario = val_limpio[-1]
        else:
            # Caso B: Usuario implícito (111). Calculamos.
            # Asumimos que todo el input es el cuerpo.
            cuerpo = val_limpio
            
        # Validación básica de números
        if not cuerpo.isdigit():
             raise ValidationError("El cuerpo del RUT debe contener solo números.")

        # 4. Cálculo Matemático (Core)
        dv_calculado = calcular_dv(cuerpo)
        
        # 5. Bifurcación de Lógica
        if dv_usuario:
            # Si el usuario dijo "Soy dígito K", y la matemática dice "Eres 5" -> ERROR
            if dv_usuario != dv_calculado:
                raise ValidationError(
                    f"RUT inválido. El dígito verificador no corresponde al cuerpo ingresado.",
                    code='rut_checksum_error'
                )
        
        # 6. Retorno Estandarizado
        # Siempre retornamos formato limpio para la BD: 12345678-K
        return f"{cuerpo}-{dv_calculado}"




class TelefonoChileField(forms.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label', 'Teléfono')
        kwargs.setdefault('max_length', 12) # +56 9 1234 5678
        # Asignamos el widget visual
        kwargs['widget'] = TelefonoChileWidget()
        super().__init__(*args, **kwargs)
        # Agregamos validador de formato (solo el cuerpo)
        self.validators.append(validar_celular_chileno)

    def to_python(self, value):
        """
        Limpia espacios y agrega +56.
        Entrada widget: "9 1234 5678"
        Salida BD: "+56912345678"
        """
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        
        # 1. ELIMINAR ESPACIOS (Tu requerimiento estricto)
        value = value.replace(' ', '')
        
        # 2. Agregar prefijo +56 si no viene
        if not value.startswith('+56'):
            value = f"+56{value}"
            
        return value
    
    def prepare_value(self, value):
        """
        Quita el +56 para mostrarlo en el widget (que ya tiene el +56 fijo visual).
        """
        value = super().prepare_value(value)
        if value and isinstance(value, str) and value.startswith('+56'):
            return value[3:] # Retorna solo 912345678
        return value




class NombrePropioField(forms.CharField):
    """
    Campo para Nombres y Apellidos.
    Rechaza números y símbolos. Capitaliza automáticamente (Juan Perez).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validators.append(validar_solo_letras)

    def to_python(self, value):
        value = super().to_python(value)
        if value:
            # "juan perez" -> "Juan Perez" (Title Case)
            return value.title() 
        return value