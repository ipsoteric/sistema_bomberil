# -----------------------------------------------------------------
# Script: db_reset.ps1
# Descripción: Resetea la BD local para desarrollo.
# Uso: ./db_reset.ps1
# Nota: Requiere PostgreSQL en el PATH.
# -----------------------------------------------------------------

$ErrorActionPreference = "Stop" 



# --- 1. CARGAR VARIABLES DESDE .ENV (Si existe) ---
# PowerShell no lee .env nativamente, así que lo hacemos manual.
if (Test-Path ".env") {
    Write-Host "📄 Leyendo configuración desde .env..." -ForegroundColor Gray
    Get-Content ".env" | Where-Object { $_ -match '=' -and $_ -notmatch '^#' } | ForEach-Object {
        # Divide solo en el primer '=' para respetar valores con '=' dentro
        $parts = $_ -split '=', 2
        $key = $parts[0].Trim()
        $val = $parts[1].Trim()
        
        # Quita comillas si existen
        $val = $val -replace '^["'']|["'']$', ''
        
        # Establece la variable de entorno temporalmente para este script
        [Environment]::SetEnvironmentVariable($key, $val, "Process")
    }
} else {
    Write-Warning "No se encontró el archivo .env en la raíz."
}



# --- 2. CONFIGURACIÓN DE VARIABLES ---
# Ahora sí tomamos los valores (del .env cargado o por defecto)

# Corrección del error "True": Usamos if/else explícito
if ($env:DB_NAME) { $DB_NAME = $env:DB_NAME } else { $DB_NAME = "bomberildb" }
if ($env:DB_USER) { $DB_USER = $env:DB_USER } else { $DB_USER = "postgres" }

# Prioridad de contraseña:
# 1. Variable PGPASSWORD del sistema (si ya la tenías)
# 2. Variable DB_PASSWORD del archivo .env (muy común en Django)
if (-not $env:PGPASSWORD -and $env:DB_PASSWORD) {
    $env:PGPASSWORD = $env:DB_PASSWORD
}

Write-Host "⚙️ Configuración detectada:" -ForegroundColor Gray
Write-Host "   Base de Datos: $DB_NAME" -ForegroundColor Gray
Write-Host "   Usuario:       $DB_USER" -ForegroundColor Gray



# --- 3. INTERACCIÓN DE SEGURIDAD ---
if (-not $env:PGPASSWORD) {
    Write-Host "⚠️ No se detectó contraseña en variables ni en .env." -ForegroundColor Yellow
    $passSecure = Read-Host "Ingresa contraseña para '$DB_USER'" -AsSecureString
    $passPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($passSecure))
    $env:PGPASSWORD = $passPlain
}

Write-Host "🔴 PELIGRO: Se BORRARÁ la base de datos '$DB_NAME' en localhost." -ForegroundColor Red
$confirm = Read-Host "¿Estás seguro? (S/N)"
if ($confirm -ne 'S' -and $confirm -ne 's') { exit }



# --- 4. LIMPIEZA ---
Write-Host "Limpiando caché de Python..." -ForegroundColor Cyan
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Where-Object { $_.FullName -notlike "*\.venv\*" } | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -File -Filter "*.pyc" | Where-Object { $_.FullName -notlike "*\.venv\*" } | Remove-Item -Force



# --- 5. RESETEO DE BD ---
Write-Host "Reiniciando DB..." -ForegroundColor Cyan
try {
    # dropdb usa la variable de entorno PGPASSWORD automáticamente
    dropdb -U $DB_USER --if-exists --force $DB_NAME
} catch {
    Write-Warning "No se pudo borrar (puede que no exista o credenciales incorrectas)."
}

createdb -U $DB_USER $DB_NAME --encoding=UTF8

if ($LASTEXITCODE -ne 0) {
    Write-Error "❌ Falló createdb. Revisa usuario/contraseña arriba."
    exit 1
}



# --- 6. DJANGO ---
Write-Host "Aplicando migraciones..." -ForegroundColor Cyan
python manage.py migrate

Write-Host "✅ ¡Base de datos reiniciada!" -ForegroundColor Green