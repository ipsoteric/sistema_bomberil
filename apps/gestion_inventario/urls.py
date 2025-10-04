from django.urls import path
from .views import *

app_name = 'gestion_inventario'

urlpatterns = [
    # Página Inicial de la gestión de inventario
    path('', InventarioInicioView.as_view(), name="ruta_inicio"),
    # Pruebas
    path('pruebas/', InventarioPruebasView.as_view(), name="ruta_pruebas"),
    # Obtener datos para gráfico de total existencias por categoría (API)
    path('existencias_por_categoria/', grafico_existencias_por_categoria, name="ruta_obtener_grafico_categoria"),

    # Lista de almacenes
    path('almacenes/', AlmacenListaView.as_view(), name="ruta_lista_almacenes"),
    # Crear almacen
    path('almacenes/crear/', AlmacenCrearView.as_view(), name="ruta_crear_almacen"),
]