[CmdletBinding()]
param(
    [switch]$SkipBrowserTests,
    [switch]$SkipDockerConfig
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$CommandArguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    Push-Location $WorkingDirectory
    try {
        & $Executable $CommandArguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed: $Executable $($CommandArguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm.cmd is required. Install Node.js 22 LTS before running verification."
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install uv before running backend verification."
}

$frontend = Join-Path $repoRoot "frontend"
$backend = Join-Path $repoRoot "backend"

Invoke-CheckedCommand -Executable "npm.cmd" -CommandArguments @("ci") -WorkingDirectory $frontend
Invoke-CheckedCommand -Executable "npm.cmd" -CommandArguments @("run", "format:check") -WorkingDirectory $frontend
Invoke-CheckedCommand -Executable "npm.cmd" -CommandArguments @("run", "lint") -WorkingDirectory $frontend
Invoke-CheckedCommand -Executable "npm.cmd" -CommandArguments @("run", "typecheck") -WorkingDirectory $frontend
Invoke-CheckedCommand -Executable "npm.cmd" -CommandArguments @("run", "test") -WorkingDirectory $frontend
Invoke-CheckedCommand -Executable "npm.cmd" -CommandArguments @("run", "build") -WorkingDirectory $frontend

if (-not $SkipBrowserTests) {
    Invoke-CheckedCommand -Executable "npx.cmd" -CommandArguments @("playwright", "test", "--config", "playwright.config.ts", "--pass-with-no-tests") -WorkingDirectory $frontend
}

Invoke-CheckedCommand -Executable "uv" -CommandArguments @("sync", "--locked", "--all-groups") -WorkingDirectory $backend
Invoke-CheckedCommand -Executable "uv" -CommandArguments @("run", "ruff", "check", "--config", "pyproject.toml", ".", "../tests/backend") -WorkingDirectory $backend
Invoke-CheckedCommand -Executable "uv" -CommandArguments @("run", "black", "--config", "pyproject.toml", "--check", ".", "../tests/backend") -WorkingDirectory $backend
Invoke-CheckedCommand -Executable "uv" -CommandArguments @("run", "mypy", "app") -WorkingDirectory $backend
Invoke-CheckedCommand -Executable "uv" -CommandArguments @("run", "pytest") -WorkingDirectory $backend

if (-not $SkipDockerConfig) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is required for Docker Compose validation. Use -SkipDockerConfig only when Docker is intentionally unavailable."
    }
    Push-Location $repoRoot
    try {
        & docker compose --env-file .env.example config --quiet
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose config validation failed."
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "CodexForge verification completed successfully."
