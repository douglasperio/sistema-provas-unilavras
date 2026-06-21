@echo off
chcp 65001 > nul
cd /d "%~dp0"

if not exist ".venv" (
    echo Criando ambiente virtual...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Instalando dependencias...
pip install -r requirements.txt -q

echo.
echo ============================================
echo  Sistema de Provas - Unilavras
echo  Acesse: http://localhost:5001
echo  Celular: veja o IP na janela do Python
echo ============================================
echo.

python app.py
pause
