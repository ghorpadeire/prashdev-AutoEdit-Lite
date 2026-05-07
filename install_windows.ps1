#Requires -Version 5.1
<#
.SYNOPSIS
    AutoEdit-Lite Windows installer / uninstaller.

.DESCRIPTION
    Installs the AutoEdit-Lite Premiere Pro plugin and Python backend onto
    any Windows machine in one double-click. Run install_windows.bat instead
    of this script directly (it handles the execution-policy bypass).

    What this script does:
      1. Copies the CEP plugin to Premiere Pro's extension folder
      2. Sets the PlayerDebugMode registry key (required for unsigned extensions)
      3. Verifies Python 3.9+ is installed
      4. Creates a Python virtual environment and installs all dependencies
      5. Writes settings.json so the plugin knows where the Python backend lives
      6. Prompts for your Anthropic API key and saves it to .env

    Run with -Uninstall to remove the plugin and settings.

.PARAMETER Uninstall
    Remove the plugin and clean up installer files.
#>

param (
    [switch]$Uninstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Paths ──────────────────────────────────────────────────────────────────────
$scriptDir   = $PSScriptRoot   # folder containing this script (the project root)
$pluginSrc   = Join-Path $scriptDir "premiere-plugin\com.autoedit.premiere"
$cepBase     = Join-Path $env:APPDATA "Adobe\CEP\extensions"
$pluginDst   = Join-Path $cepBase "com.autoedit.premiere"
$settingsDir = Join-Path $env:APPDATA "AutoEdit"
$settingsFile= Join-Path $settingsDir "settings.json"
$venvDir     = Join-Path $scriptDir "venv"
$venvPython  = Join-Path $venvDir "Scripts\python.exe"
$envFile     = Join-Path $scriptDir ".env"
$reqFile     = Join-Path $scriptDir "requirements.txt"

# CSXS versions covering Premiere Pro 2020 – 2025
$csxsVersions = @("9", "10", "11")

function Write-Step { param([string]$msg) Write-Host "`n  $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "  [!] $msg"  -ForegroundColor Yellow }
function Write-Fail { param([string]$msg) Write-Host "`n  [ERROR] $msg`n" -ForegroundColor Red; exit 1 }

# ── Banner ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor White
Write-Host "   AutoEdit-Lite — Windows Installer" -ForegroundColor White
Write-Host "  ============================================================" -ForegroundColor White
Write-Host ""

# ══════════════════════════════════════════════════════════════════════════════
# UNINSTALL PATH
# ══════════════════════════════════════════════════════════════════════════════
if ($Uninstall) {
    Write-Step "Removing plugin from Premiere Pro extension folder..."
    if (Test-Path $pluginDst) {
        Remove-Item -Path $pluginDst -Recurse -Force
        Write-OK "Plugin removed: $pluginDst"
    } else {
        Write-Warn "Plugin folder not found (already removed?): $pluginDst"
    }

    Write-Step "Removing PlayerDebugMode registry keys..."
    foreach ($ver in $csxsVersions) {
        $key = "HKCU:\SOFTWARE\Adobe\CSXS.$ver"
        if (Test-Path $key) {
            try {
                Remove-ItemProperty -Path $key -Name "PlayerDebugMode" -ErrorAction SilentlyContinue
                Write-OK "Cleared CSXS.$ver\PlayerDebugMode"
            } catch {}
        }
    }

    Write-Step "Removing installer settings..."
    if (Test-Path $settingsFile) {
        Remove-Item -Path $settingsFile -Force
        Write-OK "Removed $settingsFile"
    }

    Write-Host ""
    Write-Host "  Uninstall complete. Restart Premiere Pro to apply changes." -ForegroundColor Green
    Write-Host ""
    exit 0
}

# ══════════════════════════════════════════════════════════════════════════════
# INSTALL PATH
# ══════════════════════════════════════════════════════════════════════════════

# ── Step 1: Verify plugin source exists ───────────────────────────────────────
Write-Step "Step 1/6 — Checking plugin source..."
if (-not (Test-Path $pluginSrc)) {
    Write-Fail "Plugin folder not found: $pluginSrc`nMake sure you are running this from the AutoEdit-Lite project folder."
}
Write-OK "Plugin source found."

# ── Step 2: Copy plugin to Premiere CEP extensions folder ─────────────────────
Write-Step "Step 2/6 — Installing Premiere Pro plugin..."
if (-not (Test-Path $cepBase)) {
    New-Item -ItemType Directory -Path $cepBase -Force | Out-Null
}
if (Test-Path $pluginDst) {
    Write-Warn "Plugin already exists — updating it."
    Remove-Item -Path $pluginDst -Recurse -Force
}
Copy-Item -Path $pluginSrc -Destination $pluginDst -Recurse -Force
Write-OK "Plugin copied to: $pluginDst"

# ── Step 3: Set PlayerDebugMode registry key ───────────────────────────────────
Write-Step "Step 3/6 — Setting Premiere Pro debug key (required for unsigned extensions)..."
foreach ($ver in $csxsVersions) {
    $key = "HKCU:\SOFTWARE\Adobe\CSXS.$ver"
    if (-not (Test-Path $key)) {
        New-Item -Path $key -Force | Out-Null
    }
    Set-ItemProperty -Path $key -Name "PlayerDebugMode" -Value "1" -Type String
    Write-OK "Set CSXS.$ver\PlayerDebugMode = 1"
}

# ── Step 4: Verify Python 3.9+ ────────────────────────────────────────────────
Write-Step "Step 4/6 — Checking Python installation..."

$pythonCmd = $null
foreach ($candidate in @("python", "python3")) {
    try {
        $result = & $candidate --version 2>&1
        if ($LASTEXITCODE -eq 0) { $pythonCmd = $candidate; break }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host ""
    Write-Host "  Python was not found on your PATH." -ForegroundColor Red
    Write-Host "  Download it from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  During install, check 'Add Python to PATH', then re-run this installer." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

$versionStr = (& $pythonCmd --version 2>&1).ToString()   # e.g. "Python 3.11.4"
if ($versionStr -match "Python (\d+)\.(\d+)") {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
        Write-Fail "Python 3.9 or newer is required. Found: $versionStr`nDownload a newer version from https://www.python.org/downloads/"
    }
    Write-OK "$versionStr detected."
} else {
    Write-Warn "Could not parse Python version ('$versionStr'). Proceeding anyway."
}

# ── Step 5: Create venv and install requirements ───────────────────────────────
Write-Step "Step 5/6 — Setting up Python virtual environment..."

if (-not (Test-Path $reqFile)) {
    Write-Fail "requirements.txt not found at: $reqFile"
}

if (Test-Path $venvDir) {
    Write-Warn "Existing venv found — recreating it for a clean install."
    Remove-Item -Path $venvDir -Recurse -Force
}

Write-Host "  Creating virtual environment..." -ForegroundColor Gray
& $pythonCmd -m venv $venvDir
if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to create virtual environment." }
Write-OK "Virtual environment created at: $venvDir"

Write-Host "  Installing dependencies (this may take a few minutes)..." -ForegroundColor Gray
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r $reqFile
if ($LASTEXITCODE -ne 0) { Write-Fail "pip install failed. Check your internet connection and try again." }
Write-OK "All Python dependencies installed."

# ── Step 6: Write settings.json and .env ──────────────────────────────────────
Write-Step "Step 6/6 — Saving settings and API key..."

# Write %APPDATA%\AutoEdit\settings.json so the panel picks up both paths automatically
if (-not (Test-Path $settingsDir)) {
    New-Item -ItemType Directory -Path $settingsDir -Force | Out-Null
}

$settings = @{
    backendPath = $scriptDir
    pythonPath  = $venvPython
} | ConvertTo-Json -Compress

[System.IO.File]::WriteAllText($settingsFile, $settings, [System.Text.Encoding]::UTF8)
Write-OK "Settings written to: $settingsFile"

# API key — prompt user; skip if .env already has a real key
$existingKey = ""
if (Test-Path $envFile) {
    $existingKey = (Get-Content $envFile -Raw) -replace "(?ms).*ANTHROPIC_API_KEY=([^\r\n]*).*", '$1'
    $existingKey = $existingKey.Trim()
}

if ($existingKey -and $existingKey -ne "your_key_here" -and $existingKey.StartsWith("sk-ant")) {
    Write-OK "Existing API key found in .env — keeping it."
} else {
    Write-Host ""
    Write-Host "  Enter your Anthropic API key (starts with sk-ant-...)." -ForegroundColor White
    Write-Host "  Get it from: https://console.anthropic.com/" -ForegroundColor Gray
    $apiKey = Read-Host "  API key"
    $apiKey = $apiKey.Trim()

    if (-not $apiKey) {
        Write-Warn "No API key entered. You can add it manually to .env later:"
        Write-Warn "  ANTHROPIC_API_KEY=sk-ant-..."
    } else {
        "ANTHROPIC_API_KEY=$apiKey" | Out-File -FilePath $envFile -Encoding UTF8 -Force
        Write-OK "API key saved to .env"
    }
}

# ── Done ───────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "   AutoEdit-Lite installed successfully!" -ForegroundColor Green
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "   1. Restart Adobe Premiere Pro" -ForegroundColor White
Write-Host "   2. Go to  Window -> Extensions -> AutoEdit" -ForegroundColor White
Write-Host "   3. The panel will open — no path setup needed." -ForegroundColor White
Write-Host ""
Write-Host "  To uninstall, run:  install_windows.bat --uninstall" -ForegroundColor Gray
Write-Host ""
