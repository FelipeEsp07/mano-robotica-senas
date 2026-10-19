# Configuracion de la mano robotica. Ajustar SOLO estos valores.

# --- Ejes de la mano (6 servos MG90S) ---
# Cada eje se mueve con un valor normalizado: 0.0 = reposo (hilo flojo, dedo
# abierto), 1.0 = activo (hilo tirado, dedo cerrado). Ver README.md, seccion 4.
EJES = ("indice", "medio", "anular", "menique", "pulgar_flexion", "pulgar_oposicion")

# GPIO de la senal de cada servo. Reservados para fases futuras (no usar):
# 4/5/6 microfono, 7 LED, 15/16/17 amplificador.
PINES = {
    "indice": 8,
    "medio": 9,
    "anular": 10,
    "menique": 11,
    "pulgar_flexion": 12,
    "pulgar_oposicion": 13,
}

# --- Senal PWM de los servos ---
FRECUENCIA_HZ = 50

# Limites duros del pulso, en microsegundos. Ningun servo recibe nunca un
# pulso fuera de este rango, ni siquiera durante la calibracion: protege el
# servo si se prueba un extremo sin saber hasta donde llega. El MG90S
# estandar recorre ~180 grados con 500-2400 us. Medido en la prueba real de
# los servos GPIO8 y GPIO9 (2026-10-17): zumban al forzar el tope desde
# ~2300 us; 2400 queda como maximo absoluto, NO como pulso de trabajo (los
# pulsos "cerrado" calibrados deben quedar por debajo del zumbido). Del lado
# izquierdo el brazo siguio avanzando por debajo de 600 us (probado hasta
# 400 us, fuera de la especificacion tipica de 500 us), con zumbido en los
# extremos: 400 us queda como minimo absoluto, no como pulso de trabajo.
# Con el hilo del dedo puesto (GPIO8, 2026-10-17) se probo hasta 2700 us: a 2700
# el servo no volvio al centro, y se calento al pasar de 2600. 2600 us queda
# como maximo absoluto (no como pulso de trabajo; se esta probando 2500).
PULSO_MIN_US = 300
PULSO_MAX_US = 2700

# --- Calibracion por defecto: (pulso "abierto" en us, pulso "cerrado" en us) ---
# indice/medio: medidos a ojo con el hilo puesto (README, seccion 12).
# anular, menique y pulgar (2026-10-19, ya conectados): mismos pulsos que indice/medio
# pero INVERTIDOS (abierto 2600, cerrado 800); valores a confirmar con la mano armada.
# Si un dedo necesita el sentido contrario, basta con que "abierto" sea
# MAYOR que "cerrado": no se cambia nada mas. Los valores calibrados se
# guardan en calibracion.json en la placa y tienen prioridad sobre estos.
CALIBRACION_DEFECTO = {
    "indice": (800, 2600),
    "medio": (400, 2600),
    "anular": (400, 2600),
    "menique": (2600, 400),
    "pulgar_flexion": (2600, 400),
    "pulgar_oposicion": (2600, 400),
}
DIFERENCIA_MIN_US = 100  # recorrido minimo entre "abierto" y "cerrado" (evita una calibracion degenerada)
RUTA_CALIBRACION = "calibracion.json"

# --- Movimiento ---
# Velocidades en us de pulso por segundo (~1000 us equivalen a ~90 grados).
# Cerrar tira del hilo (con carga); abrir lo afloja, y el dedo regresa solo
# por su elasticidad, asi que se abre mas despacio para no dejar el hilo
# flojo y enredado.
VELOCIDAD_CIERRE_US_S = 700
VELOCIDAD_APERTURA_US_S = 400
VELOCIDAD_MIN_US_S = 20     # limites de velocidad aceptados al cambiarla (desde la app o el REPL)
VELOCIDAD_MAX_US_S = 3000
PERIODO_MS = 20           # cada cuanto se avanza el movimiento (igual al periodo del PWM)
MAX_PASO_MS = 100         # tope de tiempo contado en un solo avance (evita saltos tras una pausa larga)
RETARDO_ESCALON_MS = 60   # al abrir/cerrar toda la mano, cada servo arranca este tiempo despues del anterior
                          # (evita que los 6 pidan su pico de corriente al mismo instante)

# --- Ejes con servo conectado (los que mueve el servidor serial y las poses) ---
# Los demas quedan aislados a 0 V. Cambiar cuando se conecten o retiren servos.
EJES_ACTIVOS = EJES
