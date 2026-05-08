# sph2txt Uninstall Script
# Run from: c:\Users\reach\Documents\projects\sph2txt\

$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== SPH2TXT Uninstaller ===" -ForegroundColor Yellow

# 1. Stop the running process
Write-Host "Stopping sph2txt process..." -ForegroundColor Cyan
Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object {
    try { $_.CommandLine -like "*sph2txt*" } catch { $false }
} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Write-Host "[OK] Process stopped" -ForegroundColor Green

# 2. Remove startup shortcut
Write-Host "Removing startup shortcut..." -ForegroundColor Cyan
$startupLink = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\sph2txt.lnk"
if (Test-Path $startupLink) {
    Remove-Item $startupLink -Force
    Write-Host "  Removed: $startupLink" -ForegroundColor Green
} else {
    Write-Host "  No startup shortcut found" -ForegroundColor Gray
}

# 3. Remove scheduled task (if any)
Write-Host "Removing scheduled task..." -ForegroundColor Cyan
Unregister-ScheduledTask -TaskName "sph2txt" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "[OK] Auto-start entries removed" -ForegroundColor Green

# 4. Summary
Write-Host ""
Write-Host "=== Uninstall Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Process stopped and auto-start removed." -ForegroundColor White
Write-Host ""
Write-Host "To fully remove all files, delete this folder:" -ForegroundColor Yellow
Write-Host "  $PSScriptRoot" -ForegroundColor White
Write-Host ""
Write-Host "This will remove: code, venv, models (~5-6 GB), logs, and data." -ForegroundColor Gray
Write-Host "Your system Python, NVIDIA drivers, and Ollama are NOT affected." -ForegroundColor Gray
