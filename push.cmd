@echo off
title Atualizar Portal de Noticias BR - GitHub
cd /d "C:\Users\mtema\OneDrive\Desktop\portalnoticiasbr"

echo ========================================
echo   ATUALIZANDO PROJETO NO GITHUB
echo ========================================
echo.

git init
git branch -M main
git remote add origin https://github.com/mmmariano/portalnoticiasbr.git
git fetch origin
git reset origin/main
git add .
git commit -m "Atualizacao do site"
git push origin main

git add .

git diff --cached --quiet
if %errorlevel%==0 (
    echo Nenhuma alteracao nova para enviar.
    pause
    exit /b
)

git commit -m "Atualizacao do site"
if errorlevel 1 (
    echo.
    echo ERRO ao criar o commit.
    pause
    exit /b 1
)

git push origin main
if not errorlevel 1 goto ok

echo.
echo O GitHub recusou o envio. Tentando integrar as mudancas do remoto...
git pull --rebase origin main
if not errorlevel 1 (
    git push origin main
    if not errorlevel 1 goto ok
)
git rebase --abort 2>nul

echo.
echo Nao foi possivel integrar automaticamente.
echo Se o que esta no GitHub pode ser substituido pela sua pasta local, digite S.
set /p RESP=Sobrescrever o GitHub com a versao local? (S/N): 
if /i "%RESP%"=="S" (
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
echo   PUSH REALIZADO COM SUCESSO!
echo ========================================
echo.
pause