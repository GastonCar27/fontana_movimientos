@echo off
setlocal enabledelayedexpansion

rem =========================================================
rem  Sube los cambios locales de fontana_movimientos a GitHub
rem  (Paso "Windows" de guia_despliegue_git.docx)
rem =========================================================

cd /d "C:\Users\Gaston C\fontana_movimientos"
if errorlevel 1 (
    echo No se encontro la carpeta del proyecto. Revisa la ruta dentro de este script.
    pause
    exit /b 1
)

echo ===============================================
echo  Subiendo cambios de fontana_movimientos a GitHub
echo ===============================================
echo.
echo Carpeta: %cd%
echo.
echo Cambios detectados:
git status --short
echo.

set "MENSAJE="
set /p MENSAJE="Mensaje del commit (Enter para usar uno generico con fecha/hora): "
if "%MENSAJE%"=="" (
    set "MENSAJE=Actualizacion %date% %time%"
)

git add .
git commit -m "%MENSAJE%"
if errorlevel 1 (
    echo.
    echo No habia cambios para commitear (o el commit fallo). Nada para subir.
    pause
    exit /b 0
)

echo.
echo --- git push ---
git push
if errorlevel 1 (
    echo.
    echo El push fallo. Revisa la conexion a internet o las credenciales de GitHub
    echo ^(usuario/token, o iniciar sesion de nuevo en GitHub Desktop^).
    pause
    exit /b 1
)

echo.
echo Listo: cambios subidos a GitHub.
echo Ahora corre deploy_ubuntu.sh en el servidor para bajarlos.
pause
