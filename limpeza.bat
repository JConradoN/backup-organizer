@echo off
:: Define a pasta base onde o .bat está localizado
SET BASE_DIR=%~dp0
set PYTHONPATH=%BASE_DIR%src
set LOG_SESSAO="%BASE_DIR%logs\sessao_completa.log"

:: Cria a pasta de logs se ela não existir
if not exist "%BASE_DIR%logs" mkdir "%BASE_DIR%logs"

cls
echo ============================================================
echo           BACKUP ORGANIZER - SISTEMA DE AUDITORIA
echo ============================================================
echo.
echo [1/4] 🧠 Classificando novos arquivos...
python "%BASE_DIR%src\main.py" --fonte G:\ --destino F:\ --dry-run --apenas-classify >> %LOG_SESSAO% 2>&1

echo [2/4] 📝 Gerando lista de copia incremental...
python "%BASE_DIR%src\gerar_robocopy.py" >> %LOG_SESSAO% 2>&1

if not exist "%BASE_DIR%src\robocopy_run.bat" (
    echo.
    echo ℹ️  Nada novo para copiar ou arquivos ja estao no destino.
    echo Verifique o log: %LOG_SESSAO%
    pause
    exit /b
)

echo [3/4] 🚀 Executando Robocopy com Auditoria...
echo (Acompanhe a copia abaixo)
echo ------------------------------------------------------------
pushd "%BASE_DIR%src"
call robocopy_run.bat
popd

echo.
echo [4/4] ✅ Atualizando Banco de Dados...
python "%BASE_DIR%src\marcar_copiados.py" >> %LOG_SESSAO% 2>&1

echo.
echo ============================================================
echo 🏁 PROCESSO CONCLUIDO!
echo Auditoria completa em: %LOG_SESSAO%
echo Detalhes dos arquivos em: %BASE_DIR%logs\robocopy_detalhado.log
echo ============================================================
pause