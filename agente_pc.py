#!/usr/bin/env python3
# CLAUDIO · Agente del PC. Corre en TU COMPUTADOR (Windows, Linux o macOS), no en la Raspberry.
#
# Recibe órdenes de Claudio por la red local y ejecuta solo acciones de una lista fija.
# No necesita instalar nada: basta Python 3.   →   python agente_pc.py
#
# La primera vez crea agente_pc.json con un token secreto y la lista de aplicaciones que
# Claudio puede abrir. Copia ese token a config.json en la Raspberry (sección "pc").
import hmac
import json
import platform
import secrets
import subprocess
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent / "agente_pc.json"
SISTEMA = platform.system()  # "Windows", "Linux" o "Darwin" (macOS)

APPS_INICIALES = {
    "Windows": {"navegador": "start chrome", "bloc de notas": "notepad", "calculadora": "calc",
                "explorador": "explorer", "spotify": "start spotify:"},
    "Linux": {"navegador": "xdg-open https://www.google.com", "archivos": "xdg-open ~",
              "terminal": "x-terminal-emulator"},
    "Darwin": {"navegador": "open -a Safari", "notas": "open -a Notes", "spotify": "open -a Spotify"},
}


def cargar_config():
    if ARCHIVO.exists():
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    config = {"puerto": 8765, "token": secrets.token_urlsafe(24), "apps": APPS_INICIALES.get(SISTEMA, {})}
    ARCHIVO.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Creé {ARCHIVO.name}. Edítalo para agregar tus aplicaciones.")
    return config


def correr(comando):
    subprocess.Popen(comando, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def tecla_windows(codigo, veces=1):
    import ctypes
    for _ in range(veces):
        ctypes.windll.user32.keybd_event(codigo, 0, 0, 0)
        ctypes.windll.user32.keybd_event(codigo, 0, 2, 0)


def por_sistema(windows, linux, mac):
    opcion = {"Windows": windows, "Linux": linux, "Darwin": mac}.get(SISTEMA)
    if opcion is None:
        raise ValueError(f"acción no disponible en {SISTEMA}")
    opcion() if callable(opcion) else correr(opcion)


def ejecutar(config, accion, argumento):
    argumento = argumento.strip()
    if accion == "abrir_app":
        apps = {nombre.lower(): comando for nombre, comando in config["apps"].items()}
        comando = apps.get(argumento.lower())
        if not comando:
            raise ValueError(f"no tengo la aplicación «{argumento}». Disponibles: {', '.join(sorted(apps))}")
        correr(comando)
        return f"Abrí {argumento}."
    if accion == "abrir_web":
        url = argumento if "://" in argumento else f"https://{argumento}"
        partes = urllib.parse.urlparse(url)
        if partes.scheme not in ("http", "https") or "." not in partes.netloc or " " in url:
            raise ValueError("dirección web no válida")
        webbrowser.open(url)
        return f"Abrí {partes.netloc}."
    if accion == "buscar_web":
        if not argumento:
            raise ValueError("falta qué buscar")
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(argumento))
        return f"Busqué {argumento}."
    if accion == "subir_volumen":
        por_sistema(lambda: tecla_windows(0xAF, 5), "pactl set-sink-volume @DEFAULT_SINK@ +10%",
                    "osascript -e 'set volume output volume ((output volume of (get volume settings)) + 10)'")
        return "Subí el volumen."
    if accion == "bajar_volumen":
        por_sistema(lambda: tecla_windows(0xAE, 5), "pactl set-sink-volume @DEFAULT_SINK@ -10%",
                    "osascript -e 'set volume output volume ((output volume of (get volume settings)) - 10)'")
        return "Bajé el volumen."
    if accion == "silenciar":
        por_sistema(lambda: tecla_windows(0xAD), "pactl set-sink-mute @DEFAULT_SINK@ toggle",
                    "osascript -e 'set volume output muted not (output muted of (get volume settings))'")
        return "Listo, silencio alternado."
    if accion == "pausar_musica":
        por_sistema(lambda: tecla_windows(0xB3), "playerctl play-pause", None)
        return "Listo."
    if accion == "siguiente_cancion":
        por_sistema(lambda: tecla_windows(0xB0), "playerctl next", None)
        return "Siguiente canción."
    if accion == "bloquear":
        por_sistema("rundll32.exe user32.dll,LockWorkStation", "loginctl lock-session", "pmset displaysleepnow")
        return "Computador bloqueado."
    if accion == "suspender":
        por_sistema("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", "systemctl suspend", "pmset sleepnow")
        return "Computador suspendido."
    if accion == "apagar":
        por_sistema("shutdown /s /t 30", "shutdown -h +1",
                    "osascript -e 'tell application \"System Events\" to shut down'")
        return "El computador se apagará en breve."
    raise ValueError(f"acción desconocida: {accion}")


def crear_manejador(config):
    class Manejador(BaseHTTPRequestHandler):
        def responder(self, codigo, cuerpo):
            datos = json.dumps(cuerpo, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def do_POST(self):
            token = self.headers.get("X-Token", "")
            if not hmac.compare_digest(token.encode(), config["token"].encode()):
                return self.responder(401, {"resultado": "Error: token incorrecto."})
            if self.path != "/accion":
                return self.responder(404, {"resultado": "Error: ruta desconocida."})
            try:
                largo = int(self.headers.get("Content-Length", "0"))
                if largo > 4096:
                    raise ValueError("pedido demasiado grande")
                pedido = json.loads(self.rfile.read(largo) or b"{}")
                resultado = ejecutar(config, str(pedido.get("accion", "")), str(pedido.get("argumento", "")))
                print(f"✔ {pedido.get('accion')} {pedido.get('argumento', '')}".rstrip())
                self.responder(200, {"resultado": resultado})
            except Exception as error:
                print(f"✖ {error}")
                self.responder(200, {"resultado": f"Error: {error}"})

        def log_message(self, *args):
            pass

    return Manejador


def main():
    config = cargar_config()
    servidor = ThreadingHTTPServer(("0.0.0.0", int(config["puerto"])), crear_manejador(config))
    print(f"Agente de Claudio escuchando en el puerto {config['puerto']} ({SISTEMA}).")
    print(f"Token para config.json de la Raspberry:  {config['token']}")
    print("Aplicaciones permitidas:", ", ".join(sorted(config["apps"])) or "(ninguna)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
