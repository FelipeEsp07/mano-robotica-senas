"""Poses de la mano: un valor de 0.0 (abierto) a 1.0 (cerrado) por eje.

pulgar_flexion: 0.0 = pulgar extendido, 1.0 = doblado.
pulgar_oposicion: 0.0 = al costado de la palma, 1.0 = cruzado hacia la palma.

Los valores son un primer ajuste a ojo: se afinan con la mano armada
(editando este archivo). Un eje que la mano no tiene conectado se ignora
(ver control.py).
"""

POSES = {
    # Punio: todos los dedos y el pulgar completamente cerrados.
    "punio": {
        "indice": 1.0, "medio": 1.0, "anular": 1.0, "menique": 1.0,
        "pulgar_flexion": 1.0, "pulgar_oposicion": 1.0,
    },
    # OK: la punta del indice toca la del pulgar; los otros tres dedos extendidos.
    "ok": {
        "indice": 0.75, "medio": 0.0, "anular": 0.0, "menique": 0.0,
        "pulgar_flexion": 0.6, "pulgar_oposicion": 1.0,
    },
    # Rock: indice y menique extendidos; medio y anular doblados y el pulgar sobre ellos.
    "rock": {
        "indice": 0.0, "medio": 1.0, "anular": 1.0, "menique": 0.0,
        "pulgar_flexion": 1.0, "pulgar_oposicion": 1.0,
    },
}
