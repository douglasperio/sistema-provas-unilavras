@echo off
echo ============================================
echo  Configurar Inicializacao Automatica
echo  Sistema de Provas - Unilavras
echo ============================================
echo.

:: Remover tarefa antiga (se existir)
schtasks /delete /tn "SistemaProvasUnilavras" /f > nul 2>&1

:: Usar PowerShell para criar atalho na pasta Startup
:: (PowerShell lida corretamente com caminhos acentuados)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$src = '%~dp0iniciar_oculto.vbs';" ^
  "$lnk = [System.IO.Path]::Combine($env:APPDATA, 'Microsoft\Windows\Start Menu\Programs\Startup\SistemaProvasUnilavras.lnk');" ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut($lnk);" ^
  "$s.TargetPath = 'wscript.exe';" ^
  "$s.Arguments = \"\`\"$src\`\"\";" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.WindowStyle = 7;" ^
  "$s.Description = 'Sistema de Provas Unilavras';" ^
  "$s.Save();" ^
  "Write-Host 'Atalho criado: ' $lnk"

if %errorlevel% == 0 (
    echo.
    echo [OK] Inicializacao automatica configurada!
    echo.
    echo O sistema iniciara automaticamente ao fazer
    echo login no Windows. Aguarde ~20 segundos apos
    echo ligar o PC e acesse: http://localhost:5001
    echo.
    echo Para remover: execute remover_inicializacao.bat
) else (
    echo.
    echo [ERRO] Falha ao configurar.
    echo Tente executar como Administrador.
)

echo.
pause
