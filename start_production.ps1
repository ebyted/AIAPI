# Script de inicio rapido para produccion (PowerShell)

Write-Host "BeCalm API - Inicio Rapido de Produccion" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host "Servidor: http://168.231.67.221:8011" -ForegroundColor Cyan
Write-Host ""

# Verificar si existe el archivo .env
if (-not (Test-Path ".env")) {
    Write-Host "Archivo .env no encontrado" -ForegroundColor Yellow
    Write-Host "Copiando configuracion de produccion..." -ForegroundColor Yellow
    Copy-Item "env_production.txt" ".env"
    Write-Host "Archivo .env creado desde env_production.txt" -ForegroundColor Green
    Write-Host "EDITA el archivo .env con tus valores reales antes de continuar" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Variables importantes a configurar:" -ForegroundColor White
    Write-Host "  - OPENAI_API_KEY" -ForegroundColor White
    Write-Host "  - SECRET_KEY" -ForegroundColor White
    Write-Host "  - DATABASE_URL (opcional, usa SQLite por defecto)" -ForegroundColor White
    Write-Host ""
    $confirm = Read-Host "Has configurado el archivo .env? (y/N)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "Configura .env primero y ejecuta el script nuevamente" -ForegroundColor Red
        exit 1
    }
}

# Cargar variables de entorno desde .env
Write-Host "Cargando variables de entorno..." -ForegroundColor Yellow
$envLines = Get-Content ".env" -ErrorAction SilentlyContinue
foreach ($line in $envLines) {
    if ($line -match "^([^#].*)=(.*)$") {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Configurar para produccion
$env:ENVIRONMENT = "production"
$env:HOST = "0.0.0.0"
$env:PORT = "8011"
$env:ALLOWED_ORIGINS = "http://168.231.67.221:8011,https://168.231.67.221:8011"

Write-Host "Configuracion cargada" -ForegroundColor Green
Write-Host "HOST: $($env:HOST)" -ForegroundColor White
Write-Host "PORT: $($env:PORT)" -ForegroundColor White
Write-Host "ENVIRONMENT: $($env:ENVIRONMENT)" -ForegroundColor White
Write-Host ""

# Verificar entorno virtual
if (-not (Test-Path "venv")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error creando entorno virtual" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Instalando dependencias..." -ForegroundColor Yellow

# Activar entorno virtual si existe
$activateScript = "venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
}

# Instalar dependencias
pip install -r requirements_production.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error instalando dependencias" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Iniciando servidor de produccion..." -ForegroundColor Green
Write-Host "Logs se mostraran a continuacion" -ForegroundColor White
Write-Host "Presiona Ctrl+C para detener" -ForegroundColor White
Write-Host "----------------------------------------" -ForegroundColor Gray

# Ejecutar el servidor
python main_production.py
