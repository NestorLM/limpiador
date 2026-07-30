import ctypes
import os
import re
import winreg
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from collections import deque
from time import perf_counter
from tkinter import messagebox, scrolledtext, ttk


ULTIMATE_PERFORMANCE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def formatear_bytes(valor: int) -> str:
    if valor is None:
        return "N/A"

    unidades = ["B", "KB", "MB", "GB", "TB"]
    numero = float(valor)
    for unidad in unidades:
        if numero < 1024 or unidad == unidades[-1]:
            return f"{numero:.2f} {unidad}"
        numero /= 1024


def capturar_cpu_usage() -> int:
    """Captura el uso de CPU del sistema usando WMIC."""
    try:
        # WMIC es más lento pero no requiere dependencias externas como psutil
        output = subprocess.check_output("wmic cpu get loadpercentage", shell=True, text=True, stderr=subprocess.DEVNULL)
        return int(output.strip().split("\n")[1])
    except Exception:
        return 0


def capturar_ram() -> dict:
    estado = MEMORYSTATUSEX()
    estado.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado))
    total = int(estado.ullTotalPhys)
    libre = int(estado.ullAvailPhys)
    usada = total - libre
    return {
        "total": total,
        "usada": usada,
        "porcentaje": int(estado.dwMemoryLoad),
    }


def capturar_espacio_libre() -> int:
    unidad = os.environ.get("SystemDrive", "C:") + "\\"
    uso = shutil.disk_usage(unidad)
    return int(uso.free)


def formatear_delta_bytes(delta: int) -> str:
    signo = "+" if delta >= 0 else "-"
    return f"{signo}{formatear_bytes(abs(delta))}"


def formatear_segundos(segundos: float) -> str:
    return f"{segundos:.2f}s"


def es_windows() -> bool:
    return sys.platform == "win32"


def es_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def es_tema_oscuro_windows() -> bool:
    """Verifica si el usuario está usando el modo oscuro en Windows."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        # AppsUseLightTheme es 0 para modo oscuro, 1 para modo claro.
        valor, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return valor == 0
    except Exception:
        # Si falla la detección, se asume el tema claro por defecto.
        return False


def relanzar_como_admin() -> bool:
    """Relanza el script con elevación UAC."""
    try:
        params = " ".join(f'"{arg}"' for arg in sys.argv)
        resultado = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1,
        )
        return resultado > 32
    except Exception:
        return False


class OptimizadorUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Optimizador de Windows")
        self.root.geometry("860x640")
        self.root.minsize(760, 580)

        self.en_ejecucion = False
        self.progreso = tk.IntVar(value=0)
        self.estado = tk.StringVar(value="Listo para optimizar")
        tema_defecto = "Oscuro" if es_tema_oscuro_windows() else "Claro"
        self.tema = tk.StringVar(value=tema_defecto)

        self.metric_espacio = tk.StringVar(value="Espacio libre: -")
        self.metric_ram = tk.StringVar(value="RAM usada: -")
        self.metric_tiempo = tk.StringVar(value="Tiempo total: -")

        self.var_temp = tk.BooleanVar(value=True)
        self.var_dns = tk.BooleanVar(value=True)
        self.var_energia = tk.BooleanVar(value=True)
        self.var_disco = tk.BooleanVar(value=True)
        self.var_papelera = tk.BooleanVar(value=True)
        self.var_analisis = tk.BooleanVar(value=True)
        self.var_winget = tk.BooleanVar(value=True)
        self.var_registro = tk.BooleanVar(value=False)

        self.snapshot_antes = None
        self.bytes_liberados_temp = 0

        # Historial para sparklines
        self.hist_cpu = deque([0] * 50, maxlen=50)
        self.hist_ram = deque([0] * 50, maxlen=50)

        self._crear_ui()
        self._aplicar_tema(self.tema.get())
        self._iniciar_monitor_recursos()

    def _crear_ui(self):
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass

        contenedor = ttk.Frame(self.root, padding=16, style="App.TFrame")
        contenedor.pack(fill="both", expand=True)

        cabecera = ttk.Frame(contenedor, style="Card.TFrame", padding=14)
        cabecera.pack(fill="x", pady=(0, 10))

        cab_izq = ttk.Frame(cabecera, style="Card.TFrame")
        cab_izq.pack(side="left", fill="x", expand=True)

        titulo = ttk.Label(cab_izq, text="Optimizador de Windows", style="Title.TLabel")
        titulo.pack(anchor="w")

        subtitulo = ttk.Label(
            cab_izq,
            text="Limpieza y optimización con progreso en vivo y métricas antes/después.",
            style="Sub.TLabel",
        )
        subtitulo.pack(anchor="w", pady=(2, 0))

        cab_der = ttk.Frame(cabecera, style="Card.TFrame")
        cab_der.pack(side="right", padx=(12, 0))
        ttk.Label(cab_der, text="Tema", style="Sub.TLabel").pack(anchor="e")
        combo_tema = ttk.Combobox(
            cab_der,
            state="readonly",
            width=12,
            values=["Oscuro", "Claro"],
            textvariable=self.tema,
        )
        combo_tema.pack(anchor="e", pady=(4, 0))
        combo_tema.bind("<<ComboboxSelected>>", self._on_cambio_tema)

        if not es_admin():
            aviso = ttk.Label(
                contenedor,
                text="No estás como administrador. Algunas tareas pueden fallar.",
                style="Warning.TLabel",
            )
            aviso.pack(anchor="w", pady=(0, 8))

        metricas = ttk.Frame(contenedor, style="Card.TFrame", padding=12)
        metricas.pack(fill="x", pady=(0, 10))
        metricas.columnconfigure(1, weight=1)

        # Contenedor para métricas de texto
        metricas_texto = ttk.Frame(metricas, style="Card.TFrame")
        metricas_texto.grid(row=0, column=0, sticky="nw")
        ttk.Label(metricas_texto, text="Métricas de ejecución", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(metricas_texto, textvariable=self.metric_espacio, style="Metric.TLabel").pack(anchor="w")
        ttk.Label(metricas_texto, textvariable=self.metric_ram, style="Metric.TLabel").pack(anchor="w")
        ttk.Label(metricas_texto, textvariable=self.metric_tiempo, style="Metric.TLabel").pack(anchor="w")

        # Contenedor para gráficos
        metricas_graficos = ttk.Frame(metricas, style="Card.TFrame")
        metricas_graficos.grid(row=0, column=1, sticky="nsew", padx=(20, 0))
        metricas_graficos.rowconfigure(1, weight=1)
        metricas_graficos.rowconfigure(3, weight=1)
        metricas_graficos.columnconfigure(0, weight=1)

        ttk.Label(metricas_graficos, text="CPU", style="Metric.TLabel").grid(row=0, column=0, sticky="sw")
        self.canvas_cpu = tk.Canvas(metricas_graficos, height=30, highlightthickness=0)
        self.canvas_cpu.grid(row=1, column=0, sticky="nsew", pady=(2, 8))

        ttk.Label(metricas_graficos, text="RAM", style="Metric.TLabel").grid(row=2, column=0, sticky="sw")
        self.canvas_ram = tk.Canvas(metricas_graficos, height=30, highlightthickness=0)
        self.canvas_ram.grid(row=3, column=0, sticky="nsew", pady=(2, 0))

        opciones = ttk.LabelFrame(contenedor, text="Tareas de optimización", padding=12, style="Card.TLabelframe")
        opciones.pack(fill="x")

        ttk.Checkbutton(
            opciones,
            text="Limpiar archivos temporales (usuario y sistema)",
            variable=self.var_temp,
        ).grid(row=0, column=0, sticky="w", pady=2)

        ttk.Checkbutton(
            opciones,
            text="Limpiar caché DNS",
            variable=self.var_dns,
        ).grid(row=1, column=0, sticky="w", pady=2)

        ttk.Checkbutton(
            opciones,
            text="Activar plan de energía: Máximo rendimiento",
            variable=self.var_energia,
        ).grid(row=2, column=0, sticky="w", pady=2)

        ttk.Checkbutton(
            opciones,
            text="Optimizar disco del sistema (TRIM/defrag según tipo)",
            variable=self.var_disco,
        ).grid(row=3, column=0, sticky="w", pady=2)

        ttk.Checkbutton(
            opciones,
            text="Vaciar papelera de reciclaje",
            variable=self.var_papelera,
        ).grid(row=4, column=0, sticky="w", pady=2)

        ttk.Checkbutton(
            opciones,
            text="Mostrar top procesos por CPU y memoria",
            variable=self.var_analisis,
        ).grid(row=5, column=0, sticky="w", pady=2)

        ttk.Checkbutton(
            opciones,
            text="Actualizar aplicaciones con winget",
            variable=self.var_winget,
        ).grid(row=0, column=1, sticky="w", pady=2, padx=(20, 0))

        ttk.Checkbutton(
            opciones,
            text="Limpiar registro de programas desinstalados (Experimental)",
            variable=self.var_registro,
        ).grid(row=1, column=1, sticky="w", pady=2, padx=(20, 0))

        marco_progreso = ttk.Frame(contenedor)
        marco_progreso.pack(fill="x", pady=(14, 8))

        self.barra = ttk.Progressbar(
            marco_progreso,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.progreso,
        )
        self.barra.pack(fill="x")

        self.lbl_estado = ttk.Label(marco_progreso, textvariable=self.estado)
        self.lbl_estado.pack(anchor="w", pady=(6, 0))

        botones = ttk.Frame(contenedor)
        botones.pack(fill="x", pady=(4, 10))

        self.btn_iniciar = ttk.Button(
            botones,
            text="Iniciar optimización",
            style="Primary.TButton",
            command=self.iniciar,
        )
        self.btn_iniciar.pack(side="left")

        ttk.Button(botones, text="Limpiar registro", command=self.limpiar_log).pack(side="left", padx=8)
        ttk.Button(botones, text="Salir", command=self.root.destroy).pack(side="right")

        self.log = scrolledtext.ScrolledText(
            contenedor,
            wrap="word",
            height=20,
            font=("Consolas", 10),
            state="disabled",
            relief="flat",
            borderwidth=0,
        )
        self.log.pack(fill="both", expand=True)

        self.escribir_log("Aplicación lista.")

    def _on_cambio_tema(self, _event=None):
        self._aplicar_tema(self.tema.get())

    def _aplicar_tema(self, nombre_tema: str):
        oscuro = nombre_tema == "Oscuro"
        if oscuro:
            paleta = {
                "fondo": "#0f172a",
                "card": "#111827",
                "texto": "#e5e7eb",
                "subtexto": "#94a3b8",
                "acento": "#22c55e",
                "aviso": "#fbbf24",
                "entrada": "#0b1220",
            }
        else:
            paleta = {
                "fondo": "#f3f4f6",
                "card": "#ffffff",
                "texto": "#111827",
                "subtexto": "#475569",
                "acento": "#15803d",
                "aviso": "#b45309",
                "entrada": "#f8fafc",
            }

        self.root.configure(bg=paleta["fondo"])
        estilo = ttk.Style()
        estilo.configure("App.TFrame", background=paleta["fondo"])
        estilo.configure("Card.TFrame", background=paleta["card"])
        estilo.configure(
            "Card.TLabelframe",
            background=paleta["card"],
            foreground=paleta["texto"],
            borderwidth=1,
            relief="solid",
        )
        estilo.configure(
            "Card.TLabelframe.Label",
            background=paleta["card"],
            foreground=paleta["texto"],
            font=("Segoe UI", 10, "bold"),
        )
        estilo.configure("TFrame", background=paleta["fondo"])
        estilo.configure("TLabel", background=paleta["fondo"], foreground=paleta["texto"])
        estilo.configure("Title.TLabel", background=paleta["card"], foreground=paleta["texto"], font=("Segoe UI", 18, "bold"))
        estilo.configure("Sub.TLabel", background=paleta["card"], foreground=paleta["subtexto"], font=("Segoe UI", 10))
        estilo.configure("Section.TLabel", background=paleta["card"], foreground=paleta["texto"], font=("Segoe UI", 10, "bold"))
        estilo.configure("Metric.TLabel", background=paleta["card"], foreground=paleta["texto"], font=("Segoe UI", 10))
        estilo.configure("Warning.TLabel", background=paleta["fondo"], foreground=paleta["aviso"], font=("Segoe UI", 9, "bold"))
        estilo.configure("TCheckbutton", background=paleta["card"], foreground=paleta["texto"], font=("Segoe UI", 10))
        estilo.map("TCheckbutton", background=[("active", paleta["card"])])
        estilo.configure("TProgressbar", background=paleta["acento"], troughcolor=paleta["entrada"], borderwidth=0, relief="flat")

        # Estilo para el botón primario
        estilo.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 5),
            background=paleta["acento"],
            foreground=paleta["card"],
            borderwidth=0,
        )
        estilo.map(
            "Primary.TButton",
            background=[("active", paleta["texto"]), ("!active", paleta["acento"])],
            foreground=[("active", paleta["fondo"])],
        )

        # Estilo para botones secundarios
        estilo.configure(
            "TButton",
            font=("Segoe UI", 10),
            padding=(10, 5),
            borderwidth=1,
            background=paleta["card"],
            foreground=paleta["texto"],
        )
        estilo.map(
            "TButton",
            background=[("active", paleta["entrada"]), ("hover", paleta["entrada"])],
            bordercolor=[("focus", paleta["acento"]), ("!focus", paleta["subtexto"])],
        )
        self.log.configure(
            bg=paleta["entrada"],
            fg=paleta["texto"],
            insertbackground=paleta["texto"],
            selectbackground="#2563eb" if oscuro else "#93c5fd",
            selectforeground="#ffffff" if oscuro else "#111827",
        )
        self.canvas_cpu.configure(bg=paleta["entrada"])
        self.canvas_ram.configure(bg=paleta["entrada"])

    def _iniciar_monitor_recursos(self):
        """Inicia el ciclo de actualización para los gráficos de recursos."""
        cpu_uso = capturar_cpu_usage()
        ram_info = capturar_ram()

        self.hist_cpu.append(cpu_uso)
        self.hist_ram.append(ram_info["porcentaje"])

        self._dibujar_sparkline(self.canvas_cpu, self.hist_cpu, "#22c55e")
        self._dibujar_sparkline(self.canvas_ram, self.hist_ram, "#3b82f6")

        self.root.after(1000, self._iniciar_monitor_recursos)

    def _dibujar_sparkline(self, canvas: tk.Canvas, data: deque, color: str):
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 2 or h < 2: return

        puntos = []
        max_val = max(100, max(data)) # Asegura que el máximo sea al menos 100
        
        for i, val in enumerate(data):
            x = (i / (len(data) - 1)) * w if len(data) > 1 else w / 2
            y = h - (val / max_val * h)
            puntos.extend([x, y])

        if len(puntos) >= 4:
            canvas.create_line(puntos, fill=color, width=2)

        # Etiqueta de valor actual
        canvas.create_text(w - 5, 5, text=f"{data[-1]}%", anchor="ne", fill=color, font=("Segoe UI", 8))

    def _capturar_snapshot(self) -> dict:
        ram = capturar_ram()
        libre = capturar_espacio_libre()
        return {
            "espacio_libre": libre,
            "ram_usada": ram["usada"],
            "ram_total": ram["total"],
            "ram_porcentaje": ram["porcentaje"],
        }

    def _actualizar_metricas_inicio(self, snap: dict):
        self.metric_espacio.set(f"Espacio libre (antes): {formatear_bytes(snap['espacio_libre'])}")
        self.metric_ram.set(
            "RAM usada (antes): "
            f"{formatear_bytes(snap['ram_usada'])}/{formatear_bytes(snap['ram_total'])} "
            f"({snap['ram_porcentaje']}%)"
        )
        self.metric_tiempo.set("Tiempo total: ejecutando...")

    def _actualizar_metricas_final(self, snap_antes: dict, snap_despues: dict, tiempo_total: float, total_tareas: int):
        delta_espacio = snap_despues["espacio_libre"] - snap_antes["espacio_libre"]
        delta_ram = snap_despues["ram_usada"] - snap_antes["ram_usada"]
        promedio = tiempo_total / max(total_tareas, 1)

        self.metric_espacio.set(
            "Espacio libre: "
            f"{formatear_bytes(snap_antes['espacio_libre'])} -> {formatear_bytes(snap_despues['espacio_libre'])} "
            f"(Delta {formatear_delta_bytes(delta_espacio)})"
        )
        self.metric_ram.set(
            "RAM usada: "
            f"{formatear_bytes(snap_antes['ram_usada'])} -> {formatear_bytes(snap_despues['ram_usada'])} "
            f"(Delta {formatear_delta_bytes(-delta_ram)})"
        )
        self.metric_tiempo.set(
            f"Tiempo total: {formatear_segundos(tiempo_total)} | Promedio/tarea: {formatear_segundos(promedio)}"
        )

    def limpiar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def escribir_log(self, mensaje: str):
        marca_tiempo = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{marca_tiempo}] {mensaje}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run_cmd(self, comando: str):
        return subprocess.run(
            comando,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

    def iniciar(self):
        if self.en_ejecucion:
            return

        if not es_admin():
            aceptar = messagebox.askyesno(
                "Permisos de administrador",
                "Se recomienda ejecutar como administrador para aplicar todo.\n\n"
                "¿Quieres relanzar ahora con permisos elevados?",
            )
            if aceptar:
                if relanzar_como_admin():
                    self.root.destroy()
                    return
                messagebox.showerror("Error", "No se pudo relanzar como administrador.")

        tareas = self._obtener_tareas_seleccionadas()
        if not tareas:
            messagebox.showwarning("Sin tareas", "Selecciona al menos una tarea.")
            return

        self.progreso.set(0)
        self.en_ejecucion = True
        self.btn_iniciar.configure(state="disabled")
        self.estado.set("Preparando optimización...")
        self.bytes_liberados_temp = 0
        self.snapshot_antes = self._capturar_snapshot()
        self._actualizar_metricas_inicio(self.snapshot_antes)
        self.escribir_log("Inicio de optimización.")
        self.escribir_log(
            "Snapshot inicial -> "
            f"Espacio libre: {formatear_bytes(self.snapshot_antes['espacio_libre'])}, "
            f"RAM usada: {formatear_bytes(self.snapshot_antes['ram_usada'])} ({self.snapshot_antes['ram_porcentaje']}%)"
        )

        hilo = threading.Thread(target=self._ejecutar_tareas, args=(tareas,), daemon=True)
        hilo.start()

    def _obtener_tareas_seleccionadas(self):
        tareas = []
        if self.var_temp.get():
            tareas.append(("Limpieza de temporales", self.limpiar_temporales))
        if self.var_dns.get():
            tareas.append(("Limpieza de DNS", self.limpiar_dns))
        if self.var_energia.get():
            tareas.append(("Plan de máximo rendimiento", self.activar_maximo_rendimiento))
        if self.var_disco.get():
            tareas.append(("Optimización de disco", self.optimizar_disco))
        if self.var_papelera.get():
            tareas.append(("Vaciado de papelera", self.vaciar_papelera))
        if self.var_analisis.get():
            tareas.append(("Análisis de recursos", self.analizar_recursos))
        if self.var_winget.get():
            tareas.append(("Actualización con winget", self.actualizar_con_winget))
        if self.var_registro.get():
            tareas.append(("Análisis de Registro", self.analizar_registro))
        return tareas

    def _ejecutar_tareas(self, tareas):
        total = len(tareas)
        exitos = 0
        inicio_total = perf_counter()

        for indice, (nombre, funcion) in enumerate(tareas, start=1):
            self.root.after(0, self.estado.set, f"Ejecutando: {nombre} ({indice}/{total})")
            self.root.after(0, self.escribir_log, f"--> {nombre}")
            inicio_tarea = perf_counter()
            try:
                funcion()
                duracion = perf_counter() - inicio_tarea
                exitos += 1
                self.root.after(0, self.escribir_log, f"OK: {nombre} ({formatear_segundos(duracion)})")
            except Exception as ex:
                duracion = perf_counter() - inicio_tarea
                self.root.after(0, self.escribir_log, f"ERROR en {nombre} ({formatear_segundos(duracion)}): {ex}")

            progreso = int((indice / total) * 100)
            self.root.after(0, self.progreso.set, progreso)

        tiempo_total = perf_counter() - inicio_total
        snapshot_despues = self._capturar_snapshot()

        resumen = f"Finalizado: {exitos}/{total} tareas completadas."
        self.root.after(0, self.estado.set, resumen)
        self.root.after(0, self.escribir_log, resumen)
        self.root.after(
            0,
            self._actualizar_metricas_final,
            self.snapshot_antes,
            snapshot_despues,
            tiempo_total,
            total,
        )
        self.root.after(
            0,
            self.escribir_log,
            "Snapshot final -> "
            f"Espacio libre: {formatear_bytes(snapshot_despues['espacio_libre'])}, "
            f"RAM usada: {formatear_bytes(snapshot_despues['ram_usada'])} ({snapshot_despues['ram_porcentaje']}%), "
            f"Tiempo total: {formatear_segundos(tiempo_total)}",
        )
        if self.bytes_liberados_temp > 0:
            self.root.after(
                0,
                self.escribir_log,
                f"Estimado limpiado en temporales: {formatear_bytes(self.bytes_liberados_temp)}",
            )
        self.root.after(0, self._fin_ejecucion)

    def _fin_ejecucion(self):
        self.en_ejecucion = False
        self.btn_iniciar.configure(state="normal")
        messagebox.showinfo(
            "Optimización completada",
            "Proceso terminado. Se recomienda reiniciar el equipo para aplicar todos los cambios.",
        )

    def limpiar_temporales(self):
        carpetas_temp = {
            os.environ.get("TEMP"),
            os.environ.get("TMP"),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Temp"),
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp"),
        }

        archivos = 0
        carpetas = 0
        avisos = 0
        bytes_liberados = 0

        for carpeta in carpetas_temp:
            if not carpeta or not os.path.exists(carpeta):
                continue

            for item in os.listdir(carpeta):
                ruta = os.path.join(carpeta, item)
                try:
                    if os.path.isfile(ruta) or os.path.islink(ruta):
                        if os.path.isfile(ruta):
                            bytes_liberados += os.path.getsize(ruta)
                        os.unlink(ruta)
                        archivos += 1
                    elif os.path.isdir(ruta):
                        for base, _, archivos_dir in os.walk(ruta):
                            for archivo in archivos_dir:
                                archivo_ruta = os.path.join(base, archivo)
                                try:
                                    bytes_liberados += os.path.getsize(archivo_ruta)
                                except OSError:
                                    pass
                        shutil.rmtree(ruta)
                        carpetas += 1
                except PermissionError:
                    avisos += 1
                except OSError:
                    avisos += 1

        self.bytes_liberados_temp += bytes_liberados

        self.root.after(
            0,
            self.escribir_log,
            f"Temporales: {archivos} archivos y {carpetas} carpetas eliminados ({avisos} omitidos). "
            f"Estimado liberado: {formatear_bytes(bytes_liberados)}.",
        )

    def limpiar_dns(self):
        resultado = self._run_cmd("ipconfig /flushdns")
        if resultado.returncode != 0:
            raise RuntimeError(resultado.stderr.strip() or "No se pudo limpiar DNS")

    def activar_maximo_rendimiento(self):
        # Si el plan no existe, se intenta crearlo antes de activarlo.
        self._run_cmd(f"powercfg -duplicatescheme {ULTIMATE_PERFORMANCE_GUID}")
        resultado = self._run_cmd(f"powercfg /s {ULTIMATE_PERFORMANCE_GUID}")
        if resultado.returncode != 0:
            raise RuntimeError(resultado.stderr.strip() or "No se pudo activar el plan de energía")

    def optimizar_disco(self):
        unidad_letra = os.environ.get("SystemDrive", "C:").strip(":")
        cmd_tipo_disco = (
            f'powershell -NoProfile -Command "(Get-PhysicalDisk | '
            f'Where-Object {{$_.DeviceID -in (Get-Partition | Where-Object {{$_.DriveLetter -eq \\"{unidad_letra}\\"}} | '
            f'Get-Disk | Select-Object -ExpandProperty Number)}}).MediaType"'
        )

        resultado_tipo = self._run_cmd(cmd_tipo_disco)
        tipo_disco = resultado_tipo.stdout.strip().lower()

        if "ssd" in tipo_disco:
            self.root.after(0, self.escribir_log, f"  Detectado SSD ({unidad_letra}:). Ejecutando optimización (TRIM)...")
            cmd_optimizacion = f"defrag {unidad_letra}: /L"
        else:
            self.root.after(0, self.escribir_log, f"  Detectado HDD ({unidad_letra}:). Ejecutando desfragmentación...")
            cmd_optimizacion = f"defrag {unidad_letra}: /D /U"

        resultado_opt = self._run_cmd(cmd_optimizacion)
        if resultado_opt.returncode != 0:
            raise RuntimeError(resultado_opt.stderr.strip() or "No se pudo optimizar el disco")
        
        self.root.after(0, self.escribir_log, f"  Resultado de la optimización:\n{resultado_opt.stdout.strip()}")

    def vaciar_papelera(self):
        cmd = 'powershell -NoProfile -Command "Clear-RecycleBin -Force -Confirm:$false -ErrorAction SilentlyContinue"'
        resultado = self._run_cmd(cmd)
        if resultado.returncode != 0:
            raise RuntimeError(resultado.stderr.strip() or "No se pudo vaciar la papelera")

    def analizar_recursos(self):
        cmd_cpu = (
            'powershell -NoProfile -Command '
            '"Get-Process | Sort-Object CPU -Descending | '
            'Select-Object -First 10 ProcessName,CPU,Id | Format-Table -AutoSize"'
        )
        cmd_mem = (
            'powershell -NoProfile -Command '
            '"Get-Process | Sort-Object WorkingSet -Descending | '
            "Select-Object -First 10 ProcessName,@{Name='MemoryMB';Expression={[math]::Round($_.WorkingSet/1MB,2)}},Id | "
            'Format-Table -AutoSize"'
        )

        resultado_cpu = self._run_cmd(cmd_cpu)
        resultado_mem = self._run_cmd(cmd_mem)

        if resultado_cpu.returncode == 0 and resultado_cpu.stdout.strip():
            self.root.after(0, self.escribir_log, "Top CPU:")
            self.root.after(0, self.escribir_log, resultado_cpu.stdout.strip())
        else:
            self.root.after(0, self.escribir_log, "No se pudo obtener top de CPU.")

        if resultado_mem.returncode == 0 and resultado_mem.stdout.strip():
            self.root.after(0, self.escribir_log, "Top memoria:")
            self.root.after(0, self.escribir_log, resultado_mem.stdout.strip())
        else:
            self.root.after(0, self.escribir_log, "No se pudo obtener top de memoria.")

    def actualizar_con_winget(self):
        self.root.after(0, self.escribir_log, "Buscando actualizaciones con winget (puede tardar)...")
        cmd = "winget upgrade --all --silent --accept-source-agreements --accept-package-agreements --disable-interactivity"
        proceso = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        for linea in iter(proceso.stdout.readline, ""):
            if linea.strip():
                self.root.after(0, self.escribir_log, f"  winget: {linea.strip()}")
        proceso.stdout.close()
        ret_code = proceso.wait()
        if ret_code != 0:
            self.root.after(0, self.escribir_log, f"Winget finalizó con código {ret_code}. Puede que no haya nada que actualizar o winget no esté instalado/configurado.")

    def analizar_registro(self):
        if not es_admin():
            raise PermissionError("Se requieren permisos de administrador para limpiar el registro.")

        self.root.after(0, self.escribir_log, "Iniciando limpieza de registro de programas desinstalados...")
        claves_eliminadas = 0
        
        rutas_registro = [
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hive, ruta_base in rutas_registro:
            try:
                with winreg.OpenKey(hive, ruta_base) as key_base:
                    for i in range(winreg.QueryInfoKey(key_base)[0]):
                        nombre_sub_key = winreg.EnumKey(key_base, i)
                        try:
                            with winreg.OpenKey(key_base, nombre_sub_key) as sub_key:
                                display_name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                                uninstall_string, _ = winreg.QueryValueEx(sub_key, "UninstallString")
                                
                                # Limpiar y normalizar la ruta del desinstalador
                                ruta_desinstalador = uninstall_string.strip('"').split('"')[0].strip()
                                if not os.path.exists(ruta_desinstalador):
                                    self.root.after(0, self.escribir_log, f"  Clave huérfana encontrada: {display_name.strip()}")
                                    # La eliminación real se haría aquí, pero es muy arriesgado.
                                    # Por seguridad, solo informamos. Para borrar, se necesitaría una lógica más robusta.
                                    # winreg.DeleteKey(key_base, nombre_sub_key) # ¡PELIGROSO!
                                    self.root.after(0, self.escribir_log, f"  -> Se recomienda eliminar manualmente la clave: {nombre_sub_key}")
                                    claves_eliminadas += 1 # Contamos como si se fuera a eliminar
                        except FileNotFoundError:
                            # Clave no tiene DisplayName o UninstallString, se ignora.
                            continue
                        except Exception as e:
                            self.root.after(0, self.escribir_log, f"  No se pudo procesar la clave {nombre_sub_key}: {e}")
            except FileNotFoundError:
                continue # La ruta base no existe (ej. en HKCU)

        if claves_eliminadas > 0:
            self.root.after(0, self.escribir_log, f"Análisis finalizado. Se identificaron {claves_eliminadas} claves de registro huérfanas.")
        else:
            self.root.after(0, self.escribir_log, "Análisis finalizado. No se encontraron claves de registro huérfanas obvias.")


def main():
    if not es_windows():
        print("Este programa solo funciona en Windows.")
        return

    root = tk.Tk()
    OptimizadorUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
