# Script para construir la imagen Docker con BuildKit habilitado
# Esto permite usar cache mounts que persisten incluso si alguna descarga falla

Write-Host "🚀 Construyendo imagen Docker con BuildKit y cache optimizado..." -ForegroundColor Cyan

# Habilitar BuildKit
$env:DOCKER_BUILDKIT=1
$env:COMPOSE_DOCKER_CLI_BUILD=1

# Construir con docker-compose (usa BuildKit automáticamente)
docker-compose build --progress=plain

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Build completado exitosamente!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Para iniciar el contenedor ejecuta:" -ForegroundColor Yellow
    Write-Host "  docker-compose up -d" -ForegroundColor White
} else {
    Write-Host "⚠️  Build falló. Intenta ejecutar nuevamente." -ForegroundColor Red
    Write-Host "Las descargas exitosas están cacheadas y no se repetirán." -ForegroundColor Yellow
}
