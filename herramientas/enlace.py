"""Enlaces entre la app (PC) y la mano.

Los dos hablan igual: `enviar("POSE ok")` devuelve la respuesta de una linea
("OK", "OK {json}" o "ERR ...") del protocolo de firmware/control.py.

- EnlaceSerial: la placa real por USB. Arranca servidor_serial en la placa.
- EnlaceSimulado: la misma logica del firmware (Control + Mano) sobre servos
  falsos y un reloj falso, para usar y probar la app sin la mano.
"""

import json
import os
import sys
import tempfile
import time

RUTA_FIRMWARE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "firmware")
if RUTA_FIRMWARE not in sys.path:
    sys.path.insert(0, RUTA_FIRMWARE)

import config  # noqa: E402  (firmware/config.py)
from control import Control  # noqa: E402
from mano import Mano  # noqa: E402
from servo import Servo  # noqa: E402


def parsear(respuesta):
    """(ok, datos): para "OK {json}" -> (True, dict); "OK" -> (True, None);
    "ERR mensaje" -> (False, "mensaje")."""
    if respuesta.startswith("OK"):
        resto = respuesta[2:].strip()
        return True, (json.loads(resto) if resto else None)
    if respuesta.startswith("ERR"):
        return False, respuesta[3:].strip()
    return False, "respuesta inesperada: {!r}".format(respuesta)


def listar_puertos():
    """[(dispositivo, descripcion)] de los puertos serie de la PC."""
    from serial.tools import list_ports

    return [(p.device, p.description) for p in sorted(list_ports.comports())]


class EnlaceSerial:
    """La placa real. `abrir_serie(puerto, baudios, timeout)` se inyecta para
    poder probarlo sin hardware (por defecto serial.Serial)."""

    def __init__(self, puerto, baudios=115200, abrir_serie=None):
        if abrir_serie is None:
            import serial

            abrir_serie = serial.Serial
        self.puerto = puerto
        self._serie = abrir_serie(puerto, baudios, timeout=0.1)
        self._pendiente = b""

    def iniciar_servidor(self, timeout_s=20.0):
        """Interrumpe lo que corra la placa y arranca servidor_serial. Lanza
        RuntimeError si no responde "@LISTO" (con lo que dijo la placa)."""
        self._serie.write(b"\r\x03\x03\x02")  # interrumpir, y salir de REPL crudo si estaba
        time.sleep(0.4)
        self._serie.reset_input_buffer()
        self._serie.write(b"import servidor_serial; servidor_serial.iniciar()\r\n")
        visto = self._leer_hasta(lambda texto: "@LISTO" in texto, timeout_s)
        if "@LISTO" not in visto:
            raise RuntimeError("La placa no arranco el servidor. Respondio: {!r}".format(visto[-300:]))
        self._pendiente = b""

    def enviar(self, linea, timeout_s=4.0):
        self._serie.reset_input_buffer()
        self._serie.write((linea.strip() + "\n").encode())
        # una respuesta completa es una linea que empieza por "@" y ya termino en salto de linea
        visto = self._leer_hasta(
            lambda texto: any(renglon.startswith("@") for renglon in texto.split("\n")[:-1]), timeout_s)
        for renglon in visto.split("\n")[:-1]:
            if renglon.startswith("@"):
                return renglon[1:].strip()
        raise TimeoutError("La placa no respondio a {!r}".format(linea))

    def _leer_hasta(self, condicion, timeout_s):
        fin = time.monotonic() + timeout_s
        texto = ""
        while time.monotonic() < fin:
            datos = self._serie.read(self._serie.in_waiting or 1)
            if datos:
                texto += datos.decode("utf-8", errors="replace")
                if condicion(texto):
                    break
        return texto

    def cerrar(self):
        """Detiene el servidor (Ctrl+C) para dejar libre el REPL y cierra el puerto."""
        try:
            self._serie.write(b"\x03")
        finally:
            self._serie.close()


class _PwmFalso:
    def duty_ns(self, valor):
        pass


class _RelojFalso:
    def __init__(self):
        self.ms = 1000

    def __call__(self):
        return self.ms

    def dormir(self, ms):
        self.ms += ms


class EnlaceSimulado:
    """Mano virtual: el firmware real (Control + Mano) con servos falsos. Cada
    comando se completa al instante, pero `ultima_duracion_s` dice cuanto
    habria tardado la mano real con las velocidades vigentes."""

    puerto = "simulado"

    def __init__(self, ejes=None):
        # guardar_calibracion() escribiria calibracion.json en la carpeta actual:
        # en el simulador va a un archivo temporal.
        config.RUTA_CALIBRACION = os.path.join(tempfile.mkdtemp(prefix="mano_sim_"), "calibracion.json")
        ejes = tuple(ejes) if ejes is not None else tuple(config.EJES_ACTIVOS)
        self._reloj = _RelojFalso()
        servos = {e: Servo(_PwmFalso(), config.PULSO_MIN_US, config.PULSO_MAX_US) for e in ejes}
        self._mano = Mano(servos, dict(config.CALIBRACION_DEFECTO), self._reloj, self._reloj.dormir)
        self._control = Control(self._mano)
        self.ultima_duracion_s = 0.0

    def iniciar_servidor(self, timeout_s=0):
        pass

    def enviar(self, linea, timeout_s=0):
        respuesta = self._control.ejecutar(linea)
        inicio = self._reloj()
        while self._mano.actualizar():
            self._reloj.dormir(config.PERIODO_MS)
        self.ultima_duracion_s = (self._reloj() - inicio) / 1000
        return respuesta

    def cerrar(self):
        pass
