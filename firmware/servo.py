"""Un servo MG90S: pulso en microsegundos -> PWM de 50 Hz.

`pwm` es cualquier objeto con duty_ns(valor) (en la placa, machine.PWM ya
creado a config.FRECUENCIA_HZ); asi la logica se prueba en la PC sin placa.
Con duty_ns(0) no hay senal y el servo queda libre.
"""


class Servo:
    def __init__(self, pwm, pulso_min_us, pulso_max_us):
        self._pwm = pwm
        self._pulso_min_us = pulso_min_us
        self._pulso_max_us = pulso_max_us
        self._pulso_us = None  # None = sin senal

    @property
    def pulso_us(self):
        """Ultimo pulso enviado, o None si el servo esta suelto."""
        return self._pulso_us

    def mover_a_us(self, pulso_us):
        """Envia `pulso_us`, recortado a los limites duros. Devuelve el
        pulso realmente enviado."""
        pulso_us = int(round(min(max(pulso_us, self._pulso_min_us), self._pulso_max_us)))
        self._pwm.duty_ns(pulso_us * 1000)
        self._pulso_us = pulso_us
        return pulso_us

    def soltar(self):
        """Corta la senal: el servo deja de sostener su posicion."""
        self._pwm.duty_ns(0)
        self._pulso_us = None
