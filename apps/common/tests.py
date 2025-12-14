# apps/common/tests.py
from datetime import date, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.common.validators import (
    validar_rut_chileno, 
    validar_solo_letras, 
    validar_celular_chileno, 
    validar_edad
)

class RutValidatorTest(TestCase):
    """
    Pruebas unitarias para validar_rut_chileno.
    """

    def test_rut_valido_con_puntos_y_guion(self):
        """CP-UNIT-01: Acepta RUT válido con formato completo."""
        try:
            validar_rut_chileno("19.980.425-1")
        except ValidationError:
            self.fail("El validador rechazó un RUT válido")

    def test_rut_valido_sin_formato(self):
        """CP-UNIT-02: Acepta RUT válido limpio."""
        try:
            validar_rut_chileno("199804251")
        except ValidationError:
            self.fail("El validador rechazó un RUT sin formato")

    def test_rut_terminado_en_k(self):
        """CP-UNIT-03: Valida correctamente RUT terminado en K."""
        # CORRECCIÓN: Usamos 17.124.966-K que es matemáticamente válido
        # (El anterior terminaba en 1, por eso fallaba)
        try:
            validar_rut_chileno("17.124.966-K")
        except ValidationError as e:
            self.fail(f"Falló validación de dígito K válido: {e}")

    def test_rut_digito_incorrecto(self):
        """CP-UNIT-04: Rechaza RUT con dígito verificador erróneo."""
        with self.assertRaises(ValidationError):
            validar_rut_chileno("19.980.425-K") # El DV real es 1

    def test_rut_formato_basura(self):
        """CP-UNIT-05: Rechaza cadenas que no son RUTs."""
        with self.assertRaises(ValidationError):
            validar_rut_chileno("hola-mundo")

class SoloLetrasValidatorTest(TestCase):
    def test_nombres_validos(self):
        try:
            validar_solo_letras("José María")
        except ValidationError:
            self.fail("Falló con caracteres válidos")

    def test_rechaza_numeros(self):
        with self.assertRaises(ValidationError):
            validar_solo_letras("Juan 2")

class CelularValidatorTest(TestCase):
    def test_formatos_validos(self):
        try:
            validar_celular_chileno("+56912345678")
            validar_celular_chileno("912345678")
        except ValidationError:
            self.fail("Rechazó celular válido")

    def test_largo_incorrecto(self):
        with self.assertRaises(ValidationError):
            validar_celular_chileno("9123") 

    def test_inicio_incorrecto(self):
        with self.assertRaises(ValidationError):
            validar_celular_chileno("812345678")

class EdadValidatorTest(TestCase):
    def test_edad_valida(self):
        fecha = date.today() - timedelta(days=365*20)
        try:
            validar_edad(fecha)
        except ValidationError:
            self.fail("Rechazó una edad válida")

    def test_menor_de_edad(self):
        fecha = date.today() - timedelta(days=365*10)
        with self.assertRaises(ValidationError):
            validar_edad(fecha)

    def test_fecha_futura(self):
        fecha = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            validar_edad(fecha)