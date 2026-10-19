"""Unica puerta de comandos de la mano.

Lo usan por igual el REPL, el servidor serial (servidor_serial.py) y, mas
adelante, la voz y el Kinect. Cada comando es una linea de texto y la
respuesta es una sola linea:  "OK"  /  "OK {json}"  /  "ERR mensaje".

Comandos (no distinguen mayusculas; los numeros van con punto decimal):
  PING                              comprueba que responde
  ESTADO                            posicion, pulsos, calibracion y velocidades (json)
  POSE <nombre>                     punio, ok, rock (ver poses.py)
  ABRIR | CERRAR                    toda la mano (arranque escalonado)
  DEDO <eje> <valor>                un eje a 0.0 (abierto) .. 1.0 (cerrado)
  MOVER <eje>=<valor> ...           varios ejes a la vez
  VEL <cierre> <apertura> [<eje>]   velocidad en us/s; sin eje = todos los dedos
  ANGULOS <eje> <abierto> <cerrado> pulsos de abrir/cerrar en us (no mueve el servo)
  GUARDAR                           guarda los ANGULOS en calibracion.json de la placa
  DETENER                           congela donde esta (sigue sosteniendo)
  SOLTAR [<eje>]                    corta la senal (el servo deja de sostener)

Uso en el REPL:
    import mano, control
    c = control.Control(mano.crear_mano())
    c.ejecutar("POSE ok", esperar=True)
"""

import json

import config
from poses import POSES


class Control:
    def __init__(self, mano, poses=None):
        self._mano = mano
        self._poses = POSES if poses is None else poses

    # --- Entrada ---

    def ejecutar(self, linea, esperar=False):
        """Ejecuta una linea y devuelve la respuesta ("OK", "OK {json}" o
        "ERR ..."). Nunca lanza: los errores de uso salen como "ERR ...".
        Con `esperar`, no devuelve hasta que termina el movimiento (REPL);
        sin el, el movimiento avanza con mano.actualizar() (servidor)."""
        partes = linea.strip().split()
        if not partes:
            return "ERR linea vacia"
        orden = partes[0].upper()
        argumentos = partes[1:]
        manejador = getattr(self, "_cmd_" + orden.lower(), None)
        if manejador is None:
            return "ERR comando desconocido: {}".format(partes[0])
        try:
            datos = manejador(argumentos, esperar)
            if esperar:
                self._mano.esperar()
        except (ValueError, KeyError) as error:
            return "ERR {}".format(error)
        if datos is None:
            return "OK"
        return "OK " + json.dumps(datos)

    # --- Comandos ---

    def _cmd_ping(self, args, esperar):
        return None

    def _cmd_estado(self, args, esperar):
        mano = self._mano
        return {
            "ejes": list(mano.ejes()),
            "valores": mano.estado(),
            "pulsos": mano.pulsos(),
            "calibracion": {eje: list(par) for eje, par in mano.calibracion().items()},
            "velocidades": {eje: list(par) for eje, par in mano.velocidades().items()},
            "limites_us": [config.PULSO_MIN_US, config.PULSO_MAX_US],
            "limites_vel": [config.VELOCIDAD_MIN_US_S, config.VELOCIDAD_MAX_US_S],
            "poses": sorted(self._poses),
            "moviendo": mano.moviendo(),
        }

    def _cmd_pose(self, args, esperar):
        if len(args) != 1:
            raise ValueError("uso: POSE <nombre>")
        nombre = args[0].lower()
        if nombre not in self._poses:
            raise ValueError("pose desconocida: {} (poses: {})".format(nombre, ", ".join(sorted(self._poses))))
        presentes = self._mano.ejes()
        self._mano.mover({eje: v for eje, v in self._poses[nombre].items() if eje in presentes}, esperar=False)

    def _cmd_abrir(self, args, esperar):
        self._mano.abrir(esperar=False)

    def _cmd_cerrar(self, args, esperar):
        self._mano.cerrar(esperar=False)

    def _cmd_dedo(self, args, esperar):
        if len(args) != 2:
            raise ValueError("uso: DEDO <eje> <valor 0.0-1.0>")
        self._mano.dedo(args[0].lower(), _numero(args[1]), esperar=False)

    def _cmd_mover(self, args, esperar):
        if not args:
            raise ValueError("uso: MOVER <eje>=<valor> ...")
        valores = {}
        for par in args:
            if "=" not in par:
                raise ValueError("falta '=' en {!r} (uso: eje=valor)".format(par))
            eje, valor = par.split("=", 1)
            valores[eje.lower()] = _numero(valor)
        self._mano.mover(valores, esperar=False)

    def _cmd_vel(self, args, esperar):
        if len(args) not in (2, 3):
            raise ValueError("uso: VEL <cierre_us_s> <apertura_us_s> [<eje>]")
        eje = args[2].lower() if len(args) == 3 else None
        self._mano.fijar_velocidad(_numero(args[0]), _numero(args[1]), eje)

    def _cmd_angulos(self, args, esperar):
        if len(args) != 3:
            raise ValueError("uso: ANGULOS <eje> <abierto_us> <cerrado_us>")
        self._mano.fijar_calibracion(args[0].lower(), _numero(args[1]), _numero(args[2]))

    def _cmd_guardar(self, args, esperar):
        self._mano.guardar_calibracion()

    def _cmd_detener(self, args, esperar):
        self._mano.detener()

    def _cmd_soltar(self, args, esperar):
        self._mano.soltar(args[0].lower() if args else None)


def _numero(texto):
    try:
        return float(texto)
    except ValueError:
        raise ValueError("no es un numero: {!r}".format(texto))
