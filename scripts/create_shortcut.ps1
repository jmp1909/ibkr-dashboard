# create_shortcut.ps1 - put a "Refresh Dashboard" icon on the Desktop.
# Run once after setup:  powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
# Paths are derived from this script's own location, so it works wherever the
# project is checked out.

$ErrorActionPreference = "Stop"

$RefreshScript = Join-Path $PSScriptRoot "refresh_dashboard.ps1"
if (-not (Test-Path $RefreshScript)) {
    throw "Cannot find refresh_dashboard.ps1 next to this script ($PSScriptRoot)."
}

$LinkPath = Join-Path ([Environment]::GetFolderPath('Desktop')) "Refresh Dashboard.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($LinkPath)
$Shortcut.TargetPath       = "powershell.exe"
$Shortcut.Arguments        = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Normal -File `"$RefreshScript`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.IconLocation     = "powershell.exe,0"
$Shortcut.Description      = "Refresh the IBKR FIRE dashboard with live data"
$Shortcut.Save()

Write-Host "Created: $LinkPath"
Write-Host "  -> $RefreshScript"
