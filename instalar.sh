#!/usr/bin/env bash
# CLAUDIO · Instalación en Raspberry Pi OS de 64 bits (Pi 5 recomendada).
# Se puede correr más de una vez: no repite lo que ya está hecho.
#   cd claudio && ./instalar.sh
set -euo pipefail
cd "$(dirname "$0")"

# Opciones (variables de entorno):
#   PROVEEDOR=groq ./instalar.sh                      entender y pensar en Groq (nube gratuita):
#        no instala Ollama ni Whisper, y deja la voz de Microsoft (edge), que es la rápida
#   MODELO_LLM=llama3.2:3b ./instalar.sh              usar otro modelo de Ollama
#   OLLAMA_URL=http://192.168.1.20:11434 ./instalar.sh
#        el modelo de lenguaje corre en otro equipo (tu PC): aquí no se instala Ollama
PLACA="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo desconocida)"
case "$PLACA" in
  *"Raspberry Pi 4"*) MODELO_SUGERIDO="qwen2.5:1.5b"; WHISPER="tiny" ;;  # la Pi 4 no da para más
  *)                  MODELO_SUGERIDO="qwen2.5:3b";   WHISPER="base" ;;
esac
MODELO_LLM="${MODELO_LLM:-$MODELO_SUGERIDO}"
OLLAMA_URL="${OLLAMA_URL:-}"
PROVEEDOR="${PROVEEDOR:-local}"
echo "Equipo: $PLACA → modelo $MODELO_LLM, Whisper $WHISPER"
VOSK="vosk-model-small-es-0.42"

echo "== 1/6 Paquetes del sistema =="
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libportaudio2 alsa-utils unzip curl ffmpeg

echo "== 2/6 Entorno de Python =="
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "== 3/6 Modelo de palabra de activación (Vosk, ~40 MB) =="
mkdir -p modelos
if [ ! -d modelos/vosk-es ]; then
  curl -fL -o modelos/vosk.zip "https://alphacephei.com/vosk/models/$VOSK.zip"
  unzip -q modelos/vosk.zip -d modelos
  mv "modelos/$VOSK" modelos/vosk-es
  rm modelos/vosk.zip
fi

echo "== 4/6 Voces (Kokoro, ~120 MB) =="
KOKORO="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
mkdir -p modelos/kokoro
for archivo in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
  [ -f "modelos/kokoro/$archivo" ] || curl -fL -o "modelos/kokoro/$archivo" "$KOKORO/$archivo"
done

echo "== 5/6 Ollama y modelo de lenguaje ($MODELO_LLM) =="
if [ "$PROVEEDOR" = "groq" ]; then
  echo "Se usará Groq: no hace falta Ollama."
elif [ -n "$OLLAMA_URL" ]; then
  echo "Se usará el Ollama de $OLLAMA_URL (recuerda correr allí: ollama pull $MODELO_LLM)"
else
  command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
  ollama pull "$MODELO_LLM"
fi

echo "== 6/6 Configuración y arranque automático =="
if [ ! -f config.json ]; then
  MODELO_LLM="$MODELO_LLM" WHISPER="$WHISPER" OLLAMA_URL="$OLLAMA_URL" PROVEEDOR="$PROVEEDOR" \
    ./venv/bin/python - <<'PY'
import json, os
config = json.load(open("config.ejemplo.json", encoding="utf-8"))
config["modelo"], config["whisper"] = os.environ["MODELO_LLM"], os.environ["WHISPER"]
if os.environ["OLLAMA_URL"]:
    config["ollama_url"] = os.environ["OLLAMA_URL"]
if os.environ["PROVEEDOR"] == "groq":
    config["proveedor"] = "groq"
    config.update(motor_voz="edge", voz="es-ES-AlvaroNeural", tono_voz=0, efecto_voz=0)
json.dump(config, open("config.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
PY
fi
# Deja descargado el modelo de Whisper para que el primer arranque no espere.
[ "$PROVEEDOR" = "groq" ] || ./venv/bin/python -c "
import json
from faster_whisper import WhisperModel
WhisperModel(json.load(open('config.json')).get('whisper', 'base'), device='cpu', compute_type='int8')
"
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/claudio.service <<EOF
[Unit]
Description=Claudio, asistente de voz local
After=sound.target network-online.target

[Service]
WorkingDirectory=$PWD
ExecStart=$PWD/venv/bin/python -u $PWD/claudio.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload

cat <<EOF

✔ Instalación terminada.

  Probar por teclado:   ./venv/bin/python claudio.py --texto
  Probar con voz:       ./venv/bin/python claudio.py
  Ver micrófonos:       ./venv/bin/python claudio.py --audio
  Escuchar las voces:   ./venv/bin/python probar_voces.py

  Dejarlo siempre encendido (arranca solo al prender la Pi):
      sudo loginctl enable-linger $USER
      systemctl --user enable --now claudio
      journalctl --user -u claudio -f        (para ver qué hace)
EOF
