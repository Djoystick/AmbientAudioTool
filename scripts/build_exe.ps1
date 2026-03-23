$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$buildDir = Join-Path $repoRoot "build"
$distDir = Join-Path $repoRoot "dist"
$specPath = Join-Path $repoRoot "ambient_audio_tool_gui.spec"

Write-Host "Cleaning previous build output..."
if (Test-Path $buildDir) {
    Remove-Item -Recurse -Force $buildDir
}
if (Test-Path $distDir) {
    Remove-Item -Recurse -Force $distDir
}

Write-Host "Building EXE with PyInstaller..."
python -m PyInstaller --noconfirm --clean $specPath

$exePath = Join-Path $distDir "AmbientAudioTool\AmbientAudioTool.exe"
Write-Host ""
Write-Host "Build completed."
Write-Host "Output folder: $distDir\AmbientAudioTool"
Write-Host "Executable: $exePath"
