# Se ejecuta en cada arranque de la placa (tambien tras un reinicio suave).
# Deja los 6 pines de senal de los servos en 0 V desde el primer instante:
# un pin sin conducir capta ruido de los cables vecinos y mueve el servo solo.
# No mueve ningun servo (0 V = sin pulsos).
try:
    from machine import Pin
    for _pin in (8, 9, 10, 11, 12, 13):
        Pin(_pin, Pin.OUT, value=0)
except Exception as _error:
    print("[boot] No se pudieron aislar los pines:", _error)
