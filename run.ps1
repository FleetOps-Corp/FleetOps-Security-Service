param (
    [string]$action,   
    [string]$service = "role_service" 
)

if (-not $action) {
    Write-Host "Uso correcto: .\run.ps1 <acción> <servicio>" -ForegroundColor Cyan
    Write-Host "Acciones disponibles: test, lint, typecheck, format"
    Write-Host "Ejemplo: .\run.ps1 test auth_service" -ForegroundColor Gray
    exit
}

switch ($action) {
    "test"      { docker compose exec $service pytest /app/tests }
    "lint"      { docker compose exec $service ruff check app/ }
    "typecheck" { docker compose exec $service mypy app/ }
    "format"    { docker compose exec $service ruff format app/ }
    Default     { Write-Host "Acción no reconocida: $action" -ForegroundColor Red }
}