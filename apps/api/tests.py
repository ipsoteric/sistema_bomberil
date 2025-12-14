# apps/api/tests.py
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from apps.gestion_inventario.models import (
    Estacion, Comuna, Region, Ubicacion, TipoUbicacion, 
    Categoria, ProductoGlobal, Producto, Activo, 
    TipoEstado, Estado, Proveedor, Compartimento
)
from apps.gestion_usuarios.models import Membresia

User = get_user_model()

class InventarioAPITest(APITestCase):
    """
    Pruebas de Integración para la API de Inventario.
    """

    def setUp(self):
        # 1. Usuario Superuser
        self.user, _ = User.objects.get_or_create(
            email='test_api@bomberos.cl', 
            defaults={
                'rut': '99999999-9',
                'first_name': 'Test',
                'last_name': 'API',
                'is_active': True,
                'is_staff': True,
                'is_superuser': True
            }
        )
        self.user.set_password('password123')
        self.user.save()

        # 2. Estación
        self.estacion = Estacion.objects.first()
        if not self.estacion:
            region, _ = Region.objects.get_or_create(nombre="Tarapacá")
            comuna, _ = Comuna.objects.get_or_create(nombre="Iquique", region=region)
            self.estacion = Estacion.objects.create(nombre="Segunda Compañía", comuna=comuna)

        # 3. Membresía
        Membresia.objects.get_or_create(
            usuario=self.user,
            estacion=self.estacion,
            defaults={'estado': 'ACTIVO', 'fecha_inicio': timezone.now().date()}
        )

        # 4. Datos Maestros
        tipo_ubic, _ = TipoUbicacion.objects.get_or_create(nombre="Bodega")
        ubicacion, _ = Ubicacion.objects.get_or_create(
            nombre="Central", estacion=self.estacion, defaults={'tipo_ubicacion': tipo_ubic}
        )
        compartimento, _ = Compartimento.objects.get_or_create(
            nombre="Estante A", ubicacion=ubicacion
        )
        proveedor, _ = Proveedor.objects.get_or_create(nombre="Proveedor Test", rut="11222333-K")
        
        categoria, _ = Categoria.objects.get_or_create(nombre="Rescate")
        pg, _ = ProductoGlobal.objects.get_or_create(
            nombre_oficial="Hacha Pulaski", defaults={'categoria': categoria}
        )
        
        # --- CORRECCIÓN CLAVE AQUÍ ---
        # Definimos explícitamente es_serializado=True para que la API busque Activos
        self.producto, _ = Producto.objects.get_or_create(
            producto_global=pg, 
            estacion=self.estacion, 
            defaults={
                'sku': 'HACHA-001', 
                'es_serializado': True # <--- ¡ESTO FALTABA!
            }
        )
        # Aseguramos el cambio si el objeto ya existía
        if not self.producto.es_serializado:
            self.producto.es_serializado = True
            self.producto.save()
        
        tipo_estado, _ = TipoEstado.objects.get_or_create(nombre="Operativo")
        estado, _ = Estado.objects.get_or_create(nombre="DISPONIBLE", tipo_estado=tipo_estado)

        # 5. Crear Activo
        self.activo, _ = Activo.objects.get_or_create(
            codigo_activo="TEST-ACT-001",
            estacion=self.estacion,
            defaults={
                'producto': self.producto, 
                'estado': estado,
                'compartimento': compartimento,
                'proveedor': proveedor
            }
        )
        
        self.url_existencias = '/api/v1/gestion_inventario/existencias/' 

        # Forzar estación en sesión
        session = self.client.session
        session['active_estacion_id'] = self.estacion.id
        session.save()

    def test_acceso_denegado_sin_token(self):
        """CP-INT-01: API rechaza conexiones anónimas."""
        self.client.logout()
        response = self.client.get(self.url_existencias)
        self.assertIn(response.status_code, [401, 403])

    def test_listar_activos_por_producto(self):
        """CP-INT-02: Usuario autenticado ve los activos de un producto específico."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(f"{self.url_existencias}?producto={self.producto.id}")
        
        self.assertEqual(response.status_code, 200, f"Error API: {response.data}")
        # Ahora esto pasará porque la vista buscará Activos (no lotes) y encontrará el nuestro
        self.assertTrue(len(response.data) > 0, "La lista vino vacía")
        
        activo_en_respuesta = response.data[0]
        self.assertEqual(activo_en_respuesta['codigo'], "TEST-ACT-001")

    def test_listar_sin_parametro_producto_falla(self):
        """CP-INT-03: Validar que la API exige el ID del producto (Bad Request)."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url_existencias)
        self.assertEqual(response.status_code, 400)