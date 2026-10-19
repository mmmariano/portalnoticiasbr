@echo off
title Deletar todos os arquivos do repositorio
cd /d "C:\Users\mtema\OneDrive\Desktop\portalnoticiasbr"

echo ========================================
echo   DELETAR TODOS OS ARQUIVOS DO REPOSITORIO
echo ========================================
echo.
echo ATENCAO: isto apaga todos os arquivos da pasta e do GitHub
echo (exceto push.cmd e deletar-tudo.cmd).
echo O historico de commits continua no Git, mas os arquivos somem
echo da versao atual.
echo.
set /p RESP=Para continuar, digite DELETAR e pressione Enter: 
if not "%RESP%"=="DELETAR" (
    echo.
    echo Cancelado. Nada foi apagado.
    pause
    exit /b
)

echo.
echo Removendo arquivos...
for /f "delims=" %%F in ('git ls-files') do (
    if /i not "%%F"=="push.cmd" if /i not "%%F"=="deletar-tudo.cmd" git rm -f -q -- "%%F"
)

git diff --cached --quiet
if %errorlevel%==0 (
    echo.
    echo Nenhum arquivo para remover.
    pause
    exit /b
)

git commit -m "Remove todos os arquivos"
if errorlevel 1 (
    echo.
    echo ERRO ao criar o commit.
    pause
    exit /b 1
)

git push origin main
if not errorlevel 1 goto ok

echo.
echo O GitHub recusou o envio.
set /p RESP2=Sobrescrever o GitHub com a versao local? (S/N): 
if /i "%RESP2%"=="S" (
    git push --force-with-lease origin main
    if not errorlevel 1 goto ok
)

echo.
echo ERRO ao enviar para o GitHub.
pause
exit /b 1

:ok
echo.
echo ========================================
echo   ARQUIVOS REMOVIDOS COM SUCESSO!
echo ========================================
echo.
pause