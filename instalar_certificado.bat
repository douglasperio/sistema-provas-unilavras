@echo off
chcp 65001 > nul
set "PASTA=%~dp0"

echo.
echo  ================================================
echo   Instalacao do Certificado HTTPS - Sis. Provas
echo  ================================================
echo.

REM Verifica se o cert.pem existe
if not exist "%PASTA%cert.pem" (
    echo  AVISO: cert.pem nao encontrado.
    echo.
    echo  Siga estes passos:
    echo    1. Inicie o servidor pelo iniciar.bat
    echo    2. Aguarde aparecer o IP no terminal
    echo    3. Feche o servidor ^(Ctrl+C^)
    echo    4. Execute este arquivo novamente
    echo.
    pause
    exit /b 1
)

echo  Instalando certificado na loja de confianca do Windows...
echo  ^(isso elimina o aviso de "conexao nao segura" no Edge e Chrome^)
echo.

certutil -addstore -user "Root" "%PASTA%cert.pem"

if %errorlevel% == 0 (
    echo.
    echo  ================================================
    echo   Certificado instalado com sucesso!
    echo  ================================================
    echo.
    echo  Proximos passos:
    echo    1. Feche TODAS as janelas do Edge/Chrome
    echo    2. Reabra o navegador
    echo    3. Acesse https://localhost:5001 ou https://IP:5001
    echo    4. O aviso nao aparecera mais neste computador
    echo.
    echo  No celular: acesse pelo Chrome Android, toque em
    echo  "Avancado" e depois "Continuar para o site".
    echo.
) else (
    echo.
    echo  ERRO ao instalar o certificado.
    echo  Tente clicar com botao direito neste arquivo
    echo  e escolher "Executar como administrador".
    echo.
)

pause
