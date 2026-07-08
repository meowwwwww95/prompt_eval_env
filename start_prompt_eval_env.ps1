param(
    [switch]$SkipMirrorConfig,
    [switch]$SkipInstall,
    [switch]$SkipCliLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
$RequirementsFile = Join-Path $RepoRoot "requirements.txt"
$EnvExampleFile = Join-Path $RepoRoot ".env.example"
$EnvFile = Join-Path $RepoRoot ".env"
$PipConfigDir = Join-Path $env:APPDATA "pip"
$PipConfigFile = Join-Path $PipConfigDir "pip.ini"

function Write-Section {
    param([string]$Message)

    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor DarkCyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor DarkCyan
}

function Read-YesNo {
    param(
        [string]$Prompt,
        [bool]$DefaultYes = $true
    )

    $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    $answer = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($answer)) {
        return $DefaultYes
    }

    return $answer.Trim().ToLowerInvariant() -in @("y", "yes")
}

function Get-PythonLauncher {
    $candidates = @(
        @{ Exe = "py.exe"; Args = @("-3") },
        @{ Exe = "python.exe"; Args = @() },
        @{ Exe = "python"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        try {
            & $candidate.Exe @($candidate.Args + @("--version")) *> $null
            if ($LASTEXITCODE -eq 0) {
                return [pscustomobject]$candidate
            }
        }
        catch {
        }
    }

    throw "Python 3 was not found. Please install Python and enable Add Python to PATH."
}

function Get-CurrentPipMirror {
    if (-not (Test-Path -LiteralPath $PipConfigFile)) {
        return $null
    }

    $match = Select-String -Path $PipConfigFile -Pattern '^\s*index-url\s*=\s*(.+?)\s*$' | Select-Object -First 1
    if ($null -eq $match) {
        return $null
    }

    return $match.Matches[0].Groups[1].Value.Trim()
}

function Configure-PipMirror {
    Write-Section "Step 1: Configure pip mirror"

    $currentMirror = Get-CurrentPipMirror
    if ($currentMirror) {
        Write-Host "Current pip mirror: $currentMirror" -ForegroundColor Yellow
    }
    else {
        Write-Host "No user-level pip mirror config was found." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Available mirrors:"
    Write-Host "  1. Tsinghua University"
    Write-Host "  2. Aliyun"
    Write-Host "  3. USTC"
    Write-Host "  4. Custom"
    Write-Host "  0. Skip and keep current pip config"

    $choice = Read-Host "Enter a number"
    if ([string]::IsNullOrWhiteSpace($choice) -or $choice.Trim() -eq "0") {
        Write-Host "Skipped pip mirror configuration." -ForegroundColor DarkYellow
        return
    }

    $mirror = switch ($choice.Trim()) {
        "1" { [pscustomobject]@{ Name = "Tsinghua"; Url = "https://pypi.tuna.tsinghua.edu.cn/simple"; Host = "pypi.tuna.tsinghua.edu.cn" } }
        "2" { [pscustomobject]@{ Name = "Aliyun"; Url = "https://mirrors.aliyun.com/pypi/simple"; Host = "mirrors.aliyun.com" } }
        "3" { [pscustomobject]@{ Name = "USTC"; Url = "https://pypi.mirrors.ustc.edu.cn/simple"; Host = "pypi.mirrors.ustc.edu.cn" } }
        "4" {
            $customUrl = Read-Host "Enter custom index-url"
            if ([string]::IsNullOrWhiteSpace($customUrl)) {
                throw "Custom mirror URL cannot be empty."
            }

            $customHost = Read-Host "Enter trusted-host or press Enter to leave it empty"
            [pscustomobject]@{ Name = "Custom"; Url = $customUrl.Trim(); Host = $customHost.Trim() }
        }
        default { throw "Invalid selection: $choice" }
    }

    if (-not (Read-YesNo -Prompt "Write this mirror to the current user's pip config?" -DefaultYes $true)) {
        Write-Host "Canceled writing pip config." -ForegroundColor DarkYellow
        return
    }

    New-Item -ItemType Directory -Path $PipConfigDir -Force | Out-Null

    if (Test-Path -LiteralPath $PipConfigFile) {
        $backupPath = "$PipConfigFile.bak"
        Copy-Item -LiteralPath $PipConfigFile -Destination $backupPath -Force
        Write-Host "Backed up existing pip config to: $backupPath" -ForegroundColor DarkGray
    }

    $pipConfigContent = @(
        "[global]"
        "index-url = $($mirror.Url)"
        "timeout = 60"
    )

    if (-not [string]::IsNullOrWhiteSpace($mirror.Host)) {
        $pipConfigContent += "trusted-host = $($mirror.Host)"
    }

    Set-Content -LiteralPath $PipConfigFile -Value $pipConfigContent -Encoding ASCII
    Write-Host "Saved pip mirror: $($mirror.Name)" -ForegroundColor Green
}

function Ensure-Venv {
    param([pscustomobject]$PythonLauncher)

    Write-Section "Step 2: Prepare Python virtual environment"

    if (-not (Test-Path -LiteralPath $VenvPython)) {
        Write-Host "Creating .venv..." -ForegroundColor Yellow
        & $PythonLauncher.Exe @($PythonLauncher.Args + @("-m", "venv", $VenvDir))
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the virtual environment."
        }
    }
    else {
        Write-Host "Found existing virtual environment: .venv" -ForegroundColor Green
    }

    $pipVersion = & $VenvPython -m pip --version
    if ($LASTEXITCODE -ne 0) {
        throw "pip is not available inside the virtual environment."
    }

    Write-Host "Virtual environment is ready: $pipVersion" -ForegroundColor Green
}

function Install-Requirements {
    if ($SkipInstall) {
        Write-Host "Skipped dependency installation because -SkipInstall was provided." -ForegroundColor DarkYellow
        return
    }

    if (-not (Test-Path -LiteralPath $RequirementsFile)) {
        Write-Host "requirements.txt was not found. Skipping dependency installation." -ForegroundColor DarkYellow
        return
    }

    Write-Section "Step 3: Install project dependencies"
    & $VenvPython -m pip install -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install dependencies."
    }

    Write-Host "Dependencies are ready." -ForegroundColor Green
}

function Ensure-EnvFile {
    Write-Section "Step 4: Check .env"

    if (Test-Path -LiteralPath $EnvFile) {
        Write-Host "Found existing .env file." -ForegroundColor Green
        return
    }

    if (-not (Test-Path -LiteralPath $EnvExampleFile)) {
        Write-Host ".env.example was not found. Skipping .env initialization." -ForegroundColor DarkYellow
        return
    }

    Copy-Item -LiteralPath $EnvExampleFile -Destination $EnvFile
    Write-Host "Created .env from .env.example. Please fill in the API URL and API key." -ForegroundColor Green
}

function Start-PromptEvalCli {
    Write-Section "Step 5: Activate .venv and run CLI"

    if (-not (Test-Path -LiteralPath $ActivateScript)) {
        throw "Activate.ps1 was not found in .venv\Scripts."
    }

    Set-Location -LiteralPath $RepoRoot
    . $ActivateScript

    Write-Host ""
    Write-Host "Environment is ready. Active virtual environment: .venv" -ForegroundColor Green
    Write-Host "Current directory: $RepoRoot" -ForegroundColor Green
    Write-Host "Running: python -m prompt_eval_cli" -ForegroundColor Cyan
    Write-Host ""

    python -m prompt_eval_cli
    $cliExitCode = $LASTEXITCODE

    Write-Host ""
    if ($cliExitCode -eq 0) {
        Write-Host "prompt_eval_cli exited successfully. You are still in the current PowerShell window." -ForegroundColor Green
    }
    else {
        Write-Host "prompt_eval_cli exited with code $cliExitCode. You are still in the current PowerShell window." -ForegroundColor Yellow
    }
}

try {
    Set-Location -LiteralPath $RepoRoot

    Write-Section "Prompt Eval CLI One-Click Launcher"
    Write-Host "Project directory: $RepoRoot"

    $pythonLauncher = Get-PythonLauncher
    $pythonVersion = & $pythonLauncher.Exe @($pythonLauncher.Args + @("--version"))
    Write-Host "Detected Python: $pythonVersion" -ForegroundColor Green

    if (-not $SkipMirrorConfig) {
        Configure-PipMirror
    }
    else {
        Write-Host "Skipped pip mirror configuration because -SkipMirrorConfig was provided." -ForegroundColor DarkYellow
    }

    Ensure-Venv -PythonLauncher $pythonLauncher
    Install-Requirements
    Ensure-EnvFile

    if ($SkipCliLaunch) {
        Write-Host ""
        Write-Host "Setup finished. Skipped running prompt_eval_cli because -SkipCliLaunch was provided." -ForegroundColor Green
    }
    else {
        Start-PromptEvalCli
    }
}
catch {
    Write-Host ""
    Write-Host "Launcher failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Please fix the error and try again. The current PowerShell window will stay open." -ForegroundColor Red
    return
}
