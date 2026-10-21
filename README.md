# Mano robótica para lenguaje de señas

Mano robótica controlada por una **ESP32-S3 (placa Freenove, MicroPython estándar)** con **6 servomotores MG90S** (engranajes metálicos). Cada dedo se cierra tirando de un hilo de **Terlenka**; para abrirlo, el servo afloja el hilo y el dedo vuelve solo a su posición inicial (abierta).

> **Fase 1 (actual):** abrir y cerrar la mano completa y cada dedo de forma independiente, desde el REPL y desde una app Streamlit en la PC.
> **Fases futuras:** Kinect conectado a la mano (la PC manda la posición de los dedos), voz local en la placa (reutilizando el asistente de voz), señas del alfabeto.

---

## 1. Lista de materiales

| Cant. | Elemento | Nota |
|---|---|---|
| 1 | Placa Freenove ESP32-S3 WROOM | Se programa por USB |
| 1 | **Placa de expansión Freenove (breakout)** donde se inserta la ESP32-S3 | Con entrada DC de 7 a 12 V; entrega 5 V hasta 3 A (con alimentación DC) y 3,3 V hasta 0,5 A. Es la que alimenta los servos |
| 6 | Servomotor MG90S (180°, engranajes metálicos) | Torque 1,8 kg·cm a 4,8 V / 2,2 kg·cm a 6 V |
| 1 | Fuente de **12 V 2 A** con conector DC compatible con la placa | Va a la entrada DC de la breakout (verificar polaridad y conector en su manual) |
| 1 | Multímetro | Para medir el voltaje de los 5 V antes de conectar los servos |
| 1 | Condensador electrolítico **1000 µF, 10 V o más** | Entre 5 V y GND, cerca de los servos |
| — | Cables Dupont (hembra-hembra o macho-hembra según el montaje) | Para la señal de cada servo |
| — | Cable de calibre 22 AWG (o más grueso) para el 5 V y GND de los servos | Los Dupont delgados se calientan con varios servos |
| — | Hilo Terlenka, poleas/brazos de servo, elástico o resorte opcional | Montaje mecánico (sección 8) |

---

## 2. Reglas de oro eléctricas (leer antes de conectar nada)

1. **Los servos se alimentan con los 5 V de la breakout, con la fuente de 12 V conectada a su entrada DC. NUNCA desde el USB** (el USB solo da 0,5 A y el puerto del computador puede dañarse). Cada MG90S puede pedir unos 0,7 A cuando fuerza; con alimentación DC la breakout entrega hasta 3 A en los 5 V, y por eso la rampa y el arranque escalonado son obligatorios.
2. **Los 12 V nunca llegan a un servo.** Los MG90S aguantan máximo 6 V. Los 12 V solo entran por el conector DC de la breakout; los servos se conectan únicamente a los pines de **5 V** (nunca al de VIN/12 V si la breakout lo expone).
3. **GND común:** al usar los pines GND de la breakout, ya está compartido con la ESP32. Sin GND común la señal PWM no tiene referencia y los servos vibran o se mueven solos.
4. **Señal de 3,3 V.** La salida de la ESP32 alcanza para los MG90S. No se necesita convertidor de nivel. El pin de 3,3 V de la breakout (0,5 A) no es para servos.
5. **Medir antes de conectar:** con la fuente de 12 V conectada y NINGÚN servo, medir entre 5 V y GND de la breakout: debe leer entre 4,8 y 5,3 V. Si lee otra cosa, no conectar servos.
6. **Orden de energizado:** primero conectar los servos con la fuente apagada, luego encender la fuente de 12 V, y al final abrir el REPL por USB. Al apagar, la fuente primero. Los pines no emiten señal hasta el primer movimiento, así que no hay tirones al encender.
7. **Antes de conectar un servo a un hilo, probarlo suelto** (secciones 6 y 7).
8. **Si la placa se reinicia o el REPL se desconecta cuando se mueven varios servos**, es una caída de voltaje: bajar la velocidad en `config.py`, añadir el condensador y usar cable grueso. No es un problema de código.
9. **Verificación pendiente:** el manual de Freenove dice que con alimentación por USB los 5 V y 3,3 V entregan solo 0,5 A, y con la entrada DC (7–12 V) 5 V entrega 3 A. Antes de usar USB y DC a la vez, confirmar en su manual que es seguro conectar ambos.

---

## 3. Cables del servo MG90S

| Color del cable | Función | Se conecta a |
|---|---|---|
| **Marrón** (o negro) | GND | Pin GND de la breakout |
| **Rojo** | V+ (4,8–6 V) | Pin de 5 V de la breakout |
| **Naranja** (o amarillo) | Señal PWM | GPIO de la ESP32 (tabla de la sección 4) |

El conector del servo lleva los tres cables en orden: marrón – rojo – naranja. **No invertir marrón y rojo**: se daña el servo.

---

## 4. Mapeo de pines

### 4.1 Servos de la mano (fase 1)

| # | Servo | Función | GPIO ESP32-S3 | Valor 0.0 (reposo) | Valor 1.0 (activo) |
|---|---|---|---|---|---|
| 1 | `indice` | Flexión del índice | **GPIO8** | extendido | cerrado |
| 2 | `medio` | Flexión del medio | **GPIO9** | extendido | cerrado |
| 3 | `anular` | Flexión del anular | **GPIO10** | extendido | cerrado |
| 4 | `menique` | Flexión del meñique | **GPIO11** | extendido | cerrado |
| 5 | `pulgar_flexion` | Flexión del pulgar | **GPIO12** | extendido | doblado |
| 6 | `pulgar_oposicion` | Oposición del pulgar | **GPIO13** | al costado de la palma | cruzado hacia la palma |

El pulgar usa dos servos: uno dobla el dedo (flexión) y otro lo cruza hacia la palma (oposición). Se calibran por separado.

### 4.2 Pines reservados para fases futuras (NO usar para otra cosa)

Se heredan del asistente de voz para poder integrarlo después sin recablear:

| Función futura | GPIO |
|---|---|
| Micrófono INMP441: SCK / WS / SD | GPIO4 / GPIO5 / GPIO6 |
| LED indicador | GPIO7 |
| Amplificador MAX98357A: BCLK / LRC / DIN | GPIO15 / GPIO16 / GPIO17 |
| Libre para ampliar la mano (ej. muñeca) | GPIO14, GPIO18, GPIO21 |

### 4.3 Pines que NO se deben usar

| GPIO | Motivo |
|---|---|
| 0, 3, 45, 46 | Pines de arranque (strapping) |
| 19, 20 | USB nativo |
| 33 a 37 | PSRAM octal de la placa |
| 39 a 42 | JTAG |
| 43, 44 | UART0 (consola serial USB) |
| 26 a 32 | Flash interna |

---

## 5. Esquema de alimentación

```
 Fuente 12 V 2 A ──► conector DC de la breakout Freenove
                           │  (regulador interno de la breakout: 5 V hasta 3 A)
                           ▼
 ┌─────────────────────────────────────────────┐
 │ Breakout Freenove con la ESP32-S3 insertada │◄── USB al computador (REPL / programar)
 │                                             │
 │  GPIO8  ──── señal (naranja) servo 1        │
 │  GPIO9  ──── señal (naranja) servo 2        │
 │  GPIO10 ──── señal (naranja) servo 3        │
 │  GPIO11 ──── señal (naranja) servo 4        │
 │  GPIO12 ──── señal (naranja) servo 5        │
 │  GPIO13 ──── señal (naranja) servo 6        │
 │                                             │
 │  5V  ───────► rojo de los 6 servos          │
 │  GND ───────► marrón de los 6 servos        │
 │  3V3: SIN conectar a servos                 │
 └─────────────────────────────────────────────┘
        Condensador 1000 µF entre 5V y GND
        (patita larga/+ a 5V, patita corta/− a GND), cerca de los servos
```

Puntos clave:
- Una sola red de alimentación: la fuente de 12 V entra por la breakout, que reparte 5 V y GND a los servos y a la ESP32. El GND es común por construcción.
- Si la breakout tiene pocos pines de 5 V/GND para seis servos, repartir con una regleta o bornera de calibre grueso conectada a un solo pin de 5 V y uno de GND de la breakout.
- El condensador absorbe los picos de corriente cuando arrancan los servos.
- La señal de cada servo va con Dupont a su GPIO.

---

## 6. Pruebas progresivas

Se avanza por etapas. **No pasar a la siguiente hasta que la anterior funcione sin calentamiento ni vibraciones.** En las etapas A a D los servos están **sueltos**, sin hilo y sin la mano.

### Etapa A: un solo servo, sin carga

**Conexión (solo 1 servo):**

| Servo (MG90S #1) | Va a |
|---|---|
| Marrón (GND) | Pin GND de la breakout |
| Rojo (V+) | Pin 5V de la breakout |
| Naranja (señal) | **GPIO8** |

**Pasos:**

1. Con la fuente de 12 V **desconectada**, conecta el servo como en la tabla.
   Antes de conectarlo, con la fuente encendida, mide 5V–GND de la breakout (debe ser 4,8–5,3 V).
2. Conecta la fuente de 12 V al conector DC de la breakout y enciéndela. Después conecta el USB y verifica que MicroPython responde (`>>>` en el REPL).
3. El servo **no debe moverse** al encender (aún no recibe señal). Si da un pequeño tirón, es normal.
4. En el REPL, prueba de forma gradual (valores en nanosegundos; 1 500 000 ns = 1,5 ms = centro):

```python
from machine import Pin, PWM
servo = PWM(Pin(8), freq=50, duty_ns=1500000)   # centro (~90°)
servo.duty_ns(1300000)    # un poco hacia un lado
servo.duty_ns(1700000)    # un poco hacia el otro
servo.duty_ns(1000000)    # ~1,0 ms
servo.duty_ns(2000000)    # ~2,0 ms
servo.duty_ns(0)          # sin señal: el servo queda libre
```

5. Amplía el rango **de a 100 000 ns (0,1 ms) por vez** hacia 400 000 y 2 600 000 (límites de seguridad medidos con los servos reales). **Detente apenas oigas que el servo fuerza contra su tope** (zumbido continuo) y anota ese pulso.

**Qué anotar (alimenta la calibración):**
- Pulso (µs) donde el brazo llega a un extremo sin forzar.
- Pulso (µs) del extremo opuesto.
- Recorrido total en grados (la ficha dice 180°; los servos económicos varían).

**Medidas opcionales con multímetro:** voltaje entre rojo y marrón (debe mantenerse ≥ 4,8 V al moverse).

**Criterio de éxito:** el servo va a cada posición, se queda quieto y no se calienta.

### Etapa B: un servo con el firmware del proyecto

Con el firmware cargado (ver sección 11) y el mismo cableado de la etapa A:

```python
import mano
m = mano.crear_mano()      # solo GPIO8 conectado, los demás sin servo
m.dedo("indice", 1.0)      # cierra (hacia el pulso 'cerrado' de config)
m.dedo("indice", 0.0)      # abre
```

Criterio: se mueve suave (rampa), sin saltos, en la dirección esperada.

### Etapa C: tres servos (índice, medio, anular)

Agrega los servos #2 y #3 en GPIO9 y GPIO10, cada uno con su marrón al GND común, su rojo al V+ de la fuente y su naranja al GPIO. Prueba `m.abrir()` y `m.cerrar()`. Observa si la fuente cae de voltaje o la placa se reinicia (si pasa, revisar GND común, condensador y cableado grueso).

### Etapa D: los seis servos, sin carga

Conecta los servos #4, #5 y #6 (GPIO11, GPIO12, GPIO13). Prueba `m.abrir()` y `m.cerrar()` varias veces y con el pulgar en sus dos ejes. Toca los servos tras 5 minutos: tibios es normal, calientes no.

### Etapa E: servos montados en la mano, con hilo Terlenka

Ver sección 8. Se hace solo después de calibrar los extremos en vacío.

---

## 7. Tabla completa de conexiones (mano terminada)

| Servo | Cable marrón (GND) | Cable rojo (V+) | Cable naranja (señal) |
|---|---|---|---|
| 1 `indice` | GND breakout | 5V breakout | GPIO8 |
| 2 `medio` | GND breakout | 5V breakout | GPIO9 |
| 3 `anular` | GND breakout | 5V breakout | GPIO10 |
| 4 `menique` | GND breakout | 5V breakout | GPIO11 |
| 5 `pulgar_flexion` | GND breakout | 5V breakout | GPIO12 |
| 6 `pulgar_oposicion` | GND breakout | 5V breakout | GPIO13 |

| Otros elementos | Conexión |
|---|---|
| Fuente 12 V 2 A | Conector DC de la breakout (verificar polaridad en su manual) |
| Condensador 1000 µF | Entre 5V y GND de la breakout, cerca de los servos |
| Pin 3V3 de la breakout | **Sin conectar** a servos |
| USB | Al computador (programación y REPL) |

---

## 8. Montaje mecánico (hilo Terlenka)

- **Cierre:** el servo gira y enrolla (o tira de) el hilo. Con un brazo o polea de ~1 cm de radio, el tirón disponible (~1,8–2,2 kg·cm) es de ~2 kg: sobra para un dedo ligero.
- **Apertura:** el servo vuelve y afloja el hilo; el dedo regresa a su posición abierta por la elasticidad propia de la mano (articulación flexible, elástico o resorte).
- **Posición "abierto" del servo:** el hilo debe quedar **tenso pero sin tirar** del dedo. Si queda muy flojo, se enreda; si queda tenso de más, el dedo no se extiende del todo. Se ajusta con la calibración.
- **Posición "cerrado" del servo:** hasta donde el dedo cierra sin que el servo fuerce (si zumba, retroceder). Nunca forzar contra el tope del dedo.
- Montar siempre con la **mano abierta** y la fuente de 12 V **apagada**. Al energizar, un servo puede dar un tirón inicial.
- Sentido de giro: si un dedo necesita el sentido contrario, no se cambia el cableado: en la calibración el pulso "abierto" simplemente queda mayor que el "cerrado".

---

## 9. Checklist antes de energizar la fuente

- [ ] Fuente de 12 V (no más) conectada solo al conector DC de la breakout.
- [ ] Medido con multímetro: 5V–GND de la breakout entre 4,8 y 5,3 V, antes de conectar los servos.
- [ ] Todos los marrones al GND de la breakout y todos los rojos al **5V** (nunca a VIN/12 V ni a 3V3).
- [ ] Cada naranja en el GPIO de la tabla 4.1.
- [ ] Condensador con la polaridad correcta.
- [ ] Mano en posición abierta.
- [ ] Fuente encendida primero y luego el USB/REPL.

---

## 10. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El servo vibra o se mueve solo | Falta GND común | Unir GND de la fuente con GND de la ESP32 |
| La placa se reinicia al mover varios servos | Caída de voltaje por el pico de corriente | Más cable grueso, condensador, subir los límites de velocidad (rampa más lenta) o fuente más potente |
| Servo zumba sin moverse | Forzando contra un tope (mecánico o de calibración) | Cortar la señal (`duty_ns(0)`) y calibrar un extremo más cerca del centro |
| Servo caliente | Mantiene posición bajo mucha carga o fuerza contra el tope | Reducir el recorrido, aflojar el hilo en reposo |
| No se mueve nada | Fuente apagada, GND, pin equivocado | Revisar checklist de la sección 9 |
| Se mueve al revés | Sentido invertido | Intercambiar los pulsos abierto/cerrado en la calibración |

---

## 11. Estructura del proyecto

```
mano-robotica-senas/
├── README.md                ← este archivo
├── firmware/                ← lo que se sube a la ESP32 (MicroPython)
│   ├── boot.py              ← deja los pines de servo en 0 V al arrancar
│   ├── config.py            ← pines, límites, velocidades, calibración por defecto, EJES_ACTIVOS
│   ├── calibracion.py       ← lee y guarda calibracion.json en la placa
│   ├── servo.py             ← un servo MG90S (pulso → PWM)
│   ├── mano.py              ← los 6 ejes: rampa, velocidad por dedo, ángulos editables
│   ├── poses.py             ← las poses: punio, ok, rock
│   ├── control.py           ← única puerta de comandos (REPL, servidor serial, futuro Kinect/voz)
│   ├── servidor_serial.py   ← atiende comandos por USB (lo usa la app)
│   ├── prueba_servo.py      ← prueba de un servo suelto desde el REPL (etapa A)
│   └── main.py              ← no arranca nada solo (deja el REPL libre)
├── herramientas/            ← lo que corre en la PC
│   ├── app_mano.py          ← app de Streamlit
│   ├── enlace.py            ← enlace serial a la placa y enlace simulado
│   ├── unidades.py          ← µs ↔ grados (aproximado)
│   ├── subir_firmware.py    ← sube el firmware con mpremote
│   └── requirements.txt
├── pruebas/                 ← pruebas automáticas (sin placa ni navegador)
└── docs/
```

### 11.1 Subir el firmware a la placa

Cierra antes todo lo que tenga abierto el puerto (la app conectada, Thonny, un REPL):

```
python herramientas/subir_firmware.py COM5
```

El puerto es el del chip CH343 (el que muestra el REPL). No borra nada de la placa.

### 11.2 App de Streamlit

```
pip install -r herramientas/requirements.txt
streamlit run herramientas/app_mano.py
```

En la barra lateral se elige **Simulado (sin placa)** (mano virtual con el mismo firmware, útil para probar sin la mano) o **Placa por USB**. Al conectar, la app interrumpe lo que corra la placa y arranca `servidor_serial`; al desconectar lo detiene y deja libre el REPL. **Un solo programa puede usar el puerto a la vez**: app o REPL.

| Pestaña | Qué permite |
|---|---|
| Poses | ✊ Puño, 👌 OK, 🤘 Rock, abrir y cerrar la mano |
| Un dedo | Elegir el dedo, moverlo a un % (0 abierto, 100 cerrado), abrir/cerrar/soltar solo ese dedo, y su propia velocidad de cierre y apertura |
| Velocidad | Velocidad de cierre y apertura de toda la mano (µs/s) |
| Ángulos | Pulsos de abierto y cerrado de cada dedo, en grados (aprox.) o µs; aplicar, probar abierto/cerrado y **guardar en la placa** (`calibracion.json`) |
| Registro | Los últimos comandos y respuestas |

Flujo de calibración: ajustar → *Aplicar* (no mueve el servo) → *Probar abierto/cerrado* mirando el dedo → *Guardar*. El dedo, la velocidad y los pulsos respetan los límites duros del firmware.

### 11.3 Comandos (REPL y servidor serial)

La misma puerta para todo (`firmware/control.py`). Cada comando es una línea de texto y la respuesta es `OK`, `OK {json}` o `ERR mensaje`:

| Comando | Qué hace |
|---|---|
| `PING` / `ESTADO` | Comprueba la conexión / devuelve posición, pulsos, calibración, velocidades y poses (json) |
| `POSE punio\|ok\|rock` | Lleva la mano a la pose: **primero los 4 dedos y, cuando llegan, el pulgar** |
| `CERRAR` | Cierra la mano: **primero índice, medio, anular y meñique; cuando los 4 llegan (y tras una pausa de 0,3 s), el pulgar** |
| `ABRIR` | Abre la mano en orden inverso: **primero el pulgar y luego los 4 dedos** (así el pulgar no se engancha con los dedos) |
| `DEDO <eje> <0.0-1.0>` | Un dedo (0 abierto, 1 cerrado) |
| `MOVER <eje>=<v> ...` | Varios dedos a la vez |
| `VEL <cierre> <apertura> [<eje>]` | Velocidad en µs/s; sin eje, todos |
| `ANGULOS <eje> <abierto> <cerrado>` | Pulsos de abrir y cerrar (µs); no mueve el servo ni guarda |
| `GUARDAR` | Guarda los pulsos en `calibracion.json` de la placa |
| `DETENER` / `SOLTAR [<eje>]` | Congela / corta la señal |

Desde el REPL (sin app):

```python
import mano, control
c = control.Control(mano.crear_mano(["indice", "medio", "anular"]))
c.ejecutar("POSE ok", esperar=True)
c.ejecutar("DEDO medio 0.5", esperar=True)
```

El orden dedos → pulgar es **por eventos** (el pulgar arranca cuando los dedos terminaron de llegar, no por un tiempo fijo) y se configura en `firmware/config.py`: `GRUPO_DEDOS`, `GRUPO_PULGAR` y `PAUSA_ENTRE_ETAPAS_MS` (0,3 s por defecto). Un `DEDO` o `MOVER` directo cancela las etapas pendientes.

Las poses están en `firmware/poses.py` con valores a ojo (hay que afinarlas con la mano armada). Los dedos que no estén en `config.EJES_ACTIVOS` (o en la lista dada a `crear_mano`) se ignoran en las poses.

### 11.4 Pruebas en la PC (sin placa)

```
python -m unittest discover -s pruebas -v
```

84 pruebas: movimiento y calibración, poses, orden por etapas, comandos, servidor, enlace serial (con un puerto falso y con reinicio automático) y la app de Streamlit completa en modo simulado.

---

## 12. Calibración medida con los servos reales (2026-10-17)

Datos tomados en la placa, con el montaje y el hilo reales. Se actualizan a medida que se prueban los demás dedos.

### 12.1 Límites del servo (sin carga y con el hilo del dedo)

| Medida | Resultado |
|---|---|
| Recorrido | Cerca de media vuelta (≈180° o algo más) |
| Lado de pulsos mayores | Zumbido del tope desde ~2300 µs; con el hilo puesto, a 2700 µs un servo no volvió al centro y a 2650 µs se calentó |
| Lado de pulsos menores | El brazo sigue avanzando por debajo de 600 µs (probado hasta 400 µs), con zumbido en los extremos |
| Límites duros del firmware | `PULSO_MIN_US = 300`, `PULSO_MAX_US = 2700` (techos absolutos, no pulsos de trabajo) |

### 12.2 Pulso de cada dedo (abierto → cerrado)

| Dedo | GPIO | Abierto (µs) | Cerrado (µs) | Sentido | Estado |
|---|---|---|---|---|---|
| `indice` | 8 | 600 | 2600 | normal | **calibrado** (2026-10-19) |
| `medio` | 9 | 400 | 2600 | normal | **calibrado** (2026-10-19) |
| `anular` | 10 | 400 | 2600 | normal | **calibrado** (2026-10-19) |
| `menique` | 11 | 2600 | 300 | **invertido** (cierra al bajar el pulso) | **calibrado** (2026-10-19) |
| `pulgar_flexion` | 12 | 800 | 2700 | normal | cerrado en el máximo del firmware (2700) para que flexione lo más posible (2026-10-20); vigilar calentamiento; pendiente por un problema físico del pulgar |
| `pulgar_oposicion` | 13 | 800 | 1800 | normal | recorrido reducido a 800–1800 (2026-10-20); pendiente por un problema físico del pulgar |

Notas de la calibración:
- Cada servo puede quedar montado en un sentido distinto. No se cambia el cableado: en la calibración el "abierto" simplemente queda mayor que el "cerrado" (caso del meñique y del pulgar).
- **Cada vez que se aprieta o se remonta el brazo de un servo cambia la relación pulso–ángulo**: hay que recalibrar ese dedo.
- Los pulsos de trabajo están muy cerca de los límites duros del firmware (300 a 2700 µs). Un servo forzado contra su tope zumba, se calienta y puede no volver al centro: si un dedo no llega a abrir o cerrar del todo con estos valores, la causa es mecánica (hilo destensado, polea o brazo), no hay que subir más el pulso.
- Velocidad: el firmware usa 700 µs/s al cerrar y 400 µs/s al abrir (se abre más despacio para no dejar el hilo flojo). Se cambia desde la app o con `VEL`.
- Un pin de señal sin conducir capta el PWM de los cables vecinos: `boot.py` y `mano.aislar_pines()` fuerzan a 0 V los pines no usados.

---

## 13. Estado del desarrollo (última actualización: 2026-10-21)

- [x] README y estructura
- [x] Pruebas de servos sueltos y con hilo
- [x] Firmware base (`config`, `calibracion`, `servo`, `mano`, `boot`), subido y probado en la placa
- [x] Poses (`punio`, `ok`, `rock`) y `control.py` (única puerta de comandos)
- [x] Servidor serial, verificado con la placa real (si la placa no responde al conectar, la app la reinicia sola y reintenta)
- [x] Cerrar la mano y las poses por etapas: primero los 4 dedos y al llegar el pulgar; abrir al revés (probado en la placa real)
- [x] App de Streamlit (poses, un dedo, velocidad, ángulos, registro): probada en modo simulado y su comunicación con la placa verificada
- [x] 84 pruebas automáticas en la PC (movimiento, calibración, poses, orden por etapas, comandos, servidor, enlace y app)
- [x] **Cuatro dedos calibrados**: índice, medio, anular y meñique
- [ ] Pulgar (flexión y oposición): pendiente por un problema físico
- [ ] Afinar las poses (`ok`, `rock`) con la mano completa armada
- [ ] Probar la app de Streamlit manejando la mano real
- [ ] Revisión de calidad del código
- [ ] Kinect (la PC manda las posiciones de los dedos) y voz local en la placa

### 13.1 Calibración vigente en la placa y en `firmware/config.py`

Ver la tabla de la sección 12.2. Límites duros: 300 a 2700 µs. Velocidades: cerrar 700 µs/s, abrir 400 µs/s.

### 13.2 Pendientes

1. **Pulgar:** resolver el problema físico, confirmar el sentido de cada servo y afinar sus pulsos.
2. **Poses:** ajustar los valores de `firmware/poses.py` con la mano completa.
3. **App con la mano real:** conectar la app a la placa y probar poses y ajustes de calibración desde ahí.
4. Volver el mínimo duro de 300 a 400 µs si ya no hace falta (se bajó solo por pruebas).
5. Si un dedo no abre en conjunto con los demás: medir el voltaje 5V–GND de la breakout con todos cerrados (debe quedar sobre ~4,5 V).
6. Revisión de calidad y, después, Kinect y voz.

### 13.3 Lecciones de esta sesión

- El puerto del REPL de esta placa es el del **chip CH343** (COM5 en esta sesión). El conector USB nativo no mostró REPL.
- Crear el PWM con `duty_ns=0` falla en MicroPython 1.29; se usa `duty_u16=0`.
- Un pin de señal sin conducir capta el PWM de los cables vecinos y mueve su servo solo: `boot.py` y `mano.aislar_pines()` fuerzan a 0 V los pines no usados.
- Cada vez que se aprieta o se remonta el brazo del servo, cambia la relación pulso–ángulo: hay que recalibrar. Conviene montar el brazo con el servo sostenido en una posición de referencia.
- La placa se reutilizó de otro proyecto (un asistente de voz); se limpió antes de subir este firmware.
