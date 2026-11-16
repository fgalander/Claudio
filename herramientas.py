# CLAUDIO · Herramientas que el modelo puede usar: domótica (Home Assistant), el PC,
# correo y calendario (correo_agenda.py), recordatorios (recordatorios.py) y clima, noticias,
# búsqueda y resumen del día (extras.py).
# Solo se le ofrecen al modelo las que están configuradas en config.json.
import json
import socket
import urllib.error
import urllib.request

import correo_agenda
import extras
import recordatorios

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


# ───────────────────────── Domótica (Home Assistant) ─────────────────────────
# Qué tipos de dispositivo se toman solos de Home Assistant. Las cerraduras quedan fuera a
# propósito: para abrir una puerta por voz hay que agregarla a mano en config.json.
DOMINIOS = ("light", "switch", "fan", "cover", "climate", "scene", "script", "media_player",
            "input_boolean", "humidifier", "vacuum", "sensor", "binary_sensor")
ACCIONES_CASA = ["encender", "apagar", "alternar", "abrir", "cerrar", "brillo", "color", "temperatura", "volumen"]
COLORES = {
    "rojo": "red", "verde": "green", "azul": "blue", "amarillo": "yellow", "naranja": "orange", "rosa": "pink",
    "rosado": "pink", "violeta": "purple", "morado": "purple", "celeste": "cyan", "turquesa": "turquoise",
    "blanco": "white", "magenta": "magenta", "dorado": "gold", "lila": "violet",
}
_casa = {}  # nombre → entidad, lo que se pudo leer de Home Assistant


def _simple(texto):
    import unicodedata
    sin_acentos = unicodedata.normalize("NFD", str(texto).lower())
    return " ".join("".join(c for c in sin_acentos if unicodedata.category(c) != "Mn").split())


def _dispositivos(casa):
    """Los de config.json; si no hay ninguno, todos los que Home Assistant tenga."""
    if casa.get("dispositivos"):
        return casa["dispositivos"]
    if not (casa.get("url") and casa.get("token")):
        return {}
    if not _casa:
        try:
            estados = _http(f"{casa['url'].rstrip('/')}/api/states", {"Authorization": f"Bearer {casa['token']}"}, espera=6)
        except Exception as error:
            print(f"  ⚠ no pude leer los dispositivos de Home Assistant: {error}")
            return {}
        for estado in estados:
            entidad = estado.get("entity_id", "")
            if entidad.split(".")[0] not in DOMINIOS or estado.get("state") == "unavailable":
                continue
            nombre = str(estado.get("attributes", {}).get("friendly_name") or entidad.split(".", 1)[1]).strip().lower()
            if nombre in _casa:  # dos con el mismo nombre: se distinguen por el tipo
                nombre = f"{nombre} ({entidad.split('.')[0]})"
            _casa[nombre] = entidad
        print(f"Domótica: {len(_casa)} dispositivos leídos de Home Assistant.")
    return _casa


def definiciones(config):
    lista = []
    casa, pc = config.get("casa", {}), config.get("pc", {})
    dispositivos = sorted(_dispositivos(casa))
    if casa.get("url") and casa.get("token") and dispositivos:
        # Con pocos dispositivos se le da la lista cerrada; con muchos, se busca por parecido.
        nombre = {"type": "string", "enum": dispositivos + ["todas las luces"]} if len(dispositivos) <= 60 else {
            "type": "string", "description": "nombre del dispositivo tal como lo dice el usuario"}
        lista.append({"type": "function", "function": {
            "name": "controlar_casa",
            "description": (
                "Controla un dispositivo de la casa: luces, enchufes, persianas, aire acondicionado, escenas, "
                "parlantes. 'valor' se usa con brillo (0 a 100), color (nombre del color, «cálido» o «frío»), "
                "temperatura (grados) y volumen (0 a 100). Para una escena usa encender."
            ),
            "parameters": {"type": "object", "required": ["dispositivo", "accion"], "properties": {
                "dispositivo": nombre,
                "accion": {"type": "string", "enum": ACCIONES_CASA},
                "valor": {"type": "string"},
            }},
        }})
        lista.append({"type": "function", "function": {
            "name": "consultar_casa",
            "description": "Consulta el estado de un dispositivo o sensor de la casa (encendido, temperatura, etc.).",
            "parameters": {"type": "object", "required": ["dispositivo"], "properties": {"dispositivo": nombre}},
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
    return (lista + correo_agenda.definiciones(config) + recordatorios.definiciones(config)
            + extras.definiciones(config))


def nuevo_turno():
    """Lo llama el cerebro cada vez que el usuario habla (ver los seguros de correo_agenda)."""
    correo_agenda.nuevo_turno()


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
        for modulo in (correo_agenda, recordatorios, extras):
            resultado = modulo.ejecutar(config, nombre, argumentos)
            if resultado is not None:
                return resultado
        return f"Error: la herramienta {nombre} no existe."
    except urllib.error.HTTPError as error:
        detalle = error.read().decode("utf-8", "replace")[:200]
        return f"Error {error.code}: {detalle}"
    except (urllib.error.URLError, OSError) as error:
        return f"Error de conexión: {error}. Puede que el equipo esté apagado."
    except Exception as error:
        return f"Error: {error}"


def _entidad(casa, argumentos):
    dispositivos = _dispositivos(casa)
    alias = _simple(argumentos.get("dispositivo", ""))
    if alias in ("todas las luces", "todas", "las luces", "luces"):
        return "todas las luces", "light.all"
    for nombre, entidad in dispositivos.items():
        if _simple(nombre) == alias:
            return nombre, entidad
    parecidos = [(n, e) for n, e in dispositivos.items() if alias and (alias in _simple(n) or _simple(n) in alias)]
    if len(parecidos) == 1:
        return parecidos[0]
    if parecidos:
        raise ValueError(f"«{alias}» puede ser: {', '.join(n for n, _ in parecidos[:8])}. Pregunta cuál.")
    raise ValueError(f"no conozco «{alias}». Algunos disponibles: {', '.join(sorted(dispositivos)[:25])}")


def _numero(valor, minimo, maximo, que):
    try:
        numero = float(str(valor).replace(",", ".").replace("%", "").strip())
    except (TypeError, ValueError):
        raise ValueError(f"falta el valor de {que} (un número entre {minimo} y {maximo})")
    return max(minimo, min(maximo, numero))


def _servicio(dominio, accion, valor):
    """Traduce la acción pedida al servicio de Home Assistant: (dominio, servicio, datos extra)."""
    si_no = {"encender": "turn_on", "apagar": "turn_off", "alternar": "toggle"}
    if dominio in ("scene", "script"):
        return dominio, "turn_on", {}
    if dominio == "cover":
        if accion == "brillo":
            return dominio, "set_cover_position", {"position": round(_numero(valor, 0, 100, "posición"))}
        servicio = {"encender": "open_cover", "abrir": "open_cover", "apagar": "close_cover",
                    "cerrar": "close_cover", "alternar": "toggle"}.get(accion)
        return dominio, servicio, {}
    if dominio == "lock":
        return dominio, {"abrir": "unlock", "cerrar": "lock"}.get(accion), {}
    if dominio == "light" and accion == "brillo":
        return dominio, "turn_on", {"brightness_pct": round(_numero(valor, 1, 100, "brillo"))}
    if dominio == "light" and accion == "color":
        color = _simple(valor or "")
        if color in ("calido", "calida", "blanco calido"):
            return dominio, "turn_on", {"color_temp_kelvin": 2700}
        if color in ("frio", "fria", "blanco frio"):
            return dominio, "turn_on", {"color_temp_kelvin": 6000}
        if color not in COLORES:
            raise ValueError(f"no conozco el color «{valor}». Disponibles: {', '.join(COLORES)}, cálido, frío")
        return dominio, "turn_on", {"color_name": COLORES[color]}
    if dominio == "climate" and accion == "temperatura":
        return dominio, "set_temperature", {"temperature": _numero(valor, 10, 32, "temperatura")}
    if dominio == "media_player" and accion == "volumen":
        return dominio, "volume_set", {"volume_level": _numero(valor, 0, 100, "volumen") / 100}
    if dominio == "vacuum":
        return dominio, {"encender": "start", "apagar": "return_to_base"}.get(accion), {}
    if dominio in ("sensor", "binary_sensor"):
        raise ValueError("eso es un sensor: solo se puede consultar")
    return dominio, si_no.get(accion), {}


def _controlar_casa(casa, argumentos):
    nombre, entidad = _entidad(casa, argumentos)
    accion = argumentos.get("accion")
    valor = argumentos.get("valor")
    dominio = entidad.split(".")[0]
    dominio, servicio, datos = _servicio(dominio, accion, valor)
    if not servicio:
        raise ValueError(f"«{nombre}» no admite la acción {accion}")
    _http(
        f"{casa['url'].rstrip('/')}/api/services/{dominio}/{servicio}",
        {"Authorization": f"Bearer {casa['token']}"},
        dict(datos, entity_id="all" if entidad == "light.all" else entidad),
    )
    detalle = f" a {valor}" if datos else ""
    return f"Hecho: {accion} {nombre}{detalle}."


def _consultar_casa(casa, argumentos):
    nombre, entidad = _entidad(casa, argumentos)
    if entidad == "light.all":
        estados = _http(f"{casa['url'].rstrip('/')}/api/states", {"Authorization": f"Bearer {casa['token']}"})
        prendidas = [e["attributes"].get("friendly_name", e["entity_id"]) for e in estados
                     if e["entity_id"].startswith("light.") and e["state"] == "on"]
        return "Luces encendidas: " + (", ".join(prendidas) if prendidas else "ninguna") + "."
    estado = _http(
        f"{casa['url'].rstrip('/')}/api/states/{entidad}", {"Authorization": f"Bearer {casa['token']}"}
    )
    atributos = estado.get("attributes", {})
    traduccion = {"on": "encendido", "off": "apagado", "open": "abierto", "closed": "cerrado", "unavailable": "sin conexión",
                  "playing": "reproduciendo", "paused": "en pausa", "idle": "en espera", "heat": "calefacción", "cool": "frío"}
    valor = traduccion.get(estado.get("state"), estado.get("state"))
    extras = []
    if atributos.get("unit_of_measurement"):
        valor = f"{valor} {atributos['unit_of_measurement']}"
    if atributos.get("brightness") is not None:
        extras.append(f"brillo {round(atributos['brightness'] / 255 * 100)} %")
    if atributos.get("current_temperature") is not None:
        extras.append(f"temperatura actual {atributos['current_temperature']} grados")
    if atributos.get("temperature") is not None:
        extras.append(f"programado a {atributos['temperature']} grados")
    if atributos.get("current_position") is not None:
        extras.append(f"posición {atributos['current_position']} %")
    return f"{nombre}: {valor}" + (f" ({', '.join(extras)})" if extras else "") + "."


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
