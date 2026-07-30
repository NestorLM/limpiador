# Optimizador de Windows

Aplicación de limpieza y optimización para Windows, creada con Python + Tkinter.

## Funcionalidades

- Interfaz gráfica con tema claro/oscuro automático.
- Métricas en vivo de CPU y RAM (sparklines).
- Comparativa antes/después de espacio libre y RAM usada.
- Tareas seleccionables:
  - Limpieza de temporales.
  - Limpieza de caché DNS.
  - Activación de plan de energía de máximo rendimiento.
  - Optimización de disco (TRIM/defrag según corresponda).
  - Vaciado de papelera.
  - Actualización de apps con winget.
  - Análisis del registro (modo informativo, no destructivo).

## Estructura del proyecto

- `optimizador_windows.py`: código principal de la aplicación.
- `build.bat`: script de compilación para generar `.exe`.
- `optimizador_windows.spec`: configuración de PyInstaller.
- `requirements.txt`: dependencias de Python (actualmente sin librerías externas).

## Requisitos

- Windows 10 o superior.
- Python 3.10+.

## Ejecutar en modo desarrollo

```bash
python optimizador_windows.py
```

Se recomienda ejecutar como administrador para que todas las tareas funcionen correctamente.

## Compilar a ejecutable

1. Instala PyInstaller:

```bash
pip install pyinstaller
```

2. Ejecuta:

```bat
build.bat
```

3. El ejecutable quedará en `dist/OptimizadorWindows.exe`.

## Publicar en GitHub

Si ya tienes GitHub CLI autenticado (`gh auth login`), puedes publicar en un solo flujo:

```bash
git init
git add .
git commit -m "feat: publicación inicial de Optimizador de Windows"
gh repo create optimizador-windows --public --source . --remote origin --push
```

Si no usas GitHub CLI, crea el repo en la web y luego ejecuta:

```bash
git init
git add .
git commit -m "feat: publicación inicial de Optimizador de Windows"
git branch -M main
git remote add origin <URL_DEL_REPO>
git push -u origin main
```