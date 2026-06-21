@echo off
echo Removendo inicializacao automatica...

:: Remover atalho da pasta Startup
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lnk = [System.IO.Path]::Combine($env:APPDATA, 'Microsoft\Windows\Start Menu\Programs\Startup\SistemaProvasUnilavras.lnk');" ^
  "if (Test-Path $lnk) { Remove-Item $lnk; Write-Host '[OK] Atalho removido.' } else { Write-Host '[AVISO] Atalho nao encontrado.' }"

:: Remover tarefa antiga (se existir de versao anterior)
schtasks /delete /tn "SistemaProvasUnilavras" /f > nul 2>&1

echo.
pause
