# -----------------------------------------------------------------
# Script: refresh_migrations.ps1
# Descripción: Borra caché y TODAS las migraciones, luego crea nuevas.
# ¡CUIDADO! Esto reinicia el historial de cambios de la base de datos.
# -----------------------------------------------------------------

$ErrorActionPreference = "Stop"

Write-Host "🧹 Iniciando limpieza profunda de archivos temporales..." -ForegroundColor Cyan

# 1. LIMPIAR CACHÉ (.pyc y __pycache__)
Write-Host " -> Eliminando archivos compilados de Python (__pycache__)..."
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | 
    Where-Object { $_.FullName -notlike "*\.venv\*" } | 
    Remove-Item -Recurse -Force

Get-ChildItem -Path . -Recurse -File -Filter "*.pyc" | 
    Where-Object { $_.FullName -notlike "*\.venv\*" } | 
    Remove-Item -Force

# 2. BORRAR MIGRACIONES (Respetando __init__.py)
Write-Host " -> Eliminando archivos de migración antiguos..."
Get-ChildItem -Path . -Recurse -File -Filter "*.py" | Where-Object { 
    $_.FullName -notlike "*\.venv\*" -and    # Ignorar entorno virtual
    $_.DirectoryName -like "*migrations*" -and # Solo carpetas migrations
    $_.Name -ne "__init__.py"                # NUNCA borrar __init__.py
} | Remove-Item -Force

Write-Host "✅ Limpieza completada." -ForegroundColor Green

# 3. RECREAR MIGRACIONES
Write-Host "🔨 Creando nuevas migraciones iniciales (makemigrations)..." -ForegroundColor Cyan

# Ejecutamos makemigrations
python manage.py makemigrations

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Migraciones regeneradas exitosamente." -ForegroundColor Green
    Write-Host "NOTA: Recuerda que ahora tienes un historial nuevo. Si otros tienen la BD vieja, necesitarán resetearla." -ForegroundColor Yellow
} else {
    Write-Error "❌ Error al crear migraciones. Revisa tu código (models.py)."
}