# apps/gestion_mantenimiento/tests.py
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.gestion_inventario.models import Estacion, Region, Comuna
from apps.gestion_mantenimiento.models import PlanMantenimiento
from apps.gestion_usuarios.models import Membresia

User = get_user_model()

# Desactivamos hash de estáticos para evitar errores de WhiteNoise en tests
@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class FlujoMantenimientoWebTest(TestCase):
    """
    Prueba de Sistema: Simula la interacción de un usuario en el navegador
    para el módulo de Mantenimiento.
    """

    def setUp(self):
        # 1. Configuración de Entorno (ID Seguro)
        self.estacion = Estacion.objects.order_by('id').first()
        if not self.estacion:
            region, _ = Region.objects.get_or_create(nombre="Tarapacá Test")
            comuna, _ = Comuna.objects.get_or_create(nombre="Iquique Test", region=region)
            self.estacion, _ = Estacion.objects.get_or_create(
                nombre="Segunda Compañía", 
                defaults={'id': 999, 'comuna': comuna, 'codigo': "E999"}
            )

        # 2. Actor
        self.usuario, _ = User.objects.get_or_create(
            email='teniente@bomberos.cl',
            defaults={
                'rut': '11.111.111-1',
                'first_name': 'Juan',
                'last_name': 'Teniente',
                'is_active': True,
                'is_staff': True,     
                'is_superuser': True  
            }
        )
        self.usuario.set_password('password123')
        self.usuario.save()

        # 3. Contexto
        Membresia.objects.update_or_create(
            usuario=self.usuario,
            defaults={
                'estacion': self.estacion,
                'estado': 'ACTIVO',
                'fecha_inicio': timezone.now().date()
            }
        )
        
        self.client = Client()

    def test_acceso_protegido_crear_plan(self):
        """CP-SYS-01: Intentar entrar a crear plan SIN loguearse."""
        url = '/mantenimiento/planes/crear/' 
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_flujo_creacion_plan_exitoso(self):
        """CP-SYS-02: Usuario logueado crea un plan correctamente."""
        
        # 1. Login
        self.client.force_login(self.usuario)

        # 2. Sesión
        session = self.client.session
        session['active_estacion_id'] = self.estacion.id
        session.save()

        # 3. Post - DATOS CORREGIDOS SEGÚN TU MODELO
        url = '/mantenimiento/planes/crear/'
        
        datos_formulario = {
            'nombre': 'Mantenimiento Preventivo Carros',
            'estacion': self.estacion.id,
            'activo_en_sistema': True,
            'fecha_inicio': timezone.now().date(),
            
            # --- CORRECCIÓN DE CAMPOS ---
            # El modelo define choices: TIEMPO o USO
            'tipo_trigger': 'TIEMPO',  
            
            # Si es por tiempo, requiere frecuencia e intervalo
            'frecuencia': 'MENSUAL',   # DIARIO, SEMANAL, MENSUAL, ANUAL
            'intervalo': 1,            # "Cada 1 mes"
            
            # Campos opcionales (si tu form los pide)
            'responsable': self.usuario.id,
            'descripcion': 'Revisión general'
        }

        response = self.client.post(url, datos_formulario)

        if response.status_code == 200:
            errores = response.context['form'].errors if response.context else "Error desconocido"
            self.fail(f"Formulario inválido: {errores}")
            
        self.assertEqual(response.status_code, 302, "No redirigió tras guardar")

        # 4. Verificación
        nuevo_plan = PlanMantenimiento.objects.filter(nombre='Mantenimiento Preventivo Carros').first()
        self.assertIsNotNone(nuevo_plan)
        self.assertEqual(nuevo_plan.tipo_trigger, 'TIEMPO')
        self.assertEqual(nuevo_plan.frecuencia, 'MENSUAL')