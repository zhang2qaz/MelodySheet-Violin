<#
.SYNOPSIS
    Builds the MelodySheet Windows installer end-to-end.

.DESCRIPTION
    Run this on a Windows machine from the repo root:
      powershell -ExecutionPolicy Bypass -File installer\build.ps1

    Steps:
      1. Create / refresh a Python venv at apps\api\.venv-build
      2. Install backend dependencies + pyinstaller
      3. Vendor ffmpeg.exe (downloaded once into installer\vendored\ffmpeg)
      4. Run `npm ci` + static export for the frontend
      5. PyInstaller bundles backend + frontend + ffmpeg into dist\MelodySheet
      6. Inno Setup compiles dist\MelodySheet → installer\out\MelodySheet-Setup.exe

    Prerequisites (one-time install on the build machine):
      - Python 3.11 x64 in PATH
      - Node.js 20 LTS in PATH
      - Inno Setup 6 in PATH (typically C:\Program Files (x86)\Inno Setup 6\ISCC.exe)
      - Internet access for the ffmpeg download (first run only)
#>
[CmdletBinding()]
param(
    [switch]$SkipFfmpegDownload,
    [switch]$SkipWebBuild,
    [switch]$SkipBackendBuild,
    [string]$IsccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"

function Section($name) {
    Write-Host ""
    Write-Host "==> $name" -ForegroundColor Cyan
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$installerDir = Join-Path $repoRoot "installer"
$apiDir = Join-Path $repoRoot "apps\api"
$webDir = Join-Path $repoRoot "apps\web"
$venv = Join-Path $apiDir ".venv-build"
$ffmpegDir = Join-Path $installerDir "vendored\ffmpeg"
$ffmpegExe = Join-Path $ffmpegDir "ffmpeg.exe"

Section "Verifying build prerequisites"
foreach ($cmd in @("python", "npm")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Required executable '$cmd' not found in PATH."
    }
}
if (-not $SkipBackendBuild -and -not (Test-Path $IsccPath)) {
    Write-Warning "Inno Setup compiler not found at $IsccPath. The .exe step will be skipped — adjust -IsccPath or install Inno Setup 6."
}

Section "Preparing Python venv"
if (-not (Test-Path $venv)) {
    python -m venv $venv
}
$venvPy = Join-Path $venv "Scripts\python.exe"
& $venvPy -m pip install --upgrade pip wheel setuptools | Out-Null
& $venvPy -m pip install -r (Join-Path $apiDir "requirements.txt")
& $venvPy -m pip install pyinstaller "basic-pitch[onnx]"

if (-not $SkipFfmpegDownload) {
    Section "Vendoring ffmpeg.exe"
    if (-not (Test-Path $ffmpegExe)) {
        New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null
        $zipUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"
        $zipPath = Join-Path $env:TEMP "ffmpeg-build.zip"
        Write-Host "  downloading $zipUrl"
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
        $extractRoot = Join-Path $env:TEMP "ffmpeg-extract"
        if (Test-Path $extractRoot) { Remove-Item -Recurse -Force $extractRoot }
        Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force
        $inner = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
        Copy-Item (Join-Path $inner.FullName "bin\ffmpeg.exe") $ffmpegExe -Force
        Remove-Item $zipPath -Force
        Remove-Item -Recurse -Force $extractRoot
        Write-Host "  vendored at $ffmpegExe"
    } else {
        Write-Host "  already vendored at $ffmpegExe"
    }
}

if (-not $SkipWebBuild) {
    Section "Building frontend (Next.js static export)"
    # The lockfile lives at repo root because apps/web is a npm workspace.
    # Install from root so node_modules end up at apps/web/node_modules.
    Push-Location $repoRoot
    try {
        npm ci
    } finally {
        Pop-Location
    }
    Push-Location $webDir
    try {
        $env:NEXT_OUTPUT = "export"
        $env:NEXT_PUBLIC_API_BASE_URL = ""
        npm run build
    } finally {
        Pop-Location
    }
}

if (-not $SkipBackendBuild) {
    Section "Freezing backend with PyInstaller"
    Push-Location $repoRoot
    try {
        & $venvPy -m PyInstaller --clean --noconfirm (Join-Path $installerDir "melody-sheet.spec")
    } finally {
        Pop-Location
    }
}

if (Test-Path $IsccPath) {
    Section "Building Inno Setup installer"
    Push-Location $installerDir
    try {
        & $IsccPath "melody-sheet.iss"
    } finally {
        Pop-Location
    }
    $artifact = Join-Path $installerDir "out\MelodySheet-Setup.exe"
    if (Test-Path $artifact) {
        $size = (Get-Item $artifact).Length / 1MB
        $sizeMb = [math]::Round($size, 1)
        Write-Host ""
        Write-Host "Built: $artifact ($sizeMb MB)" -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "PyInstaller bundle ready at dist\MelodySheet\MelodySheet.exe" -ForegroundColor Green
    Write-Host "Install Inno Setup 6 and re-run to produce the .exe installer." -ForegroundColor Yellow
}
