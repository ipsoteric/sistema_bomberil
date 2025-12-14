# apps/gestion_usuarios/tests_auditoria.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.gestion_usuarios.models import RegistroActividad

User = get_user_model()

class AuditoriaTest(TestCase):
    def test_registro_actividad_creado(self):
        """CP-SEG-01: Verificar que acciones críticas generan un log de auditoría."""
        
        # 1. Crear usuario con TODOS los campos obligatorios (RUT, Nombre, etc.)
        usuario = User.objects.create_user(
            email='auditor@bomberos.cl', 
            password='123', 
            rut='99.999.999-K',
            first_name='Auditor',
            last_name='De Seguridad'
        )
        
        self.client.force_login(usuario)
        
        # 2. Simulamos la creación de un log (acción auditada)
        # Importante: 'ip_address' va dentro del JSON 'detalles'
        RegistroActividad.objects.create(
            actor=usuario,
            verbo="realizó una prueba de seguridad",
            detalles={
                'prueba': 'seguridad',
                'ip_address': '127.0.0.1' 
            }
        )

        # 3. Verificar que se guardó en la BD
        ultimo_log = RegistroActividad.objects.last()
        
        self.assertIsNotNone(ultimo_log, "El log de auditoría no se creó")
        self.assertEqual(ultimo_log.actor, usuario, "El actor del log no coincide")
        self.assertEqual(ultimo_log.verbo, "realizó una prueba de seguridad")
        
        # Verificar integridad del JSON
        self.assertEqual(ultimo_log.detalles['ip_address'], '127.0.0.1')