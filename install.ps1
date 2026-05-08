# sph2txt Install Script
# Run from: c:\Users\reach\Documents\projects\sph2txt\

param(
    [switch]$SkipVenv,
    [switch]$AddStartup
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

Write-Host "=== SPH2TXT Installer ===" -ForegroundColor Yellow
Write-Host "Project root: $projectRoot" -ForegroundColor Gray
Write-Host ""

# 1. Create virtual environment
if (-not $SkipVenv) {
    if (Test-Path "$projectRoot\s2tenv") {
        Write-Host "[OK] Virtual environment already exists" -ForegroundColor Green
    } else {
        Write-Host "Creating virtual environment..." -ForegroundColor Cyan
        python -m venv "$projectRoot\s2tenv"
        Write-Host "[OK] Virtual environment created" -ForegroundColor Green
    }
}

# 2. Install dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
& "$projectRoot\s2tenv\Scripts\pip.exe" install -r "$projectRoot\requirements.txt"
Write-Host "[OK] Dependencies installed" -ForegroundColor Green

# 3. Ensure data directories exist
$dirs = @("models\huggingface", "data\exports", "logs", "assets")
foreach ($dir in $dirs) {
    $fullPath = Join-Path $projectRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}
Write-Host "[OK] Directory structure ready" -ForegroundColor Green

# 4. Optionally add to Windows startup
if ($AddStartup) {
    Write-Host "Adding startup shortcut..." -ForegroundColor Cyan
    $ws = New-Object -ComObject WScript.Shell
    $shortcut = $ws.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\sph2txt.lnk")
    $shortcut.TargetPath = "$projectRoot\s2tenv\Scripts\pythonw.exe"
    $shortcut.Arguments = "$projectRoot\src\main.py"
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.WindowStyle = 7
    $shortcut.Save()
    Write-Host "[OK] Startup shortcut created" -ForegroundColor Green
}

# 5. Summary
Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To run:" -ForegroundColor White
Write-Host "  .\s2tenv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "  python src\main.py" -ForegroundColor Gray
Write-Host ""
Write-Host "First run will download the Whisper model (~3 GB)." -ForegroundColor Yellow
