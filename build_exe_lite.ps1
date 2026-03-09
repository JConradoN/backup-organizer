$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = "C:/Users/morph/dev-tools/backup-organizer/venv/Scripts/python.exe"

Write-Host "[1/2] Garantindo PyInstaller..."
& $python -m pip install --upgrade pyinstaller

Write-Host "[2/2] Gerando executavel LITE (sem OCR pesado)..."
& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --name BackupOrganizerLite `
  --copy-metadata streamlit `
  --exclude-module torch `
  --exclude-module torchvision `
  --exclude-module torchaudio `
  --exclude-module easyocr `
  --exclude-module cv2 `
  --add-data "src;src" `
  --add-data "docs;docs" `
  --add-data "requirements.txt;." `
  src/app_launcher.py

Write-Host "Build LITE concluido em: $root\dist\BackupOrganizerLite"
