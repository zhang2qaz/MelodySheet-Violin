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
      6. Inno Setup compiles dist\MelodySheet -> installer\out\MelodySheet-Setup.exe

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
    Write-Warning "Inno Setup compiler not found at $IsccPath. The .exe step will be skipped -- adjust -IsccPath or install Inno Setup 6."
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
        $zipPath = Join-Path $env:TEMP "ffmpeg-build.zip"
        # Multiple mirrors — BtbN's CDN occasionally 404s on GH Actions runners.
        # gyan.dev is the canonical Windows ffmpeg builder, with stable URLs.
        $mirrors = @(
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
            "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
            "https://github.com/GyanD/codexffmpeg/releases/latest/download/ffmpeg-release-essentials.zip"
        )
        $downloaded = $false
        foreach ($zipUrl in $mirrors) {
            Write-Host "  trying $zipUrl"
            # curl.exe is shipped with Windows 10+ and follows redirects more
            # reliably than Invoke-WebRequest. -fL = follow + fail on 4xx.
            & curl.exe -fL --connect-timeout 30 --max-time 600 --retry 3 --retry-delay 5 `
                -o $zipPath $zipUrl
            if ($LASTEXITCODE -eq 0 -and (Test-Path $zipPath) -and (Get-Item $zipPath).Length -gt 1MB) {
                Write-Host "  downloaded successfully ($((Get-Item $zipPath).Length) bytes)"
                $downloaded = $true
                break
            }
            Write-Host "  mirror failed (exit=$LASTEXITCODE), trying next"
            Remove-Item -Force -ErrorAction SilentlyContinue $zipPath
        }
        if (-not $downloaded) {
            throw "All ffmpeg mirrors failed."
        }
        $extractRoot = Join-Path $env:TEMP "ffmpeg-extract"
        if (Test-Path $extractRoot) { Remove-Item -Recurse -Force $extractRoot }
        Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force
        # Find ffmpeg.exe anywhere in the extracted tree (the layout differs
        # between BtbN and gyan.dev builds).
        $ffmpegSource = Get-ChildItem -Path $extractRoot -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $ffmpegSource) {
            throw "ffmpeg.exe not found in extracted archive."
        }
        Copy-Item $ffmpegSource.FullName $ffmpegExe -Force
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
        # PowerShell gotcha: `$env:VAR = ""` is treated as Remove-Item env:VAR
        # in some PS versions, which leaves the variable UNDEFINED when
        # `next build` reads it. Use the .NET API to force a true empty
        # string into the process environment. The api.ts code now also
        # treats production+undefined as same-origin so we have double
        # protection, but we still want the env var to behave correctly.
        [System.Environment]::SetEnvironmentVariable("NEXT_OUTPUT", "export", "Process")
        [System.Environment]::SetEnvironmentVariable("NEXT_PUBLIC_API_BASE_URL", "", "Process")
        # Sanity check — surface the env state to build logs so we don't ever
        # silently regress this. If the var is missing here the installer's
        # bundled JS will hardcode http://localhost:8000.
        $envVal = [System.Environment]::GetEnvironmentVariable("NEXT_PUBLIC_API_BASE_URL", "Process")
        if ($null -eq $envVal) {
            Write-Host "[build] WARNING: NEXT_PUBLIC_API_BASE_URL is null after SetEnvironmentVariable — same-origin fallback in api.ts will kick in." -ForegroundColor Yellow
        } else {
            Write-Host "[build] NEXT_PUBLIC_API_BASE_URL='$envVal' (len=$($envVal.Length))"
        }
        npm run build

        # =====================================================================
        # POST-BUILD GUARD — the killer regression check.
        #
        # History: we have shipped TWO bad installers in a row that hardcoded
        # http://localhost:8000 into the bundled JS, even though api.ts looked
        # correct in source. Root cause was PowerShell silently turning
        # `$env:VAR = ""` into Remove-Item, so the prod build saw env=undefined
        # and fell through to the localhost fallback.
        #
        # Even with all the source-level defenses, ONLY a post-build artifact
        # check can prove the shipped JS is correct. If you ever see this guard
        # fire in CI, do NOT ship the installer — something in the build chain
        # changed and the fallback URL is back in the bundle.
        # =====================================================================
        $outDir = Join-Path $webDir "out"
        if (-not (Test-Path $outDir)) {
            # NOTE: do not use backticks in PowerShell strings — they are the
            # escape character, NOT a quote marker. Past version of this file
            # had backticks around 'next build' and broke the parser entirely.
            throw "[build] Static export missing at $outDir -- next build did not produce out/."
        }
        $offender = Get-ChildItem -Path $outDir -Recurse -Include *.js,*.html -ErrorAction SilentlyContinue |
            Select-String -Pattern "localhost:8000" -List -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $offender) {
            throw "[build] FATAL: 'localhost:8000' found in shipped bundle at $($offender.Path):$($offender.LineNumber). The installer would point at the wrong API. Refusing to package."
        }
        Write-Host "[build] Post-build URL guard passed — no localhost:8000 in shipped JS." -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

if (-not $SkipBackendBuild) {
    Section "Freezing backend with PyInstaller"
    Push-Location $repoRoot
    try {
        & $venvPy -m PyInstaller --clean --noconfirm (Join-Path $installerDir "melody-sheet.spec")
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller exited with code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
    $frozenExe = Join-Path $repoRoot "dist\MelodySheet\MelodySheet.exe"
    if (-not (Test-Path $frozenExe)) {
        throw "PyInstaller finished but did not produce $frozenExe."
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
        # Use -f format operator: `MB` inside a double-quoted string trips
        # PowerShell's numeric-suffix parser (1MB = 1048576) even when it's
        # just literal text.
        Write-Host ("Built: {0} ({1} MB)" -f $artifact, $sizeMb) -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "PyInstaller bundle ready at dist\MelodySheet\MelodySheet.exe" -ForegroundColor Green
    Write-Host "Install Inno Setup 6 and re-run to produce the .exe installer." -ForegroundColor Yellow
}
