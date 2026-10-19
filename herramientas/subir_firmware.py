"""Sube el firmware de la mano a la placa con mpremote.

    python herramientas/subir_firmware.py COM5

Copia solo los archivos del firmware; no borra nada de la placa. Cierra antes
cualquier programa que tenga abierto el puerto (la app de Streamlit
conectada, Thonny, un REPL).
"""

import os
import subprocess
import sys

ARCHIVOS = [
    "boot.py", "config.py", "calibracion.py", "servo.py", "mano.py",
    "poses.py", "control.py", "servidor_serial.py", "main.py", "prueba_servo.py",
]
CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "firmware")


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python herramientas/subir_firmware.py COM<n>")
    puerto = sys.argv[1]
    rutas = [os.path.join(CARPETA, a) for a in ARCHIVOS]
    faltan = [r for r in rutas if not os.path.exists(r)]
    if faltan:
        sys.exit("Faltan archivos: {}".format(faltan))
    comando = [sys.executable, "-m", "mpremote", "connect", puerto, "cp"] + rutas + [":"]
    print("Subiendo {} archivos a {}...".format(len(rutas), puerto))
    if subprocess.run(comando).returncode != 0:
        sys.exit("No se pudo subir. ¿El puerto está libre y es el del chip CH343 (REPL)?")
    print("Listo. Ahora puedes conectar desde la app o usar el REPL.")


if __name__ == "__main__":
    main()
