# -----------------------------------------------------------------
# Script para resetear BD (PowerShell - v3 - Ignorando .venv)
# -----------------------------------------------------------------
$ErrorActionPreference = "Stop" 
$DB_NAME = "bomberildb"

# --- LÓGICA DE LIMPIEZA CORREGIDA ---
Write-Host "Limpiando caché de Python (.pyc y __pycache__)..."
# Busca todas las carpetas __pycache__ y las filtra
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Where-Object { 
    $_.FullName -notlike "*\.venv\*" 
} | Remove-Item -Recurse -Force

# Busca todos los archivos .pyc y los filtra
Get-ChildItem -Path . -Recurse -File -Filter "*.pyc" | Where-Object { 
    $_.FullName -notlike "*\.venv\*" 
} | Remove-Item -Force

Write-Host "Borrando archivos de migración anteriores..."
# Busca todos los .py en carpetas "migrations" y los filtra
Get-ChildItem -Path . -Recurse -File -Filter "*.py" | Where-Object { 
    $_.FullName -notlike "*\.venv\*" -and 
    $_.DirectoryName -like "*migrations" -and 
    $_.Name -ne "__init__.py" 
} | Remove-Item -Force
# --- FIN DE LA LÓGICA DE LIMPIEZA ---


Write-Host "Borrando y recreando la base de datos MySQL '$DB_NAME'..."
mysql -u root -e "DROP DATABASE IF EXISTS $DB_NAME;"
mysql -u root -e "CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
Write-Host "Base de datos '$DB_NAME' recreada."


Write-Host "Creando nuevas migraciones..."
python manage.py makemigrations
if ($LASTEXITCODE -ne 0) { throw "Error: 'makemigrations' falló." }

Write-Host "Aplicando migraciones (creando tablas)..."
python manage.py migrate
if ($LASTEXITCODE -ne 0) { throw "Error: 'migrate' falló." }

Write-Host "Cargando datos iniciales (fixtures)..."
python manage.py loaddata apps/gestion_inventario/fixtures/datos_inventario.json
if ($LASTEXITCODE -ne 0) { throw "Error: 'loaddata datos_inventario.json' falló." }

python manage.py loaddata apps/gestion_usuarios/fixtures/datos_usuarios.json
if ($LASTEXITCODE -ne 0) { throw "Error: 'loaddata datos_usuarios.json' falló." }

Write-Host "¡Proceso completado! Base de datos reseteada y cargada."