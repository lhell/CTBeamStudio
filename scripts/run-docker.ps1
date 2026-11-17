# Run CTBeamStudio in Docker (Windows / PowerShell).
#
#   .\scripts\run-docker.ps1                          # mounts .\data
#   .\scripts\run-docker.ps1 -DataDir C:\data\ct      # mounts that folder
#   .\scripts\run-docker.ps1 -Slim                    # viewer only, no projection
#
# Builds the image on first use. Data is mounted read-only at /data; type
# /data/<study> into the sidebar's "DICOM Folder" field.
param(
    [string]$DataDir = (Join-Path (Get-Location) "data"),
    [switch]$Slim,
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$container = if ($Slim) { "ctbeamstudio-slim" } else { "ctbeamstudio" }
$image = if ($Slim) { "ctbeamstudio:slim" } else { "ctbeamstudio:full" }
$target = if ($Slim) { "slim" } else { "full" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker not found. Install Docker Desktop (winget install --id Docker.DockerDesktop -e) and start it."
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon not reachable. Start Docker Desktop and wait until it is ready."
}

if (-not (Test-Path -LiteralPath $DataDir)) {
    throw "Data folder not found: $DataDir"
}
$DataDir = (Resolve-Path -LiteralPath $DataDir).Path

docker stop $container *> $null
docker rm $container *> $null

docker image inspect $image *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Building $image (target: $target)..."
    docker build -t $image --target $target .
    if ($LASTEXITCODE -ne 0) { throw "Image build failed." }
}

Write-Host "Starting $container on port $Port (data: $DataDir -> /data)..."
docker run -d -p "${Port}:8501" --name $container `
    -v "${DataDir}:/data:ro" `
    -v "${container}-cache:/app/data" `
    $image
if ($LASTEXITCODE -ne 0) { throw "Container start failed." }

Write-Host "Waiting for the health endpoint..."
$healthy = $false
foreach ($i in 1..30) {
    Start-Sleep -Seconds 2
    try {
        $resp = Invoke-WebRequest "http://localhost:$Port/_stcore/health" -UseBasicParsing -TimeoutSec 3
        if ($resp.Content -match "ok") { $healthy = $true; break }
    } catch { }
}
if (-not $healthy) {
    Write-Warning "Health endpoint did not answer in 60 s. Logs:"
    docker logs --tail 40 $container
} else {
    Write-Host "CTBeamStudio running at http://localhost:$Port"
    Write-Host "In the sidebar, enter /data/<your-study> as the DICOM folder."
}
