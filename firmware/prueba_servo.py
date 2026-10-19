"""Prueba de un servo suelto desde el REPL (README, etapa A).

Sirve para comprobar que el servo funciona y hasta donde recorre, antes de
usar mano.py. Respeta los limites duros de 300 a 2700 us.

    >>> import prueba_servo as p
    >>> p.iniciar(8)          # GPIO8; no envia senal todavia
    >>> p.ir_a(1500)          # centro (~90 grados)
    >>> p.ir_a(1700)          # un poco hacia un lado
    >>> p.barrido(1500, 2000) # recorre despacio de 1500 a 2000 us
    >>> p.soltar()            # corta la senal
"""

import time
from machine import PWM, Pin

# Autonomo a proposito: NO importa config.py (la placa tiene el config.py del
# asistente de voz). Mismos valores que el config.py de la mano.
FRECUENCIA_HZ = 50
PULSO_MIN_US = 300
PULSO_MAX_US = 2700

_pwm = None
_pulso_us = None


def iniciar(pin=8):
    """Prepara el PWM en `pin` SIN enviar senal (el servo no se mueve)."""
    global _pwm, _pulso_us
    soltar()
    if _pwm is not None:
        _pwm.deinit()
    _pwm = PWM(Pin(pin), freq=FRECUENCIA_HZ, duty_u16=0)
    _pulso_us = None


def ir_a(pulso_us):
    """Manda `pulso_us` (recortado a los limites duros) y lo imprime."""
    global _pulso_us
    if _pwm is None:
        raise RuntimeError("llama primero a iniciar(pin)")
    _pulso_us = int(min(max(pulso_us, PULSO_MIN_US), PULSO_MAX_US))
    _pwm.duty_ns(_pulso_us * 1000)
    print("pulso = {} us".format(_pulso_us))


def barrido(desde_us, hasta_us, paso_us=10, pausa_ms=40):
    """Recorre de `desde_us` a `hasta_us` en pasos chicos. Detenlo con Ctrl+C
    apenas el servo zumbe contra su tope, y anota el ultimo pulso impreso."""
    paso_us = abs(paso_us) if hasta_us >= desde_us else -abs(paso_us)
    pulso = desde_us
    while (pulso - hasta_us) * (1 if paso_us > 0 else -1) <= 0:
        ir_a(pulso)
        time.sleep_ms(pausa_ms)
        pulso += paso_us


def soltar():
    """Corta la senal: el servo queda libre."""
    global _pulso_us
    if _pwm is not None:
        _pwm.duty_ns(0)
    _pulso_us = None
