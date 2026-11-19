# Create a desktop shortcut that starts CTBeamStudio and opens the default browser.
#
# Why this script exists: two pieces of the "double-click and it runs" setup live
# outside the repo and were hand-made once:
#
#   1. %USERPROFILE%\.streamlit\credentials.toml -- without it, Streamlit asks for
#      an email on first start ("Welcome to Streamlit! Email:"). That prompt reads
#      stdin, so a server started with --server.headless false blocks forever
#      instead of ever binding port 8501.
#   2. The desktop shortcut itself, pointing at run_app.cmd with that same flag so
#      Streamlit opens http://localhost:8501 in the user's default browser.
#
# The shortcut runs run_app.cmd, which activates the conda env ct-viewer (needed
# for parallelproj) -- this script never calls python or streamlit itself.
#
# Usage (from anywhere, Windows only):
#   powershell -ExecutionPolicy Bypass -File scripts\install_desktop_shortcut.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install_desktop_shortcut.ps1 -Name "CTBeam"

[CmdletBinding()]
param(
    # Repo root that contains run_app.cmd. Defaults to the parent of this script.
    # Resolved in the body: $PSScriptRoot is not reliable inside a param default.
    [string]$RepoPath = '',

    # Shortcut file name, without the .lnk extension.
    [string]$Name = 'CTBeamStudio'
)

$ErrorActionPreference = 'Stop'

if (-not $IsWindows -and $PSVersionTable.PSVersion.Major -ge 6) {
    throw 'This script creates a Windows .lnk shortcut and only runs on Windows.'
}

if (-not $RepoPath) {
    if (-not $PSScriptRoot) { throw 'Cannot infer the repo root - pass -RepoPath <repo root>.' }
    $RepoPath = Split-Path -Parent $PSScriptRoot
}

$RepoPath = (Resolve-Path $RepoPath).Path
$runApp = Join-Path $RepoPath 'run_app.cmd'
if (-not (Test-Path $runApp)) {
    throw "run_app.cmd not found at $runApp - pass -RepoPath <repo root>."
}

# 1. Streamlit first-run credentials. Written once, never overwritten, so an
#    existing email address (if the user did answer the prompt) survives.
$streamlitDir = Join-Path $env:USERPROFILE '.streamlit'
$credentials = Join-Path $streamlitDir 'credentials.toml'
if (Test-Path $credentials) {
    Write-Host "kept     $credentials"
}
else {
    New-Item -ItemType Directory -Force -Path $streamlitDir | Out-Null
    Set-Content -Path $credentials -Value "[general]`nemail = `"`""
    Write-Host "created  $credentials"
}

# 2. The shortcut. --server.headless false overrides .streamlit/config.toml
#    (headless = true) for this launch only: it is what makes Streamlit open the
#    default browser at http://localhost:8501.
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop) { throw 'Could not resolve the Desktop folder.' }
$lnk = Join-Path $desktop "$Name.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\cmd.exe'
$shortcut.Arguments = '/c run_app.cmd --server.headless false'
$shortcut.WorkingDirectory = $RepoPath
$shortcut.Description = 'Start CTBeamStudio (conda env ct-viewer) and open http://localhost:8501'
$shortcut.WindowStyle = 7  # minimized: the log keeps running, the browser is the UI
$icon = Join-Path $env:USERPROFILE 'miniforge3\envs\ct-viewer\python.exe'
if (Test-Path $icon) { $shortcut.IconLocation = "$icon,0" }
$shortcut.Save()
Write-Host "created  $lnk"

Write-Host ''
Write-Host "Double-click '$Name' on the desktop: it activates ct-viewer, starts the" -ForegroundColor Green
Write-Host 'server on port 8501 and opens http://localhost:8501 in your default browser.' -ForegroundColor Green
