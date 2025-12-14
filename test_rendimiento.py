# test_rendimiento.py
import os
import time
import django
import random

# 1. Configurar entorno Django fuera de manage.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model
from apps.gestion_inventario.models import (
    Activo, Producto, ProductoGlobal, Categoria, 
    Marca, Estacion, Ubicacion, TipoUbicacion, 
    Compartimento, Estado, TipoEstado, Comuna, Region, Proveedor
)

def preparar_datos_masivos(cantidad=1000):
    """Crea datos maestros y X cantidad de activos para la prueba."""
    print(f"--- 1. PREPARANDO ENTORNO (Generando {cantidad} registros) ---")
    
    # Datos Maestros
    region, _ = Region.objects.get_or_create(nombre="Region LoadTest")
    comuna, _ = Comuna.objects.get_or_create(nombre="Comuna LoadTest", region=region)
    estacion, _ = Estacion.objects.get_or_create(
        nombre="Estación de Carga", 
        defaults={'id': 888, 'comuna': comuna, 'codigo': 'E888'}
    )
    
    tipo_ubic, _ = TipoUbicacion.objects.get_or_create(nombre="Bodega Masiva")
    ubicacion, _ = Ubicacion.objects.get_or_create(
        nombre="Bodega Test", estacion=estacion, defaults={'tipo_ubicacion': tipo_ubic}
    )
    compartimento, _ = Compartimento.objects.get_or_create(nombre="Estante Z", ubicacion=ubicacion)
    
    categoria, _ = Categoria.objects.get_or_create(nombre="Material Mayor")
    marca, _ = Marca.objects.get_or_create(nombre="Marca Test")
    pg, _ = ProductoGlobal.objects.get_or_create(
        nombre_oficial="Equipo de Prueba Masiva", 
        defaults={'categoria': categoria, 'marca': marca, 'modelo': 'X-1000'}
    )
    
    producto, _ = Producto.objects.get_or_create(
        producto_global=pg, estacion=estacion, defaults={'sku': 'TEST-LOAD'}
    )
    
    # --- CORRECCIÓN DE ESTADO ---
    # Buscamos primero por nombre para evitar choque de unicidad
    tipo_estado, _ = TipoEstado.objects.get_or_create(nombre="Operativo")
    
    # Usamos get_or_create con 'defaults' para buscar SOLO por nombre
    estado, _ = Estado.objects.get_or_create(
        nombre="DISPONIBLE", 
        defaults={'tipo_estado': tipo_estado, 'descripcion': 'Generado por Test'}
    )

    proveedor, _ = Proveedor.objects.get_or_create(nombre="Prov Test", rut="55555555-5")

    # Creación Masiva (Bulk Create)
    conteo_actual = Activo.objects.filter(estacion=estacion).count()
    faltantes = cantidad - conteo_actual
    
    if faltantes > 0:
        print(f"Generando {faltantes} activos nuevos (esto puede tomar unos segundos)...")
        activos_a_crear = []
        for i in range(faltantes):
            # Generamos código único real
            codigo_unico = f"LOAD-{int(time.time())}-{i}"
            
            activos_a_crear.append(Activo(
                producto=producto,
                estacion=estacion,
                codigo_activo=codigo_unico,
                estado=estado,
                compartimento=compartimento,
                proveedor=proveedor
            ))
        
        Activo.objects.bulk_create(activos_a_crear)
        print("Datos generados exitosamente.")
    else:
        print("Datos suficientes ya existentes.")

    return estacion

def ejecutar_prueba_carga(estacion):
    """Mide el tiempo de respuesta de una consulta pesada."""
    print("\n--- 2. EJECUTANDO PRUEBA DE CARGA ---")
    print("Escenario: Consultar lista completa de activos y serializar datos básicos.")
    
    # Pausa técnica para asegurar que la DB terminó de escribir
    time.sleep(1)
    
    inicio = time.time()
    
    # Simulación de Queryset (Lo que hace la API)
    # Traemos 1000 registros de la DB usando select_related para optimizar
    queryset = Activo.objects.filter(estacion=estacion).select_related(
        'producto__producto_global', 'estado', 'compartimento__ubicacion'
    )
    
    # Forzamos la evaluación de la query convirtiendo a lista
    activos = list(queryset)
    
    # Simulación de Procesamiento (Serialización)
    data = []
    for a in activos:
        data.append({
            'id': str(a.id),
            'codigo': a.codigo_activo,
            'nombre': a.producto.producto_global.nombre_oficial,
            'estado': a.estado.nombre
        })
        
    fin = time.time()
    tiempo_total = fin - inicio
    
    print(f"\nResultados:")
    print(f"- Registros procesados: {len(data)}")
    print(f"- Tiempo Total: {tiempo_total:.4f} segundos")
    
    # Validación SLA (2.0 segundos)
    limite_sla = 2.0
    if tiempo_total < limite_sla:
        print(f"\n✅ RESULTADO: APROBADO (Cumple SLA < {limite_sla}s)")
    else:
        print(f"\n❌ RESULTADO: FALLIDO (Lento > {limite_sla}s)")

if __name__ == "__main__":
    try:
        estacion_test = preparar_datos_masivos(1000)
        ejecutar_prueba_carga(estacion_test)
    except Exception as e:
        print(f"\nError crítico en la prueba: {e}")