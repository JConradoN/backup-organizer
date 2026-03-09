$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$iss = Join-Path $root 'installer\BackupOrganizerLite.iss'

$isccCandidates = @(
  'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
  'C:\Program Files\Inno Setup 6\ISCC.exe',
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)

$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
  $keys = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
  )
  $inno = Get-ItemProperty $keys -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like '*Inno Setup*' } |
    Select-Object -First 1
  if ($inno -and $inno.InstallLocation) {
    $candidate = Join-Path $inno.InstallLocation 'ISCC.exe'
    if (Test-Path $candidate) {
      $iscc = $candidate
    }
  }
}

if (!(Test-Path $iscc)) {
  throw "ISCC.exe nao encontrado em: $iscc"
}

if (!(Test-Path (Join-Path $root 'dist\BackupOrganizerLite\BackupOrganizerLite.exe'))) {
  throw "Executavel LITE nao encontrado. Gere antes com build_exe_lite.ps1"
}

& $iscc $iss
Write-Host "Setup LITE gerado em: $root\dist\BackupOrganizerLite_Setup.exe"
