# refresh_dashboard.ps1 - one-click live refresh for the IBKR FIRE dashboard.
# Double-clicked via the "Refresh Dashboard" Desktop shortcut.

$ErrorActionPreference = "Stop"

$ProjectRoot     = Split-Path -Parent $PSScriptRoot          # ...\ibkr-fire-dashboard
$PythonExe       = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$MainPy          = Join-Path $ProjectRoot "src\main.py"
$BaseUrl         = "https://localhost:5000"
$AuthStatusUrl   = "$BaseUrl/v1/api/iserver/auth/status"
$LoginTimeoutSec = 300
$PortWaitSec     = 15

function Test-GatewayReachableAndAuthenticated {
    # A gateway that's up but not yet logged in returns HTTP 401 with a genuinely
    # empty body -- that's "reachable, not authenticated", not "unreachable". So
    # reachability is decided from the HTTP status code (did we get a response at
    # all), never from whether the body happened to be non-empty.
    $bodyFile = Join-Path $env:TEMP "refresh_dashboard_auth_status.json"
    $httpCode = & curl.exe -sk -o $bodyFile -w "%{http_code}" --max-time 5 $AuthStatusUrl 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $httpCode -or $httpCode -eq "000") {
        return @{ Reachable = $false; Authenticated = $false }
    }
    $authenticated = $false
    try {
        $body = Get-Content $bodyFile -Raw -ErrorAction SilentlyContinue
        if ($body) {
            $status = $body | ConvertFrom-Json
            $authenticated = [bool]$status.authenticated
        }
    } catch {
        # Non-JSON or unparseable body (e.g. the empty 401 above) -> not authenticated,
        # but the gateway did respond, so Reachable stays true.
    }
    return @{ Reachable = $true; Authenticated = $authenticated }
}

function Find-GatewayRoot {
    # No hardcoded location: the gateway is a separate download that people put
    # wherever suits them. Checked in order of how explicit the intent is.
    $candidates = @()
    if ($env:IBKR_GATEWAY_HOME) { $candidates += $env:IBKR_GATEWAY_HOME }
    $candidates += Join-Path (Split-Path -Parent $ProjectRoot) "clientportal.gw"  # sibling of the project
    $candidates += Join-Path $ProjectRoot "clientportal.gw"                        # inside the project
    $candidates += Join-Path $env:USERPROFILE "clientportal.gw"
    $candidates += Join-Path $env:USERPROFILE "Desktop\clientportal.gw"
    $candidates += Join-Path $env:USERPROFILE "Downloads\clientportal.gw"

    foreach ($c in $candidates) {
        if ($c -and (Test-Path (Join-Path $c "bin\run.bat"))) { return (Resolve-Path $c).Path }
    }
    return $null
}

function Find-JavaExe {
    $onPath = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
        return (Join-Path $env:JAVA_HOME "bin\java.exe")
    }
    # Common vendor install roots, in no particular order of preference.
    $roots = @(
        "$env:ProgramFiles\Eclipse Adoptium", "$env:ProgramFiles\Java",
        "$env:ProgramFiles\Microsoft\jdk",    "$env:ProgramFiles\Amazon Corretto",
        "$env:ProgramFiles\Zulu",             "${env:ProgramFiles(x86)}\Java"
    )
    foreach ($r in $roots) {
        if (-not (Test-Path $r)) { continue }
        $hit = Get-ChildItem $r -Filter java.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Start-Gateway {
    $GatewayRoot = Find-GatewayRoot
    if (-not $GatewayRoot) {
        throw ("Client Portal Gateway not found. Download it from " +
               "https://download2.interactivebrokers.com/portal/clientportal.gw.zip, unzip it " +
               "next to this project (a folder named clientportal.gw), or set IBKR_GATEWAY_HOME " +
               "to wherever you unzipped it.")
    }
    $java = Find-JavaExe
    if (-not $java) {
        throw "Java not found. Install a JRE (e.g. Eclipse Temurin from adoptium.net), then run this again."
    }
    $javaDir = Split-Path -Parent $java
    if ($env:PATH -notlike "*$javaDir*") {
        $env:PATH = "$javaDir;$env:PATH"
    }

    Write-Host "Starting gateway..."
    $stdout = Join-Path $env:TEMP "refresh_dashboard_gateway.out.log"
    $stderr = Join-Path $env:TEMP "refresh_dashboard_gateway.err.log"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "bin\run.bat root\conf.yaml" `
        -WorkingDirectory $GatewayRoot -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr | Out-Null

    $deadline = (Get-Date).AddSeconds($PortWaitSec)
    while ((Get-Date) -lt $deadline) {
        if ((Test-GatewayReachableAndAuthenticated).Reachable) { return }
        Start-Sleep -Seconds 1
    }
    $captured = @(Get-Content $stdout, $stderr -ErrorAction SilentlyContinue) -join "`n"
    throw "Gateway did not come up on port 5000 within $PortWaitSec seconds.`n$captured"
}

function Get-GatewayProcess {
    # Match on the command line, not just the image name: unrelated java.exe
    # processes (PyCharm's bundled JBR, for one) must not be killed.
    Get-CimInstance Win32_Process -Filter "Name = 'java.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*clientportal.gw*" }
}

function Stop-Gateway {
    param([string]$Message = "Stopping gateway...")
    $procs = @(Get-GatewayProcess)
    if (-not $procs) { return }
    Write-Host $Message
    foreach ($p in $procs) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {}
    }
    # Wait for port 5000 to actually be released. Killing the process is not
    # instant, and starting the next gateway too early fails with
    # "Address already in use: bind" - which then looks like a login problem.
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-GatewayProcess) -and -not (Test-GatewayReachableAndAuthenticated).Reachable) { return }
        Start-Sleep -Milliseconds 300
    }
    Write-Host "  (port 5000 still busy after 10s - continuing anyway)"
}

function Wait-ForLogin {
    Write-Host "Opening browser for login..."
    Start-Process $BaseUrl
    $deadline = (Get-Date).AddSeconds($LoginTimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if ((Test-GatewayReachableAndAuthenticated).Authenticated) {
            Write-Host "Logged in."
            return
        }
        Start-Sleep -Seconds 3
    }
    throw "Login not detected within $([math]::Round($LoginTimeoutSec/60)) minutes. Run the icon again when ready."
}

function Invoke-DashboardRefresh {
    Write-Host "Pulling live data..."
    & $PythonExe $MainPy
    if ($LASTEXITCODE -ne 0) {
        throw "main.py exited with code $LASTEXITCODE (see output above)."
    }
}

try {
    # Always start from a clean slate. A leftover gateway from an earlier run
    # (or a second one started by accident) leaves the browser polling an SSO
    # session that never completes, which presents as "login just doesn't work".
    # Sessions expire after ~24h anyway, so reusing one is rarely a saving.
    $stale = @(Get-GatewayProcess)
    if ($stale) {
        Stop-Gateway -Message "Clearing $($stale.Count) gateway process(es) left over from a previous run..."
    }

    Start-Gateway
    Wait-ForLogin
    Invoke-DashboardRefresh

    Stop-Gateway
    Write-Host "Done."
    Start-Sleep -Seconds 2
} catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Stop-Gateway
    Write-Host ""
    Write-Host "Press Enter to close this window..."
    Read-Host | Out-Null
    exit 1
}
