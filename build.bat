@echo off
setlocal

echo ======================================================
echo      Compilador para Optimizador de Windows
echo ======================================================
echo.

REM Comprueba si pyinstaller está instalado
py -3 -m PyInstaller --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller no está instalado o no se encuentra en el PATH.
    echo Por favor, instálalo con: pip install pyinstaller
    goto :eof
)

echo [INFO] Limpiando compilaciones anteriores...
if exist "dist" (
    echo      - Eliminando directorio 'dist'
    rd /s /q "dist"
)
if exist "build" (
    echo      - Eliminando directorio 'build'
    rd /s /q "build"
)

echo [INFO] Compilando optimizador_windows.py en un solo ejecutable...
py -3 -m PyInstaller --clean --onefile --windowed --name OptimizadorWindows --icon=NONE optimizador_windows.py

echo.
echo [SUCCESS] Proceso de compilación completado.
echo El ejecutable se encuentra en la carpeta 'dist'.
echo.
pause