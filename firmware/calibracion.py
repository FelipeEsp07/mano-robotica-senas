"""Calibracion de los servos: pulso "abierto" y "cerrado" de cada eje.

Se guarda en calibracion.json en la placa como {eje: [abierto_us, cerrado_us]}.
Si el archivo no existe se usan los valores de config.CALIBRACION_DEFECTO.
"""

import json

import config


def validar(eje, abierto_us, cerrado_us):
    """Lanza ValueError si el par de pulsos no es seguro para el servo."""
    if eje not in config.PINES:
        raise ValueError("eje desconocido: {}".format(eje))
    for nombre, valor in (("abierto", abierto_us), ("cerrado", cerrado_us)):
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            raise ValueError("{}: el pulso '{}' debe ser un numero".format(eje, nombre))
        if not config.PULSO_MIN_US <= valor <= config.PULSO_MAX_US:
            raise ValueError("{}: el pulso '{}' ({}) esta fuera de {}-{} us".format(
                eje, nombre, valor, config.PULSO_MIN_US, config.PULSO_MAX_US))
    if abs(cerrado_us - abierto_us) < config.DIFERENCIA_MIN_US:
        raise ValueError("{}: abierto y cerrado deben diferir al menos {} us".format(
            eje, config.DIFERENCIA_MIN_US))


def cargar(ruta=None):
    """Calibracion completa {eje: (abierto_us, cerrado_us)}: los valores por
    defecto, con lo guardado en `ruta` por encima. Un archivo con valores
    invalidos lanza ValueError (mejor avisar que mover un servo con datos
    corruptos)."""
    ruta = ruta or config.RUTA_CALIBRACION
    calibracion = dict(config.CALIBRACION_DEFECTO)
    try:
        with open(ruta) as archivo:
            guardada = json.load(archivo)
    except OSError:
        return calibracion
    for eje, par in guardada.items():
        abierto_us, cerrado_us = par
        validar(eje, abierto_us, cerrado_us)
        calibracion[eje] = (abierto_us, cerrado_us)
    return calibracion


def guardar(calibracion, ruta=None):
    """Valida y guarda `calibracion` ({eje: (abierto_us, cerrado_us)})."""
    ruta = ruta or config.RUTA_CALIBRACION
    datos = {}
    for eje, (abierto_us, cerrado_us) in calibracion.items():
        validar(eje, abierto_us, cerrado_us)
        datos[eje] = [abierto_us, cerrado_us]
    with open(ruta, "w") as archivo:
        json.dump(datos, archivo)
