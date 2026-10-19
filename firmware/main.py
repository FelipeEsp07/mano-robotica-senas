"""Punto de entrada de la mano robotica.

MicroPython ejecuta main.py al arrancar la placa. Este archivo no mueve nada
al encender, para que el REPL quede libre y los servos no reciban senal sola.
Para usar la mano:

    >>> import mano
    >>> m = mano.crear_mano()      # o crear_mano(["indice"]) con un solo servo
    >>> m.cerrar()
    >>> m.dedo("indice", 0.5)
    >>> m.abrir()
"""
