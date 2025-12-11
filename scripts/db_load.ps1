# -----------------------------------------------------------------
# Script: db_load.ps1
# Descripción: Carga datos iniciales en la BD local para desarrollo.
# Uso: ./db_load.ps1
# -----------------------------------------------------------------

Write-Host "Cargando fixtures..." -ForegroundColor Cyan
$fixtures = @(
#    "apps/gestion_inventario/fixtures/datos_inventario.json",
    "apps/gestion_inventario/fixtures/inventario_datos_base.json",
    "apps/gestion_inventario/fixtures/inventario_datos_estaciones.json",
    "apps/gestion_inventario/fixtures/inventario_datos_ubicaciones.json",
    "apps/gestion_inventario/fixtures/inventario_datos_ubicaciones_vehiculos.json",
    "apps/gestion_inventario/fixtures/inventario_datos_compartimentos.json",
    "apps/gestion_inventario/fixtures/inventario_datos_marcas.json",
    "apps/gestion_inventario/fixtures/inventario_datos_productos_globales.json",
    "apps/gestion_inventario/fixtures/inventario_datos_proveedores.json",
    "apps/gestion_inventario/fixtures/inventario_datos_productos.json",
    "apps/gestion_inventario/fixtures/inventario_datos_activos.json",
    "apps/gestion_inventario/fixtures/inventario_datos_lotes.json",
    "apps/gestion_inventario/fixtures/inventario_datos_destinatarios.json",
#    "apps/gestion_usuarios/fixtures/datos_usuarios.json",
    "apps/gestion_usuarios/fixtures/usuarios_datos_base.json",
    "apps/gestion_usuarios/fixtures/usuarios_datos_usuarios.json",
#    "apps/gestion_voluntarios/fixtures/datos_voluntarios.json",
    "apps/gestion_voluntarios/fixtures/voluntarios_datos_base.json",
    "apps/gestion_voluntarios/fixtures/voluntarios_datos_voluntarios.json",
#    "apps/gestion_medica/fixtures/datos_medica.json"
    "apps/gestion_medica/fixtures/medica_datos_base.json"
    "apps/gestion_medica/fixtures/medica_datos_fichas.json"
    "apps/gestion_documental/fixtures/documental_datos_base.json"
)

foreach ($fixture in $fixtures) {
    if (Test-Path $fixture) {
        Write-Host " -> $fixture"
        python manage.py loaddata $fixture
    }
}

Write-Host "✅ ¡Listo!" -ForegroundColor Green
$env:PGPASSWORD = $null