# CLAUDIO · Herramientas que el modelo puede usar: domótica (Home Assistant) y el PC.
# Solo se le ofrecen al modelo las que están configuradas en config.json.
import json
import socket
import urllib.error
import urllib.request

ACCIONES_PC = [
    "abrir_app", "abrir_web", "buscar_web", "subir_volumen", "bajar_volumen", "silenciar",
    "pausar_musica", "siguiente_cancion", "bloquear", "suspender", "apagar",
]


def _http(url, token_cabecera, cuerpo=None, espera=8):
    pedido = urllib.request.Request(
        url,
        data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
        headers={"Content-Type": "application/json", **token_cabecera},
        method="POST" if cuerpo is not None else "GET",
    )
    with urllib.request.urlopen(pedido, timeout=espera) as respuesta:
        texto = respuesta.read().decode("utf-8", "replace")
    try:
        return json.loads(texto)
    except ValueError:
        return texto


def definiciones(config):
    lista = []
    casa, pc = config.get("casa", {}), config.get("pc", {})
    dispositivos = sorted(casa.get("dispositivos", {}))
    if casa.get("url") and casa.get("token") and dispositivos:
        lista.append({"type": "function", "function": {
            "name": "controlar_casa",
            "description": "Enciende, apaga o alterna un dispositivo de la casa (luces, enchufes, etc.).",
            "parameters": {"type": "object", "required": ["dispositivo", "accion"], "properties": {
                "dispositivo": {"type": "string", "enum": dispositivos},
                "accion": {"type": "string", "enum": ["encender", "apagar", "alternar"]},
            }},
        }})
        lista.append({"type": "function", "function": {
            "name": "consultar_casa",
            "description": "Consulta el estado actual de un dispositivo o sensor de la casa.",
            "parameters": {"type": "object", "required": ["dispositivo"], "properties": {
                "dispositivo": {"type": "string", "enum": dispositivos},
            }},
        }})
    if pc.get("url") and pc.get("token"):
        lista.append({"type": "function", "function": {
            "name": "controlar_pc",
            "description": (
                "Ejecuta una acción en el computador del usuario. 'argumento' es el nombre de la "
                "aplicación (abrir_app), la dirección (abrir_web) o lo que hay que buscar (buscar_web)."
            ),
            "parameters": {"type": "object", "required": ["accion"], "properties": {
                "accion": {"type": "string", "enum": ACCIONES_PC},
                "argumento": {"type": "string"},
            }},
        }})
    if pc.get("mac"):
        lista.append({"type": "function", "function": {
            "name": "encender_pc",
            "description": "Enciende el computador del usuario por la red (Wake-on-LAN).",
            "parameters": {"type": "object", "properties": {}},
        }})
    return lista


def ejecutar(config, nombre, argumentos):
    """Devuelve siempre un texto corto que el modelo lee como resultado."""
    try:
        if nombre == "controlar_casa":
            return _controlar_casa(config["casa"], argumentos)
        if nombre == "consultar_casa":
            return _consultar_casa(config["casa"], argumentos)
        if nombre == "controlar_pc":
            return _controlar_pc(config["pc"], argumentos)
        if nombre == "encender_pc":
            return _encender_pc(config["pc"])
        return f"Error: la herramienta {nombre} no existe."
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", "replace")[:200]
        return f"Error {error.code}: {detalle}"
    except (urllib.error.URLError, OSError) as error:
        return f"Error de conexión: {error}. Puede que el equipo esté apagado."
    except Exception as error:
        return f"Error: {error}"


def _entidad(casa, argumentos):
    alias = str(argumentos.get("dispositivo", "")).strip().lower()
    for nombre, entidad in casa["dispositivos"].items():
        if nombre.lower() == alias:
            return nombre, entidad
    raise ValueError(f"no conozco «{alias}». Disponibles: {', '.join(sorted(casa['dispositivos']))}")


def _controlar_casa(casa, argumentos):
    nombre, entidad = _entidad(casa, argumentos)
    accion = argumentos.get("accion")
    dominio = entidad.split(".")[0]
    if dominio == "cover":
        servicio = {"encender": "open_cover", "apagar": "close_cover", "alternar": "toggle"}.get(accion)
    elif dominio in ("scene", "script"):
        servicio = "turn_on"
    else:
        servicio = {"encender": "turn_on", "apagar": "turn_off", "alternar": "toggle"}.get(accion)
    if not servicio:
        raise ValueError("acción no válida: usa encender, apagar o alternar")
    _http(
        f"{casa['url'].rstrip('/')}/api/services/{dominio}/{servicio}",
        {"Authorization": f"Bearer {casa['token']}"},
        {"entity_id": entidad},
    )
    return f"Hecho: {accion} {nombre}."


def _consultar_casa(casa, argumentos):
    nombre, entidad = _entidad(casa, argumentos)
    estado = _http(
        f"{casa['url'].rstrip('/')}/api/states/{entidad}", {"Authorization": f"Bearer {casa['token']}"}
    )
    unidad = estado.get("attributes", {}).get("unit_of_measurement", "")
    return f"{nombre}: {estado.get('state')} {unidad}".strip()


def _controlar_pc(pc, argumentos):
    accion = argumentos.get("accion")
    if accion not in ACCIONES_PC:
        raise ValueError(f"acción no válida. Disponibles: {', '.join(ACCIONES_PC)}")
    respuesta = _http(
        f"{pc['url'].rstrip('/')}/accion",
        {"X-Token": pc["token"]},
        {"accion": accion, "argumento": str(argumentos.get("argumento") or "")},
    )
    return respuesta.get("resultado", str(respuesta)) if isinstance(respuesta, dict) else str(respuesta)


def _encender_pc(pc):
    mac = bytes.fromhex(pc["mac"].replace(":", "").replace("-", ""))
    if len(mac) != 6:
        raise ValueError("la MAC del PC en config.json no es válida")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as enchufe:
        enchufe.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        enchufe.sendto(b"\xff" * 6 + mac * 16, ("255.255.255.255", 9))
    return "Señal de encendido enviada. El computador tarda cerca de un minuto en arrancar."
