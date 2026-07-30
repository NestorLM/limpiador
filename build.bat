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

echo [INFO] Compilando optimizador_windows.py en un solo ejecutable...
py -3 -m PyInstaller --clean --onefile --windowed --name OptimizadorWindows --icon=NONE optimizador_windows.py

echo.
echo [SUCCESS] Proceso de compilación completado.
echo El ejecutable se encuentra en la carpeta 'dist'.
echo.
pause