$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = "C:/Users/morph/dev-tools/backup-organizer/venv/Scripts/python.exe"

Write-Host "[1/3] Instalando pyinstaller..."
& $python -m pip install --upgrade pyinstaller

Write-Host "[2/3] Gerando executavel..."
& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --name BackupOrganizer `
  --copy-metadata streamlit `
  --add-data "src;src" `
  --add-data "docs;docs" `
  --add-data "requirements.txt;." `
  src/app_launcher.py

Write-Host "[3/3] Build concluido em: $root\dist\BackupOrganizer"
