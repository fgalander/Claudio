# CLAUDIO · Recordatorios, alarmas y temporizadores.
#
# Se guardan en recordatorios.json, así sobreviven a un reinicio. Un hilo revisa la hora cada
# segundo y, cuando toca, avisa en voz alta. El mismo hilo dispara el resumen diario si
# config.json trae una hora en "resumen_diario".
import datetime
import json
import threading
import time
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent / "recordatorios.json"
_candado = threading.Lock()
_lista = None  # [{"cuando": segundos desde 1970, "texto": "..."}]
_mostrados = []  # la última lista que se le mostró al modelo, para "borra el segundo"


def _cargar():
    global _lista
    if _lista is None:
        try:
            _lista = json.loads(ARCHIVO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _lista = []
    return _lista


def _guardar():
    ARCHIVO.write_text(json.dumps(_lista, ensure_ascii=False, indent=1), encoding="utf-8")


def _cuando(segundos):
    momento = datetime.datetime.fromtimestamp(segundos)
    hoy = datetime.date.today()
    if momento.date() == hoy:
        return f"hoy a las {momento:%H:%M}"
    if momento.date() == hoy + datetime.timedelta(days=1):
        return f"mañana a las {momento:%H:%M}"
    return f"el {momento:%d/%m} a las {momento:%H:%M}"


def definiciones(config):
    return [
        {"type": "function", "function": {
            "name": "crear_recordatorio",
            "description": (
                "Programa un recordatorio, alarma o temporizador: Claudio avisará en voz alta a esa hora. "
                "Usa 'en_minutos' para «en 20 minutos» o un temporizador, o 'cuando' para una hora o fecha concreta."
            ),
            "parameters": {"type": "object", "required": ["texto"], "properties": {
                "texto": {"type": "string", "description": "qué hay que recordar, por ejemplo «llamar al dentista»"},
                "en_minutos": {"type": "number"},
                "cuando": {"type": "string", "description": "AAAA-MM-DDTHH:MM en hora local"},
            }},
        }},
        {"type": "function", "function": {
            "name": "ver_recordatorios",
            "description": "Lista los recordatorios pendientes, numerados.",
            "parameters": {"type": "object", "properties": {}},
        }},
        {"type": "function", "function": {
            "name": "borrar_recordatorio",
            "description": "Borra un recordatorio de la última lista mostrada, por su número.",
            "parameters": {"type": "object", "required": ["numero"], "properties": {"numero": {"type": "integer"}}},
        }},
    ]


def ejecutar(config, nombre, argumentos):
    if nombre == "crear_recordatorio":
        return _crear(argumentos)
    if nombre == "ver_recordatorios":
        return pendientes() or "No hay recordatorios pendientes."
    if nombre == "borrar_recordatorio":
        return _borrar(argumentos)
    return None


def _crear(argumentos):
    texto = str(argumentos.get("texto") or "").strip() or "aviso"
    ahora = time.time()
    if argumentos.get("en_minutos") not in (None, ""):
        try:
            minutos = float(argumentos["en_minutos"])
        except (TypeError, ValueError):
            return "en_minutos tiene que ser un número."
        if not 0 < minutos <= 60 * 24 * 366:
            return "El plazo tiene que ser mayor que cero y de un año como máximo."
        cuando = ahora + minutos * 60
    elif argumentos.get("cuando"):
        try:
            cuando = datetime.datetime.fromisoformat(str(argumentos["cuando"]).strip().replace(" ", "T")).timestamp()
        except ValueError:
            return "Fecha no válida: usa AAAA-MM-DDTHH:MM."
        if cuando <= ahora:
            return "Esa hora ya pasó. Pregúntale al usuario si quiso decir mañana."
    else:
        return "Falta cuándo: indica en_minutos o cuando."
    with _candado:
        _cargar().append({"cuando": cuando, "texto": texto})
        _lista.sort(key=lambda r: r["cuando"])
        _guardar()
    return f"Recordatorio programado para {_cuando(cuando)}: {texto}."


def pendientes(solo_hoy=False):
    """Texto con los recordatorios pendientes (también lo usa el resumen del día)."""
    with _candado:
        lista = list(_cargar())
    if solo_hoy:
        fin_del_dia = datetime.datetime.combine(datetime.date.today(), datetime.time.max).timestamp()
        lista = [r for r in lista if r["cuando"] <= fin_del_dia]
    else:
        _mostrados[:] = lista
    return "\n".join(f"{n}. {_cuando(r['cuando'])}: {r['texto']}" for n, r in enumerate(lista, 1))


def _borrar(argumentos):
    try:
        numero = int(argumentos.get("numero"))
    except (TypeError, ValueError):
        numero = 0
    if not _mostrados:
        return "Primero hay que listar los recordatorios con ver_recordatorios."
    if not 1 <= numero <= len(_mostrados):
        return f"Ese número no está en la lista: hay del 1 al {len(_mostrados)}."
    elegido = _mostrados[numero - 1]
    with _candado:
        if elegido in _cargar():
            _lista.remove(elegido)
            _guardar()
    _mostrados.clear()
    return f"Recordatorio borrado: {elegido['texto']}."


def iniciar(config, avisar, resumen=None):
    """Arranca el hilo que vigila la hora. avisar(texto) se llama al vencer un recordatorio;
    resumen() una vez al día, a la hora de config["resumen_diario"] (por ejemplo "08:00")."""
    hora_resumen = str(config.get("resumen_diario") or "").strip()

    def vigilar():
        ultimo_resumen = None
        while True:
            time.sleep(1)
            try:
                ahora = time.time()
                with _candado:
                    vencidos = [r for r in _cargar() if r["cuando"] <= ahora]
                    if vencidos:
                        _lista[:] = [r for r in _lista if r["cuando"] > ahora]
                        _guardar()
                for recordatorio in vencidos:
                    atraso = ahora - recordatorio["cuando"]
                    avisar(recordatorio["texto"] + (f" (era {_cuando(recordatorio['cuando'])})" if atraso > 300 else ""))
                momento = datetime.datetime.now()
                if resumen and hora_resumen and f"{momento:%H:%M}" == hora_resumen and ultimo_resumen != momento.date():
                    ultimo_resumen = momento.date()
                    resumen()
            except Exception as error:  # el hilo no puede morir por un aviso fallido
                print(f"   ✖ recordatorios: {error}")

    hilo = threading.Thread(target=vigilar, daemon=True)
    hilo.start()
    return hilo
