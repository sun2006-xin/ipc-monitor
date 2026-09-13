param(
    [switch]$SkipConsoleTest,
    [int]$SelfTestSeconds = 25
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $projectRoot 'dist'
$buildDir = Join-Path $projectRoot 'build'
$specPath = Join-Path $projectRoot 'IPC-Monitor.spec'
$mainPath = Join-Path $projectRoot 'main.py'
Set-Location -LiteralPath $projectRoot

$common = @(
    '--noconfirm', '--clean', '--onefile', '--name', 'IPC-Monitor',
    '--collect-all=dlib', '--collect-all=cv2',
    '--hidden-import=PyQt5.QtCore', '--hidden-import=PyQt5.QtGui',
    '--hidden-import=PyQt5.QtWidgets', '--hidden-import=PyQt5.QtSvg',
    '--hidden-import=PyQt5.QtMultimedia', '--hidden-import=cv2.data',
    '--hidden-import=numpy.core._multiarray_umath', '--hidden-import=dlib',
    '--hidden-import=PIL.Image',
    '--add-data', 'best.onnx;.',
    '--add-data', 'models;models', '--add-data', 'resources;resources',
    '--exclude-module=tkinter', '--exclude-module=test', '--exclude-module=lib2to3',
    '--exclude-module=torch', '--exclude-module=torchvision', '--exclude-module=torchaudio',
    '--exclude-module=ultralytics', '--exclude-module=scipy', '--exclude-module=pandas',
    '--exclude-module=seaborn', '--exclude-module=matplotlib',
    '--distpath', $distDir, '--workpath', $buildDir
)

function Invoke-PyInstaller([string]$mode) {
    & python -m PyInstaller @common $mode $mainPath
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller $mode failed: $LASTEXITCODE" }
}

Write-Host '[1/5] Checking PyInstaller'
& python -m PyInstaller --version
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller is not installed' }

Write-Host '[2/5] Cleaning previous build outputs'
if (Test-Path -LiteralPath $buildDir) { Remove-Item -LiteralPath $buildDir -Recurse -Force }
if (Test-Path -LiteralPath $distDir) { Remove-Item -LiteralPath $distDir -Recurse -Force }
if (Test-Path -LiteralPath $specPath) { Remove-Item -LiteralPath $specPath -Force }

if (-not $SkipConsoleTest) {
    Write-Host '[3/5] Building and testing console executable'
    Invoke-PyInstaller '--console'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot 'selftest.ps1') -Seconds $SelfTestSeconds -DistDir $distDir
    if ($LASTEXITCODE -ne 0) { throw "Console self-test failed: $LASTEXITCODE" }
}

Write-Host '[4/5] Building windowed release'
if (Test-Path -LiteralPath $buildDir) { Remove-Item -LiteralPath $buildDir -Recurse -Force }
$releaseExe = Join-Path $distDir 'IPC-Monitor.exe'
if (Test-Path -LiteralPath $releaseExe) { Remove-Item -LiteralPath $releaseExe -Force }
Invoke-PyInstaller '--windowed'

Write-Host '[5/5] Verifying artifact'
if (-not (Test-Path -LiteralPath $releaseExe)) { throw "Missing artifact: $releaseExe" }
$artifact = Get-Item -LiteralPath $releaseExe
Write-Host ("BUILD_OK path={0} bytes={1}" -f $artifact.FullName, $artifact.Length)
