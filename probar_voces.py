#!/usr/bin/env python3
# CLAUDIO · Escucha las voces disponibles y elige la que más te guste.
#
#   python probar_voces.py                    reproduce las de Kokoro (locales)
#   python probar_voces.py --motor edge       las de Microsoft (necesitan internet)
#   python probar_voces.py --motor piper      las de Piper (las descarga)
#   python probar_voces.py --guardar          no reproduce: deja un .wav por voz en muestras/
#   python probar_voces.py --voz "bm_george:0.7+em_alex:0.3"    prueba una voz o mezcla puntual
#   python probar_voces.py --voz em_alex --velocidad 0.95 --tono -2 --efecto 0.3
#                                             retoques: más pausado, más grave, con resonancia
#
# Después copia a config.json lo que el programa muestra junto a la voz elegida.
import argparse
import subprocess
import sys
import wave
from pathlib import Path

import voces

AQUI = Path(__file__).resolve().parent

CATALOGO = {
    "kokoro": [
        ("em_alex", "español, hombre"),
        ("em_santa", "español, hombre, más grave"),
        ("ef_dora", "español, mujer"),
        ("bm_george", "timbre británico maduro, hablando español"),
        ("bm_lewis", "timbre británico grave, hablando español"),
        ("bm_daniel", "timbre británico, hablando español"),
        ("bm_fable", "timbre británico narrador, hablando español"),
        ("am_onyx", "timbre profundo, hablando español"),
        ("bm_george:0.6+em_alex:0.4", "mezcla: británico con pronunciación más española"),
        ("bm_lewis:0.6+em_santa:0.4", "mezcla: británico grave con español"),
    ],
    "edge": [
        ("es-ES-AlvaroNeural", "España, hombre"),
        ("es-MX-JorgeNeural", "México, hombre"),
        ("es-AR-TomasNeural", "Argentina, hombre"),
        ("es-CL-LorenzoNeural", "Chile, hombre"),
        ("es-CO-GonzaloNeural", "Colombia, hombre"),
        ("es-US-AlonsoNeural", "Estados Unidos, hombre"),
        ("es-ES-ElviraNeural", "España, mujer"),
    ],
    "piper": [
        ("es_ES-davefx-medium", "España, hombre"),
        ("es_ES-sharvard-medium", "España"),
        ("es_MX-ald-medium", "México, hombre"),
        ("es_MX-claude-high", "México, calidad alta"),
        ("es_AR-daniela-high", "Argentina, mujer"),
    ],
}
FRASE = (
    "Buenos días, señor. Todos los sistemas están en línea. "
    "La temperatura exterior es de dieciocho grados. ¿En qué puedo ayudarle?"
)


def nombre_archivo(motor, voz, args):
    nombre = f"{motor}-" + "".join(c if c.isalnum() or c in "-_" else "_" for c in voz)
    if args.velocidad != 1.0:
        nombre += f"-vel{args.velocidad:g}"
    if args.tono:
        nombre += f"-tono{args.tono:+g}"
    if args.efecto:
        nombre += f"-efecto{args.efecto:g}"
    return nombre + ".wav"


def main():
    opciones = argparse.ArgumentParser(description="Probar las voces de Claudio")
    opciones.add_argument("--motor", choices=sorted(CATALOGO), default="kokoro")
    opciones.add_argument("--voz", help="probar solo esta voz (o mezcla de Kokoro)")
    opciones.add_argument("--guardar", action="store_true", help="guardar .wav en muestras/ en vez de reproducir")
    opciones.add_argument("--velocidad", type=float, default=1.0)
    opciones.add_argument("--tono", type=float, default=0, help="semitonos: negativo más grave (piper lo ignora)")
    opciones.add_argument("--efecto", type=float, default=0, help="0 a 1: resonancia de computadora de a bordo")
    opciones.add_argument("--frase", default=FRASE)
    args = opciones.parse_args()

    lista = [(args.voz, "")] if args.voz else CATALOGO[args.motor]
    for voz, descripcion in lista:
        config = {"motor_voz": args.motor, "voz": voz, "velocidad_voz": args.velocidad,
                  "tono_voz": args.tono, "efecto_voz": args.efecto}
        if args.motor == "piper":
            archivo = voces.MODELOS / f"{voz}.onnx"
            if not archivo.exists():
                voces.MODELOS.mkdir(exist_ok=True)
                print(f"Descargando {voz}…")
                subprocess.run([sys.executable, "-m", "piper.download_voices", voz,
                                "--download-dir", str(voces.MODELOS)])
            config["voz"] = f"modelos/{voz}.onnx"
        print(f"\n▶ {voz}" + (f" — {descripcion}" if descripcion else ""))
        try:
            trozos = list(voces.crear_voz(config).sintetizar(args.frase))
        except Exception as error:
            print(f"  ✖ no se pudo: {error}")
            continue
        print(f'  para usarla:  "motor_voz": "{args.motor}", "voz": "{config["voz"]}", "velocidad_voz": '
              f'{args.velocidad:g}, "tono_voz": {args.tono:g}, "efecto_voz": {args.efecto:g}')
        if args.guardar:
            destino = AQUI / "muestras" / nombre_archivo(args.motor, voz, args)
            destino.parent.mkdir(exist_ok=True)
            with wave.open(str(destino), "wb") as salida:
                salida.setnchannels(1)
                salida.setsampwidth(2)
                salida.setframerate(trozos[0][1])
                for muestras, _ in trozos:
                    salida.writeframes(muestras.tobytes())
            print(f"  guardada en {destino}")
        else:
            import sounddevice
            for muestras, frecuencia in trozos:
                sounddevice.play(muestras, frecuencia, blocking=True)


if __name__ == "__main__":
    main()
