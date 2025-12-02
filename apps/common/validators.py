# apps/common/validators.py
import re
from datetime import date
from django.core.exceptions import ValidationError
from itertools import cycle


def validar_solo_letras(value):
    """
    Valida que el texto solo contenga letras y espacios (permite tildes y ñ).
    Ideal para: Nombres, Apellidos.
    """
    # Regex: Inicio a fin, letras (a-z), acentos, ñ, espacios.
    regex = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$'
    if not re.match(regex, value):
        raise ValidationError(
            'Este campo solo debe contener letras y espacios.',
            code='solo_letras'
        )




def validar_rut_chileno(value):
    """
    Algoritmo de Módulo 11 para validar RUT chileno.
    Acepta formatos: 12.345.678-k, 12345678-k, 12345678k
    """
    # 1. Limpieza inicial para operar
    rut_limpio = value.replace('.', '').replace('-', '').upper()
    
    # Validaciones básicas de formato
    if not rut_limpio or len(rut_limpio) < 2:
        raise ValidationError('El RUT ingresado no tiene un formato válido.', code='rut_invalido')

    cuerpo = rut_limpio[:-1]
    dv = rut_limpio[-1]

    # Validar que el cuerpo sean solo números
    if not cuerpo.isdigit():
         raise ValidationError('El cuerpo del RUT debe contener solo números.', code='rut_invalido')

    # 2. Cálculo matemático (Módulo 11)
    try:
        revertido = map(int, reversed(cuerpo))
        factors = cycle(range(2, 8))
        s = sum(d * f for d, f in zip(revertido, factors))
        res = (-s) % 11
        
        if res == 10:
            dv_calculado = 'K'
        elif res == 11:
            dv_calculado = '0'
        else:
            dv_calculado = str(res)
    except Exception:
         raise ValidationError('Error al calcular el dígito verificador.', code='rut_error')

    # 3. Comparación
    if dv != dv_calculado:
        raise ValidationError(f'El RUT {value} no es válido (Dígito verificador incorrecto).', code='rut_incorrecto')




def validar_celular_chileno(value):
    """
    Valida un celular chileno. 
    Es robusto: acepta formatos '912345678' O '+56912345678'.
    """
    # 1. Aseguramos limpieza de espacios (Defensivo)
    val = value.replace(' ', '')
    
    # 2. Si ya viene con el formato de BD (+56), se lo quitamos temporalmente para validar
    if val.startswith('+56'):
        val = val[3:] # Quitamos los primeros 3 caracteres (+56)

    # 3. Validaciones del "Cuerpo" del número
    if not val.isdigit():
        raise ValidationError("El teléfono debe contener solo números.")
    
    if len(val) != 9:
        raise ValidationError(f"El celular debe tener 9 dígitos (ingresaste {len(val)}).")
        
    if not val.startswith('9'):
        raise ValidationError("El celular debe comenzar con 9.")




def validar_edad(fecha_nacimiento):
    """
    Valida que la fecha sea lógica:
    1. No futura.
    2. Edad entre 18 y 100 años.
    """
    hoy = date.today()
    
    # 1. Validación temporal
    if fecha_nacimiento > hoy:
        raise ValidationError("La fecha de nacimiento no puede estar en el futuro.")
    
    # Cálculo de edad preciso
    edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    
    # 2. Rangos de edad
    if edad < 14:
        raise ValidationError(f"El usuario debe ser mayor de 14 años (Tiene {edad} años).")
    if edad > 100:
        raise ValidationError("La fecha de nacimiento no parece válida (Mayor a 100 años).")