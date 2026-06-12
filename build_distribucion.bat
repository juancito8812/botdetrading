@echo off
cd /d "%~dp0"
echo ============================================
echo  MiBotTrading - Build Distribucion
echo ============================================
echo.

:: Activar entorno virtual
echo Activando entorno virtual...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo ERROR: No se encuentra el entorno virtual (venv)
    pause
    exit /b 1
)

echo.
echo PASO 1: Compilar .exe con PyInstaller...
pyinstaller MiBotTrading.spec --clean
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller fallo.
    pause
    exit /b 1
)
echo OK - .exe compilado.
echo.
echo PASO 2: Copiar archivos limpios a dist/...
copy /Y dist\.env dist\.env.tmp >nul 2>&1
copy /Y dist\config.json dist\config.json.tmp >nul 2>&1
if exist "C:\Program Files (x86)\Inno Setup 6\iscc.exe" (
    echo.
    echo PASO 3: Generando instalador con Inno Setup...
    "C:\Program Files (x86)\Inno Setup 6\iscc.exe" Installer_Script.iss
    if %errorlevel% equ 0 (
        echo OK - Instalador generado.
    ) else (
        echo NOTA: Inno Setup fallo. Puedes compilar manualmente.
    )
) else (
    echo.
    echo PASO 3: Inno Setup no encontrado.
    echo Para generar instalador, instala Inno Setup desde:
    echo   https://jrsoftware.org/isdl.php
    echo Luego ejecuta: iscc Installer_Script.iss
)

echo.
echo ============================================
echo  DISTRIBUCION LISTA
echo ============================================
echo.
echo Contenido de dist/:
dir dist\*.* 2>nul
echo.
echo Para distribucion manual:
echo   - Comprime la carpeta dist/ como ZIP
echo   - O ejecuta el instalador (si se genero)
echo.
pause
