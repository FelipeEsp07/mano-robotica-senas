"""Conversion entre pulso (us) y grados aproximados de un servo de 180 grados.

La relacion es solo de referencia: se toma 500 us = 0 grados y 2500 us =
180 grados (centro 1500 us = 90 grados). Cada servo real se aparta un poco
de eso; lo que manda al servo siempre son los microsegundos.
"""

US_EN_CERO_GRADOS = 500
US_POR_GRADO = 2000 / 180


def us_a_grados(pulso_us):
    return (pulso_us - US_EN_CERO_GRADOS) / US_POR_GRADO


def grados_a_us(grados):
    return US_EN_CERO_GRADOS + grados * US_POR_GRADO
