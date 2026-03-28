# Обновление репозитория и зависимостей (Windows, из корня проекта)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
git fetch origin
git pull origin main
if (Test-Path .\.venv\Scripts\Activate.ps1) {
    & .\.venv\Scripts\Activate.ps1
}
pip install -r requirements.txt
Write-Host "Готово. Перезапустите бота (python -m bot.main)."
