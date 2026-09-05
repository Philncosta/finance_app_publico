@echo off
REM ============================================================
REM  Painel Financeiro — atalho para abrir o app
REM  E so dar DUPLO CLIQUE neste arquivo.
REM ============================================================
REM  O que ele faz, passo a passo:
REM    1. entra na pasta do projeto
REM    2. confere se o ambiente (.venv) existe
REM    3. sobe o Streamlit, que abre o app no navegador
REM ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  [!] O ambiente Python ainda nao foi criado.
    echo.
    echo  Abra o Prompt de Comando nesta pasta e rode:
    echo.
    echo      python -m venv .venv
    echo      .venv\Scripts\python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo  Abrindo o Painel Financeiro...
echo.
echo  No navegador:  http://localhost:8501
echo  De outro aparelho na mesma rede, use o endereco que aparece abaixo.
echo.
echo  Para FECHAR o app, feche esta janela preta ou aperte Ctrl+C.
echo.

.venv\Scripts\python -m streamlit run app.py

pause
