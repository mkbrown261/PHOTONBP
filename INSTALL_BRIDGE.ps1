<#
.SYNOPSIS
    Installs ue_http_bridge.py into your UE project's Content/Python folder
    and activates it in a running UE instance via the HTTP API.

.DESCRIPTION
    This script:
      1. Finds your UE project directory (searches common locations, or you set it below).
      2. Copies ue_http_bridge.py into <Project>/Content/Python/.
      3. Tells the running UE to import it right now via the HTTP API (no restart needed).
      4. Verifies the bridge is working.

.USAGE
    Right-click INSTALL_BRIDGE.ps1 -> "Run with PowerShell"
    OR in PowerShell:
        .\INSTALL_BRIDGE.ps1
    OR with explicit project path:
        .\INSTALL_BRIDGE.ps1 -ProjectPath "D:\UEProjects\MyGame"

.NOTES
    Does NOT require Administrator rights.
    UE must be running with Remote Control plugin enabled (port 30010).
#>

param(
    [string]$ProjectPath = ""
)

# ── Config ────────────────────────────────────────────────────────────────────

$UeosRoot   = $PSScriptRoot   # Directory this script lives in
$BridgeSrc  = Join-Path $UeosRoot "ue_scripts\ue_http_bridge.py"
$HttpPort   = 30010
$BaseUrl    = "http://127.0.0.1:$HttpPort"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  PhotonBP HTTP Bridge Installer" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Check bridge source exists ────────────────────────────────────────────────

if (-not (Test-Path $BridgeSrc)) {
    Write-Host "ERROR: ue_http_bridge.py not found at:" -ForegroundColor Red
    Write-Host "  $BridgeSrc" -ForegroundColor Red
    Write-Host "Make sure you're running this from the ueos directory." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Bridge source: $BridgeSrc" -ForegroundColor Gray

# ── Find UE project ───────────────────────────────────────────────────────────

function Find-UEProject {
    # Search common UE project locations for a .uproject file
    $SearchPaths = @(
        "C:\Users\$env:USERNAME\Documents\Unreal Projects",
        "C:\Users\$env:USERNAME\Documents\UnrealProjects",
        "D:\UEProjects",
        "D:\UnrealProjects",
        "C:\UEProjects",
        "E:\UEProjects"
    )
    foreach ($base in $SearchPaths) {
        if (Test-Path $base) {
            $projects = Get-ChildItem -Path $base -Filter "*.uproject" -Recurse -Depth 2 -ErrorAction SilentlyContinue
            if ($projects) {
                return Split-Path $projects[0].FullName -Parent
            }
        }
    }
    return $null
}

if ($ProjectPath -eq "") {
    Write-Host "Searching for UE project..." -ForegroundColor Gray
    $ProjectPath = Find-UEProject
    if ($ProjectPath) {
        Write-Host "Found project: $ProjectPath" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "Could not auto-detect your UE project." -ForegroundColor Yellow
        Write-Host "Enter the full path to your UE project folder" -ForegroundColor Yellow
        Write-Host "(e.g. C:\Users\You\Documents\Unreal Projects\MyGame):" -ForegroundColor Yellow
        $ProjectPath = Read-Host "Project path"
        $ProjectPath = $ProjectPath.Trim('"').Trim("'")
    }
}

if (-not (Test-Path $ProjectPath)) {
    Write-Host "ERROR: Project path does not exist: $ProjectPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Copy bridge to Content/Python ─────────────────────────────────────────────

$ContentPython = Join-Path $ProjectPath "Content\Python"
if (-not (Test-Path $ContentPython)) {
    Write-Host "Creating Content\Python directory..." -ForegroundColor Gray
    New-Item -ItemType Directory -Path $ContentPython -Force | Out-Null
}

$BridgeDst = Join-Path $ContentPython "ue_http_bridge.py"
Copy-Item -Path $BridgeSrc -Destination $BridgeDst -Force
Write-Host "Copied bridge to: $BridgeDst" -ForegroundColor Green

# ── Check UE is running ───────────────────────────────────────────────────────

Write-Host ""
Write-Host "Checking UE Remote Control API on port $HttpPort..." -ForegroundColor Gray

try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/remote/info" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "OK — UE is running and Remote Control is active" -ForegroundColor Green
} catch {
    Write-Host "FAIL — Could not reach UE on port $HttpPort" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure:" -ForegroundColor Yellow
    Write-Host "  1. UE is running" -ForegroundColor Yellow
    Write-Host "  2. Remote Control Plugin is enabled:" -ForegroundColor Yellow
    Write-Host "     Edit > Project Settings > Plugins > Remote Control API = ON" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "The bridge file HAS been copied to Content\Python." -ForegroundColor Green
    Write-Host "It will auto-load next time you open UE." -ForegroundColor Green
    Write-Host ""
    Write-Host "After restarting UE, run: python test_photon.py" -ForegroundColor Cyan
    Read-Host "Press Enter to exit"
    exit 0
}

# ── Load bridge in running UE via HTTP API ────────────────────────────────────

Write-Host ""
Write-Host "Loading bridge in running UE..." -ForegroundColor Gray

$LoadScript = @"
import sys, importlib
sys.path.insert(0, r'$($ContentPython.Replace('\', '\\'))')
if 'ue_http_bridge' in sys.modules:
    importlib.reload(sys.modules['ue_http_bridge'])
    print('bridge:reloaded')
else:
    import ue_http_bridge
    print('bridge:loaded')
"@

$body = @{
    objectPath        = "/Engine/PythonScriptPlugin.Default__PythonScriptPlugin"
    functionName      = "ExecutePythonScript"
    parameters        = @{ PythonScript = $LoadScript }
    generateTransaction = $false
} | ConvertTo-Json -Depth 5

try {
    $result = Invoke-RestMethod -Uri "$BaseUrl/remote/object/call" `
        -Method PUT -Body $body -ContentType "application/json" -TimeoutSec 15
    Write-Host "Load command sent successfully" -ForegroundColor Green
    Write-Host "  Response: $($result | ConvertTo-Json -Compress)" -ForegroundColor Gray
} catch {
    Write-Host "WARN: Could not send load command: $_" -ForegroundColor Yellow
    Write-Host "The bridge file is in place — try restarting UE." -ForegroundColor Yellow
}

# ── Verify bridge is working ──────────────────────────────────────────────────

Write-Host ""
Write-Host "Verifying bridge works (trying PhotonExecBridge.RunScript)..." -ForegroundColor Gray
Start-Sleep -Seconds 1  # Give UE a moment to process

$verifyBody = @{
    objectPath        = "/Engine/PhotonExecBridge.Default__PhotonExecBridge_C"
    functionName      = "RunScript"
    parameters        = @{ Script = "print('bridge_verify_ok')" }
    generateTransaction = $false
} | ConvertTo-Json -Depth 5

$bridgeWorking = $false
try {
    $verifyResult = Invoke-RestMethod -Uri "$BaseUrl/remote/object/call" `
        -Method PUT -Body $verifyBody -ContentType "application/json" -TimeoutSec 10
    $returnValue = $verifyResult.ReturnValue
    if ($returnValue -and $returnValue.Contains("bridge_verify_ok")) {
        $bridgeWorking = $true
        Write-Host "BRIDGE IS WORKING!" -ForegroundColor Green
    } else {
        Write-Host "Bridge responded but output unexpected:" -ForegroundColor Yellow
        Write-Host "  $returnValue" -ForegroundColor Gray
    }
} catch {
    Write-Host "Bridge not yet responding: $_" -ForegroundColor Yellow
}

# ── Summary ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan

if ($bridgeWorking) {
    Write-Host "  SUCCESS! PhotonExecBridge is active." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Now run: python test_photon.py" -ForegroundColor White
} else {
    Write-Host "  Bridge file installed. UE may need a moment or a restart." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  MANUAL ACTIVATION (paste into UE Output Log Python console):" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    import ue_http_bridge" -ForegroundColor White
    Write-Host ""
    Write-Host "  If that fails, paste the full path version:" -ForegroundColor Yellow
    Write-Host "    import sys; sys.path.insert(0, r'$ContentPython'); import ue_http_bridge" -ForegroundColor White
    Write-Host ""
    Write-Host "  Then run: python test_photon.py" -ForegroundColor White
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
