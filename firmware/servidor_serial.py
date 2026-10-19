"""Servidor de comandos por el puerto serie (USB) de la placa.

Lee una linea de texto por comando, la ejecuta con control.Control y responde
una linea que empieza por "@" (asi la PC la distingue del eco del REPL):

    @OK            @OK {json}            @ERR mensaje

Mientras corre, el REPL no esta disponible (el puerto serie es uno solo):
Ctrl+C lo detiene y devuelve el REPL. La app de Streamlit lo arranca sola.

Arranque a mano:
    >>> import servidor_serial
    >>> servidor_serial.iniciar()
"""

import config
import control as _control


class Servidor:
    """Acumula caracteres y ejecuta cada linea completa. Sin E/S propia:
    `escribir(texto)` se inyecta (print en la placa, una lista en pruebas)."""

    def __init__(self, control, escribir):
        self._control = control
        self._escribir = escribir
        self._buffer = ""

    def alimentar(self, texto):
        for caracter in texto:
            if caracter in "\r\n":
                linea, self._buffer = self._buffer.strip(), ""
                if linea:
                    self._responder(linea)
            else:
                self._buffer += caracter

    def _responder(self, linea):
        try:
            respuesta = self._control.ejecutar(linea)
        except Exception as error:  # un comando raro no debe tumbar el servidor
            respuesta = "ERR interno: {}".format(error)
        self._escribir("@" + respuesta + "\n")


def iniciar(ejes=None):
    """Crea la mano con los ejes conectados (por defecto config.EJES_ACTIVOS)
    y atiende comandos hasta Ctrl+C."""
    import select
    import sys

    import mano as _mano

    mano = _mano.crear_mano(ejes if ejes is not None else config.EJES_ACTIVOS)
    servidor = Servidor(_control.Control(mano), sys.stdout.write)
    sondeo = select.poll()
    sondeo.register(sys.stdin, select.POLLIN)

    sys.stdout.write("@LISTO ejes=" + ",".join(mano.ejes()) + "\n")
    try:
        while True:
            sondeo.poll(config.PERIODO_MS)  # espera como mucho un periodo, o menos si llega algo
            while sondeo.poll(0):
                servidor.alimentar(sys.stdin.read(1))
            mano.actualizar()
    finally:
        mano.detener()
