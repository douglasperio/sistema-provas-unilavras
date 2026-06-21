@echo off
echo Parando o servidor do Sistema de Provas...
taskkill /f /im pythonw.exe > nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq app*" > nul 2>&1
:: Mata qualquer python usando a porta 5001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5001"') do (
    taskkill /f /pid %%a > nul 2>&1
)
echo [OK] Servidor parado.
echo.
pause
