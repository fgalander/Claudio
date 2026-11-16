# Claudio · asistente de voz local

Un "Jarvis" que corre entero en una Raspberry Pi: sin nube, sin cuentas y sin costo de uso.
Dices **«Claudio»**, le hablas y te responde con voz. Puede controlar la casa (Home Assistant)
y tu computador.

```
micrófono → Vosk (palabra «Claudio») → Whisper (voz a texto)
          → Ollama (modelo de lenguaje + herramientas) → Kokoro (texto a voz) → parlante
```

## Qué comprar

| Pieza | Recomendación |
|---|---|
| Raspberry Pi | **Pi 5 de 8 GB** (16 GB si quieres modelos más grandes). Una Pi 4 es demasiado lenta para el modelo de lenguaje. |
| Refrigeración | Active Cooler oficial: el modelo usa los 4 núcleos al máximo. |
| Fuente | La oficial de 27 W (USB-C). |
| Almacenamiento | microSD de 64 GB o más (mejor un SSD). |
| Micrófono | USB. Uno de conferencia (tipo "speakerphone") capta mucho mejor de lejos. |
| Parlante | USB o por jack con placa de sonido USB (la Pi 5 no trae salida de audio analógica). |

**Qué esperar:** en una Pi 5 la respuesta empieza a sonar entre 5 y 10 segundos después de
que terminas de hablar. Si quieres que sea más rápido y más inteligente, deja la Pi como
"oído y boca" y corre Ollama en tu PC: basta cambiar `ollama_url` en `config.json`.

## Modo rápido con Groq (charla fluida)

Con todo local, una Pi tarda muchos segundos en responder. Para conversar con fluidez,
Claudio puede usar [Groq](https://console.groq.com): un servicio en la nube con capa
gratuita (con límites por minuto y por día) que entiende la voz y piensa la respuesta en
décimas de segundo. Sirve cualquier Pi, incluida la Pi 4.

Qué cambia: se necesita internet, y lo que dices **después** de «Claudio» (el audio y la
conversación) sale a los servidores de Groq. La palabra de activación se sigue detectando
en la Pi, así que no se envía nada mientras no lo llames.

1. Crea una cuenta en <https://console.groq.com> y genera una clave (*API Keys*).
2. Instala en la Pi:

   ```bash
   PROVEEDOR=groq ./instalar.sh
   ```

3. Pega la clave en `config.json`, en `groq` → `clave` (ese archivo no se sube a GitHub).
4. Prueba con `./venv/bin/python claudio.py --texto` y luego sin `--texto`.

Si un modelo deja de existir, `./venv/bin/python claudio.py --modelos` lista los que hay
con tu clave; se cambia en `groq` → `modelo`.

**La voz en este modo:** Kokoro (la voz local) puede tardar varios segundos por frase en
una Pi 4, así que el instalador deja `edge` (voces de Microsoft, también en línea y
gratis). Elige una con `./venv/bin/python probar_voces.py --motor edge`. Si prefieres
probar tu voz de Kokoro igual, pon `"motor_voz": "kokoro"` y
`"voz": "em_alex:0.8+em_santa:0.2"`; Claudio muestra en pantalla cuánto tarda cada etapa.

## Que se sienta como una charla

- **Frases de relleno.** Cuando va a ejecutar una orden dice algo corto al instante
  («Enseguida, señor») y luego calla hasta tener el resultado. Si la respuesta se demora
  más de `relleno_tras` segundos, avisa («Un momento, señor»). El audio de esas frases se
  genera una vez y queda guardado en `cache_voz/`. Se apagan con `"rellenos": false`.
- **Interrumpirlo.** Di «Claudio» mientras habla: se calla y te escucha de inmediato. No
  reacciona a cualquier voz, solo a su nombre, porque sin cancelación de eco se
  interrumpiría con su propio parlante. Se apaga con `"interrumpir": false`.
- **Seguir la conversación.** Después de responder sigue escuchando unos segundos, sin
  que repitas «Claudio».
- **De corrido.** Puedes decir «Claudio, prende la luz» sin pausa entre el nombre y la orden.

## Si tienes una Raspberry Pi 4

Funciona, pero es bastante más lenta que la Pi 5. `instalar.sh` la detecta y elige solo
un modelo más chico (`qwen2.5:1.5b`) y Whisper `tiny`: responde, pero es menos listo y se
equivoca más al usar herramientas. Hay dos caminos:

- **Todo en la Pi 4** (instalación normal): independiente del PC, respuestas lentas y simples.
- **Pi 4 de oído y boca, cerebro en el PC** (recomendado si el PC suele estar encendido):
  mucho más rápido y con un modelo mejor. En el PC instala [Ollama](https://ollama.com),
  haz que escuche en la red (variable de entorno `OLLAMA_HOST=0.0.0.0`) y baja el modelo
  con `ollama pull qwen2.5:7b`. En la Pi instala así, con la IP de tu PC:

  ```bash
  MODELO_LLM=qwen2.5:7b OLLAMA_URL=http://192.168.1.20:11434 ./instalar.sh
  ```

Puedes cambiar de un camino al otro después editando `modelo` y `ollama_url` en `config.json`.

## Instalación (en la Raspberry)

Con Raspberry Pi OS de 64 bits recién instalado:

```bash
git clone https://github.com/fgalander/Claudio.git
```

```bash
cd Claudio && ./instalar.sh
```

Instala los paquetes, baja los modelos (unos 3 GB en total) y deja `config.json` listo.

```bash
./venv/bin/python claudio.py --texto
```

Eso prueba el cerebro por teclado. Para la voz:

```bash
./venv/bin/python claudio.py
```

Si no te oye o no suena, `./venv/bin/python claudio.py --audio` lista los dispositivos;
pon el número del micrófono y del parlante en `config.json` (`microfono`, `parlante`).

## La voz (estilo Jarvis)

Claudio no copia la voz de la película (es la de un actor real); lo que se consigue es el
*estilo*: hombre adulto, serio, formal, trato de «señor». Hay tres motores, se eligen con
`motor_voz` en `config.json`:

| Motor | Dónde corre | Notas |
|---|---|---|
| `kokoro` (por defecto) | En la Pi, gratis | El más natural de los locales. Permite usar timbres británicos hablando español y **mezclar voces**. |
| `edge` | Internet, gratis | Voces neuronales de Microsoft, muy naturales. El texto de cada respuesta sale a sus servidores y sin internet Claudio queda mudo. |
| `piper` | En la Pi, gratis | El más liviano y rápido; suena más sintético. |

Para oírlas y elegir:

```bash
./venv/bin/python probar_voces.py
```

Con `--motor edge` o `--motor piper` prueba los otros motores, y con `--guardar` deja un
`.wav` por voz en `muestras/`. Junto a cada voz muestra qué poner en `config.json`.

Para afinar una voz de Kokoro, prueba mezclas y velocidades hasta que te guste:

```bash
./venv/bin/python probar_voces.py --voz "bm_lewis:0.7+em_santa:0.3" --velocidad 0.92
```

Las voces `em_*` y `ef_*` son españolas; las `bm_*` (británicas) y `am_*` hablan español
con algo de acento, que es justo lo que da el aire de mayordomo inglés. Mezclarlas con una
`em_*` mejora la pronunciación.

Ajustes en `config.json`:

- `"motor_voz"` y `"voz"`: lo que muestra `probar_voces.py`.
- `"velocidad_voz": 0.95`: menos de 1 habla más pausado y solemne.
- `"tono_voz": -2`: semitonos; negativo es más grave (Piper lo ignora).
- `"efecto_voz": 0.3`: de 0 a 1, resonancia sutil de "computadora de a bordo".
- Mezclar: `"voz": "em_alex:0.8+em_santa:0.2"` le da cuerpo sin cambiar de voz (solo Kokoro).
- `"personalidad"`: el texto que define cómo habla (por defecto, mayordomo cortés e irónico).

## Controlar la casa

Claudio habla con [Home Assistant](https://www.home-assistant.io/), que es gratis y puede
correr en la misma Pi o en otra. En Home Assistant: tu perfil → Seguridad → *Tokens de
acceso de larga duración* → crear uno. Luego, en `config.json`:

```json
"casa": {
  "url": "http://192.168.1.50:8123",
  "token": "EL_TOKEN",
  "dispositivos": {
    "luz del living": "light.living",
    "temperatura del dormitorio": "sensor.dormitorio_temperature"
  }
}
```

A la izquierda va el nombre con que tú lo dices; a la derecha, el `entity_id` de Home
Assistant. Claudio solo puede tocar lo que esté en esa lista.

## Gmail y Google Calendar

Claudio puede decirte qué correos tienes sin leer, leerte uno y contarte tu agenda. Es
**solo lectura**: no puede enviar correos ni crear eventos. No hace falta crear un proyecto
en Google Cloud.

**Correo.** Necesita una *contraseña de aplicación* (distinta de tu contraseña normal, y
que puedes revocar cuando quieras):

1. Activa la verificación en dos pasos en <https://myaccount.google.com/security>.
2. Crea la contraseña en <https://myaccount.google.com/apppasswords> (nombre: Claudio).
   Google muestra 16 letras.
3. En `config.json`:

   ```json
   "correo": { "usuario": "tucuenta@gmail.com", "clave_app": "abcd efgh ijkl mnop" }
   ```

**Calendario.** En <https://calendar.google.com>: rueda de ajustes → elige tu calendario a
la izquierda → *Integrar el calendario* → copia la **dirección secreta en formato iCal**.

```json
"calendario": { "url_ical": "https://calendar.google.com/calendar/ical/.../basic.ics" }
```

Para varios calendarios, pon una lista: `"url_ical": ["https://...", "https://..."]`.

Después instala las dos librerías nuevas con `./venv/bin/pip install -r requirements.txt`.

Ten presente: esa contraseña y esa dirección dan acceso de lectura a tu correo y agenda,
así que cuida `config.json`. Y en modo Groq, el texto de los correos y eventos que Claudio
consulta se envía a Groq para poder resumirlo.

Ejemplos: «¿tengo correos nuevos?», «léeme el segundo», «¿hay algo de mi banco?»,
«¿qué tengo mañana?», «¿cómo viene la semana?».

## Controlar el PC

1. Copia `agente_pc.py` a tu computador y córrelo (solo necesita Python 3):

   ```bash
   python agente_pc.py
   ```

2. La primera vez crea `agente_pc.json` y muestra un **token**. En ese archivo defines qué
   aplicaciones puede abrir Claudio (`"nombre": "comando"`).
3. En la Raspberry, en `config.json`:

   ```json
   "pc": { "url": "http://192.168.1.20:8765", "token": "EL_TOKEN", "mac": "AA:BB:CC:DD:EE:FF" }
   ```

Acciones: abrir aplicaciones, abrir una web, buscar en Google, volumen, pausar o cambiar
la música, bloquear, suspender y apagar. Con `mac` puede además **encender** el PC
(Wake-on-LAN, hay que activarlo en la BIOS y en la tarjeta de red).

El agente solo ejecuta esa lista fija y exige el token, pero la conexión va sin cifrar:
úsalo solo dentro de tu red de casa y no abras el puerto 8765 hacia internet.

## Dejarlo siempre encendido

```bash
sudo loginctl enable-linger $USER
```

```bash
systemctl --user enable --now claudio
```

## Ajustes útiles (`config.json`)

| Clave | Para qué |
|---|---|
| `palabra_activacion` | Lista de palabras que lo despiertan. Si «claudio» falla mucho, agrega variantes. |
| `modelo` | Modelo de Ollama. `qwen2.5:3b` equilibra velocidad y uso de herramientas; `llama3.2:3b` es alternativa. |
| `whisper` | `tiny` (rápido), `base` (por defecto) o `small` (más preciso, más lento). |
| `seguir_conversando` | Tras responder sigue escuchando unos segundos sin repetir «Claudio». |
| `umbral_minimo` | Súbelo si el ruido de la sala hace que nunca termine de grabar. |
