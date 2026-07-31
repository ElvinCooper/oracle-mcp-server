param()

$ErrorActionPreference = "Stop"

Write-Host "=== Oracle MCP Server - Setup ===" -ForegroundColor Cyan
Write-Host ""

# --- 1. Verificar Python ---
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "ERROR: Python no encontrado. Instala Python 3.10+ primero." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python: $($py.Source)"

# --- 2. Crear virtual environment ---
if (-not (Test-Path ".venv")) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    & python -m venv .venv
    if (-not $?) { Write-Host "Error creando .venv" -ForegroundColor Red; exit 1 }
    Write-Host "[OK] .venv creado"
} else {
    Write-Host "[OK] .venv ya existe"
}

# --- 3. Instalar dependencias ---
Write-Host "Instalando dependencias..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe -m pip install -e .
if (-not $?) { Write-Host "Error instalando dependencias" -ForegroundColor Red; exit 1 }
Write-Host "[OK] Dependencias instaladas"

# --- 4. Crear .env si no existe ---
if (-not (Test-Path ".env")) {
    Write-Host "Creando .env desde .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "[OK] .env creado"
} else {
    Write-Host "[OK] .env ya existe"
}

Write-Host ""
Write-Host "=== Setup completado ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Proximos pasos:" -ForegroundColor Green
Write-Host "  1. Edita el archivo .env con tus credenciales Oracle"
Write-Host "  2. Asegurate de tener Oracle Instant Client instalado"
Write-Host "  3. Inicia el servidor: .\.venv\Scripts\oracle-mcp"
Write-Host "     (o: .\.venv\Scripts\python -m oracle_mcp.server)"
Write-Host ""
Write-Host "Para configurarlo en tu cliente MCP, revisa el README.md" -ForegroundColor Green
