#!/bin/bash

# Array con la lista de fixtures (rutas relativas a la raíz del proyecto)
fixtures=(
    "apps/gestion_inventario/fixtures/inventario_datos_base.json"
    "apps/gestion_inventario/fixtures/inventario_datos_estaciones.json"
    "apps/gestion_inventario/fixtures/inventario_datos_ubicaciones.json"
    "apps/gestion_inventario/fixtures/inventario_datos_ubicaciones_vehiculos.json"
    "apps/gestion_inventario/fixtures/inventario_datos_compartimentos.json"
    "apps/gestion_inventario/fixtures/inventario_datos_marcas.json"
    "apps/gestion_inventario/fixtures/inventario_datos_productos_globales.json"
    "apps/gestion_inventario/fixtures/inventario_datos_proveedores.json"
    "apps/gestion_inventario/fixtures/inventario_datos_productos.json"
    "apps/gestion_inventario/fixtures/inventario_datos_activos.json"
    "apps/gestion_inventario/fixtures/inventario_datos_lotes.json"
    "apps/gestion_inventario/fixtures/inventario_datos_destinatarios.json"
    "apps/gestion_usuarios/fixtures/usuarios_datos_base.json"
    #"apps/gestion_usuarios/fixtures/usuarios_datos_usuarios.json"
    "apps/gestion_voluntarios/fixtures/voluntarios_datos_base.json"
    #"apps/gestion_voluntarios/fixtures/voluntarios_datos_voluntarios.json"
    "apps/gestion_medica/fixtures/medica_datos_base.json"
    #"apps/gestion_medica/fixtures/medica_datos_fichas.json"
    "apps/gestion_documental/fixtures/documental_datos_base.json"
)

echo "Iniciando carga de fixtures en Docker..."

# Iterar y cargar
for fixture in "${fixtures[@]}"; do
    if [ -f "$fixture" ]; then
        echo " -> Cargando: $fixture"
        python manage.py loaddata "$fixture"
    else
        echo " ADVERTENCIA: No se encontró el archivo: $fixture"
    fi
done

echo "✅ ¡Carga de fixtures finalizada!"