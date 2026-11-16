# CLAUDIO · Motores de voz (texto a voz). Se elige en config.json con "motor_voz":
#
#   "kokoro"  local y gratis. Voces más naturales que Piper. Permite mezclar voces:
#             "voz": "em_alex"                       una voz en español
#             "voz": "bm_george"                     timbre británico hablando español
#             "voz": "bm_george:0.6+em_alex:0.4"     mezcla con pesos
#   "piper"   local y gratis, el más liviano.  "voz": "auto" o la ruta de un .onnx
#   "edge"    voces neuronales de Microsoft: muy naturales y gratis, pero NECESITAN INTERNET
#             (el texto de cada respuesta sale a sus servidores).  "voz": "es-ES-AlvaroNeural"
#
# Retoques (valen para cualquier motor salvo donde se indica):
#   "velocidad_voz": 0.95   menos de 1 = más pausado
#   "tono_voz": -2          semitonos: negativo = más grave, positivo = más agudo
#   "efecto_voz": 0.3       0 a 1: resonancia sutil de "computadora de a bordo"
#
# Todos devuelven lo mismo: trozos (muestras int16, frecuencia) listos para reproducir.
import subprocess
import threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MODELOS = AQUI / "modelos"
KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_ARCHIVOS = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")


class VozKokoro:
    _motor = None  # el modelo se carga una sola vez aunque se prueben muchas voces

    def __init__(self, voz, velocidad, tono=0.0):
        import numpy
        from kokoro_onnx import Kokoro

        carpeta = MODELOS / "kokoro"
        faltan = [a for a in KOKORO_ARCHIVOS if not (carpeta / a).exists()]
        if faltan:
            raise FileNotFoundError(f"faltan {', '.join(faltan)} en {carpeta}. Corre ./instalar.sh")
        if VozKokoro._motor is None:
            VozKokoro._motor = Kokoro(str(carpeta / KOKORO_ARCHIVOS[0]), str(carpeta / KOKORO_ARCHIVOS[1]))
        # El tono se cambia estirando el audio; para que no cambie la duración,
        # se le pide al modelo que hable más rápido o más lento en la misma proporción.
        self.np, self.factor = numpy, 2 ** (float(tono) / 12)
        self.velocidad = min(2.0, max(0.5, velocidad / self.factor))
        partes = []
        for parte in (voz or "em_alex").split("+"):
            nombre, _, peso = parte.strip().partition(":")
            partes.append((nombre, float(peso) if peso else 1.0))
        total = sum(peso for _, peso in partes)
        if len(partes) == 1:
            self.estilo = partes[0][0]
        else:  # mezcla: promedio ponderado de los "estilos" de cada voz
            self.estilo = sum(self._motor.get_voice_style(n) * (p / total) for n, p in partes)

    def sintetizar(self, texto):
        muestras, frecuencia = self._motor.create(texto, voice=self.estilo, speed=self.velocidad, lang="es")
        if abs(self.factor - 1) > 0.001:
            largo = int(len(muestras) / self.factor)
            muestras = self.np.interp(
                self.np.linspace(0, len(muestras) - 1, largo), self.np.arange(len(muestras)), muestras
            )
        yield (self.np.clip(muestras, -1, 1) * 32767).astype(self.np.int16), frecuencia


class VozPiper:
    def __init__(self, voz, velocidad):
        import numpy
        from piper import PiperVoice
        from piper.config import SynthesisConfig

        if not voz or voz == "auto":
            disponibles = sorted(MODELOS.glob("*.onnx"))
            if not disponibles:
                raise FileNotFoundError("no hay voces de Piper en modelos/. Corre probar_voces.py --motor piper")
            ruta = disponibles[0]
        else:
            ruta = Path(voz) if Path(voz).is_absolute() else AQUI / voz
        self.np = numpy
        self.voz = PiperVoice.load(str(ruta))
        self.hablantes = max(1, getattr(self.voz.config, "num_speakers", 1) or 1)
        self.ajuste = SynthesisConfig(length_scale=1.0 / velocidad)

    def sintetizar(self, texto):
        for trozo in self.voz.synthesize(texto, self.ajuste):
            yield self.np.frombuffer(trozo.audio_int16_bytes, dtype=self.np.int16), trozo.sample_rate


class VozEdge:
    def __init__(self, voz, velocidad, tono):
        import edge_tts
        import numpy

        self.np, self.edge = numpy, edge_tts
        self.voz = voz or "es-ES-AlvaroNeural"
        self.ritmo = f"{round((velocidad - 1) * 100):+d}%"
        self.tono = f"{round(float(tono) * 7):+d}Hz"  # un semitono ≈ 7 Hz en una voz de hombre

    def sintetizar(self, texto):
        habla = self.edge.Communicate(texto, self.voz, rate=self.ritmo, pitch=self.tono)
        mp3 = b"".join(parte["data"] for parte in habla.stream_sync() if parte["type"] == "audio")
        pcm = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-f", "s16le", "-ar", "24000", "-ac", "1", "pipe:1"],
            input=mp3, stdout=subprocess.PIPE, check=True,
        ).stdout
        yield self.np.frombuffer(pcm, dtype=self.np.int16), 24000


class ConEfecto:
    """Envuelve una voz y le suma ecos muy cortos: suena a sala metálica, no a caverna."""

    ECOS = ((0.017, 0.55), (0.031, 0.40), (0.047, 0.28), (0.071, 0.18))  # (segundos, fuerza)

    def __init__(self, voz, cantidad):
        import numpy
        self.np, self.voz, self.cantidad = numpy, voz, min(1.0, max(0.0, float(cantidad)))

    def sintetizar(self, texto):
        for muestras, frecuencia in self.voz.sintetizar(texto):
            seco = self.np.concatenate([muestras.astype(self.np.float32), self.np.zeros(int(frecuencia * 0.12))])
            salida = seco.copy()
            for segundos, fuerza in self.ECOS:
                salto = int(frecuencia * segundos)
                salida[salto:] += seco[:-salto] * fuerza * self.cantidad
            salida *= 1 / (1 + 0.6 * self.cantidad)  # compensa el volumen que agregan los ecos
            yield self.np.clip(salida, -32768, 32767).astype(self.np.int16), frecuencia


def elegir_dispositivo(configurado, salida=True):
    """Qué parlante (o micrófono) usar: el de config.json; si no hay, el primero por USB;
    y si tampoco, el que el sistema tenga por defecto (None)."""
    if configurado is not None:
        return configurado
    try:
        import sounddevice
        for numero, dispositivo in enumerate(sounddevice.query_devices()):
            canales = dispositivo["max_output_channels" if salida else "max_input_channels"]
            if canales > 0 and "usb" in dispositivo["name"].lower():
                return numero
    except Exception:
        pass
    return None


def cambiar_frecuencia(muestras, origen, destino):
    """Convierte audio int16 de una frecuencia de muestreo a otra (interpolación lineal)."""
    import numpy
    if origen == destino or len(muestras) == 0:
        return muestras
    largo = max(1, int(round(len(muestras) * destino / origen)))
    posiciones = numpy.linspace(0, len(muestras) - 1, largo)
    return numpy.interp(posiciones, numpy.arange(len(muestras)), muestras).astype(numpy.int16)


class Salida:
    """Parlante siempre abierto. Abrirlo y cerrarlo en cada frase hace que muchos parlantes
    USB se coman el primer segundo: tardan en despertar. Aquí el canal queda abierto todo el
    tiempo, con un ruido inaudible entre frases para que el parlante no se duerma."""

    def __init__(self, dispositivo, mantener=3):
        import numpy
        import sounddevice
        self.np, self.mantener = numpy, int(mantener or 0)
        datos = sounddevice.query_devices(dispositivo if dispositivo is not None else sounddevice.default.device[1])
        self.frecuencia = int(datos["default_samplerate"])
        self.canales = 2 if int(datos["max_output_channels"]) >= 2 else 1
        self.pendiente = numpy.zeros(0, dtype=numpy.int16)
        self.candado = threading.Lock()
        self.flujo = sounddevice.OutputStream(
            samplerate=self.frecuencia, channels=self.canales, dtype="int16",
            device=dispositivo, callback=self._llenar,
        )
        self.flujo.start()

    def _llenar(self, salida, cuadros, tiempo, estado):
        with self.candado:
            trozo, self.pendiente = self.pendiente[:cuadros], self.pendiente[cuadros:]
        if self.mantener:
            bloque = self.np.random.randint(-self.mantener, self.mantener + 1, cuadros).astype(self.np.int16)
        else:
            bloque = self.np.zeros(cuadros, dtype=self.np.int16)
        bloque[: len(trozo)] = trozo
        salida[:] = bloque.reshape(-1, 1)

    def reproducir(self, muestras, frecuencia):
        """Agrega audio a la cola y vuelve de inmediato."""
        muestras = cambiar_frecuencia(self.np.asarray(muestras, dtype=self.np.int16), frecuencia, self.frecuencia)
        with self.candado:
            self.pendiente = self.np.concatenate([self.pendiente, muestras])

    def segundos(self):
        return len(self.pendiente) / self.frecuencia

    def detener(self):
        with self.candado:
            self.pendiente = self.np.zeros(0, dtype=self.np.int16)

    def esperar(self):
        import time
        while self.segundos() > 0:
            time.sleep(0.05)
        time.sleep(0.15)


def crear_voz(config):
    motor = config.get("motor_voz", "kokoro")
    voz, velocidad = config.get("voz"), float(config.get("velocidad_voz", 1.0))
    tono = float(config.get("tono_voz", 0) or 0)
    if motor == "kokoro":
        creada = VozKokoro(None if voz == "auto" else voz, velocidad, tono)
    elif motor == "piper":
        creada = VozPiper(voz, velocidad)
    elif motor == "edge":
        creada = VozEdge(None if voz == "auto" else voz, velocidad, tono)
    else:
        raise ValueError(f"motor_voz desconocido: {motor} (usa kokoro, piper o edge)")
    efecto = float(config.get("efecto_voz", 0) or 0)
    return ConEfecto(creada, efecto) if efecto > 0 else creada
