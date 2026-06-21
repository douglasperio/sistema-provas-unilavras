@echo off
:: Requer execução como Administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Solicitando permissao de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo Liberando porta 5001 no Firewall do Windows...
netsh advfirewall firewall delete rule name="Flask Sistema de Provas 5001" >nul 2>&1
netsh advfirewall firewall add rule name="Flask Sistema de Provas 5001" dir=in action=allow protocol=TCP localport=5001

echo.
echo ============================================
echo  Porta 5001 liberada com sucesso!
echo  Agora reinicie o iniciar.bat normalmente.
echo ============================================
echo.
pause
