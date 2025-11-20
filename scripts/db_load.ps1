# -----------------------------------------------------------------
# Script: db_load.ps1
# Descripción: Carga datos iniciales en la BD local para desarrollo.
# Uso: ./db_load.ps1
# -----------------------------------------------------------------

Write-Host "Cargando fixtures..." -ForegroundColor Cyan
$fixtures = @(
    "apps/gestion_inventario/fixtures/datos_inventario.json",
    "apps/gestion_usuarios/fixtures/datos_usuarios.json",
    "apps/gestion_voluntarios/fixtures/datos_voluntarios.json",
    "apps/gestion_medica/fixtures/datos_medica.json"
)

foreach ($fixture in $fixtures) {
    if (Test-Path $fixture) {
        Write-Host " -> $fixture"
        python manage.py loaddata $fixture
    }
}

Write-Host "✅ ¡Listo!" -ForegroundColor Green
$env:PGPASSWORD = $null