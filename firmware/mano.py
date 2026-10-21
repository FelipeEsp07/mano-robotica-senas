"""La mano: 6 ejes (4 dedos + 2 del pulgar) con movimiento suave.

Cada eje se manda con un valor de 0.0 (reposo: hilo flojo, dedo abierto) a
1.0 (activo: hilo tirado, dedo cerrado). El pulso real de cada extremo sale
de la calibracion (ver calibracion.py), asi el resto del programa nunca
trabaja con angulos ni microsegundos.

Reglas:
- Ningun servo recibe senal hasta su primer movimiento. Ese primer
  movimiento arranca desde el pulso "abierto" (la pose segura: la mano se
  coloca abierta antes de energizar) y avanza con rampa.
- Todo movimiento avanza con rampa de velocidad, y abrir/cerrar la mano
  entera arranca los servos escalonados: asi no se pide el pico de corriente
  de los 6 a la vez.

servos/reloj_ms/dormir_ms se inyectan: en la placa son machine.PWM,
time.ticks_ms y time.sleep_ms (ver crear_mano); en la PC se simulan.

Uso desde el REPL:
    import mano
    m = mano.crear_mano()
    m.cerrar()                  # cierra toda la mano
    m.dedo("indice", 0.5)       # el indice a la mitad
    m.abrir()
"""

import calibracion as _calibracion
import config
from servo import Servo

MASCARA_TICKS = 0x3FFFFFFF  # time.ticks_ms de MicroPython da la vuelta en 2**30


class Mano:
    def __init__(self, servos, calibracion, reloj_ms, dormir_ms):
        """servos: {eje: Servo}. calibracion: {eje: (abierto_us, cerrado_us)}
        con al menos los ejes de `servos`."""
        self._servos = servos
        self._calibracion = {}
        for eje in servos:
            abierto_us, cerrado_us = calibracion[eje]
            _calibracion.validar(eje, abierto_us, cerrado_us)
            self._calibracion[eje] = (abierto_us, cerrado_us)
        self._reloj_ms = reloj_ms
        self._dormir_ms = dormir_ms
        self._pos = {eje: None for eje in servos}       # pulso actual (us); None = sin senal
        self._objetivo = {eje: None for eje in servos}  # pulso al que va (us); None = quieto
        self._espera_ms = {eje: 0 for eje in servos}    # retraso antes de arrancar (escalonado)
        self._ultimo_ms = None                          # instante del ultimo avance; None = nada en curso
        self._vel_global = (config.VELOCIDAD_CIERRE_US_S, config.VELOCIDAD_APERTURA_US_S)
        self._vel_eje = {}                              # {eje: (cierre_us_s, apertura_us_s)} solo los que difieren
        self._etapas = []                               # etapas pendientes de mover_por_etapas (lista de {eje: valor})
        self._espera_etapa_ms = 0                       # pausa que falta antes de lanzar la siguiente etapa

    def ejes(self):
        """Ejes presentes, en el orden de config.EJES."""
        return tuple(eje for eje in config.EJES if eje in self._servos)

    # --- Validacion y conversion ---

    def _revisar_valor(self, valor):
        if not isinstance(valor, (int, float)) or isinstance(valor, bool) or not 0.0 <= valor <= 1.0:
            raise ValueError("el valor debe estar entre 0.0 y 1.0, llego {!r}".format(valor))

    def _revisar_eje(self, eje):
        if eje not in self._servos:
            raise ValueError("eje desconocido o sin servo: {!r} (ejes: {})".format(eje, ", ".join(self.ejes())))

    def _pulso_de_valor(self, eje, valor):
        abierto_us, cerrado_us = self._calibracion[eje]
        return abierto_us + (cerrado_us - abierto_us) * valor

    def _valor_de_pulso(self, eje, pulso_us):
        abierto_us, cerrado_us = self._calibracion[eje]
        return (pulso_us - abierto_us) / (cerrado_us - abierto_us)

    # --- Ordenes ---

    def mover(self, valores, esperar=True, escalonado=False):
        """Lleva varios ejes a la vez: valores = {eje: 0.0..1.0}. Se valida
        todo antes de mover nada. Con `escalonado`, cada eje arranca
        config.RETARDO_ESCALON_MS despues del anterior. Con `esperar`, no
        devuelve hasta que todos llegaron."""
        for eje, valor in valores.items():
            self._revisar_eje(eje)
            self._revisar_valor(valor)
        self._etapas = []  # una orden directa cancela las etapas que quedaran pendientes
        self._lanzar(valores, escalonado)
        if esperar:
            self.esperar()

    def _lanzar(self, valores, escalonado):
        """Pone en marcha los ejes de `valores` (ya validados)."""
        for indice, eje in enumerate(e for e in config.EJES if e in valores):
            if self._pos[eje] is None:
                # primer movimiento: la senal arranca en la pose segura ("abierto")
                self._pos[eje] = float(self._servos[eje].mover_a_us(self._calibracion[eje][0]))
            self._objetivo[eje] = self._pulso_de_valor(eje, valores[eje])
            self._espera_ms[eje] = indice * config.RETARDO_ESCALON_MS if escalonado else 0
        if self._ultimo_ms is None:
            self._ultimo_ms = self._reloj_ms()

    def mover_por_etapas(self, etapas, esperar=True, escalonado=True):
        """Mueve por tandas: `etapas` es una lista de {eje: valor}. La primera
        arranca ya; cada una de las siguientes arranca cuando la anterior
        TERMINO de llegar (mas config.PAUSA_ENTRE_ETAPAS_MS). Se valida todo
        antes de mover nada. Ej.: cerrar el punio = dedos primero, pulgar despues."""
        etapas = [dict(etapa) for etapa in etapas if etapa]
        for etapa in etapas:
            for eje, valor in etapa.items():
                self._revisar_eje(eje)
                self._revisar_valor(valor)
        if not etapas:
            return
        self._etapas = etapas[1:]
        self._espera_etapa_ms = config.PAUSA_ENTRE_ETAPAS_MS
        self._lanzar(etapas[0], escalonado)
        if esperar:
            self.esperar()

    def dedo(self, eje, valor, esperar=True):
        """Mueve un solo eje (0.0 abierto .. 1.0 cerrado)."""
        self.mover({eje: valor}, esperar=esperar)

    def abrir(self, esperar=True):
        self.mover({eje: 0.0 for eje in self.ejes()}, esperar=esperar, escalonado=True)

    def cerrar(self, esperar=True):
        self.mover({eje: 1.0 for eje in self.ejes()}, esperar=esperar, escalonado=True)

    def detener(self):
        """Congela todos los ejes donde estan (siguen sosteniendo la posicion)."""
        for eje in self._objetivo:
            self._objetivo[eje] = None
        self._etapas = []
        self._ultimo_ms = None

    def soltar(self, eje=None):
        """Corta la senal de un eje (o de todos): el servo deja de sostener.
        El siguiente movimiento vuelve a arrancar desde "abierto"."""
        ejes = self.ejes() if eje is None else (eje,)
        if eje is None:
            self._etapas = []
        for nombre in ejes:
            self._revisar_eje(nombre)
            self._servos[nombre].soltar()
            self._pos[nombre] = None
            self._objetivo[nombre] = None
            self._espera_ms[nombre] = 0
        if all(objetivo is None for objetivo in self._objetivo.values()):
            self._ultimo_ms = None

    # --- Movimiento ---

    def actualizar(self):
        """Avanza un paso todos los ejes que van hacia su objetivo, segun el
        tiempo transcurrido. Devuelve True mientras quede algo por mover.
        Llamar cada config.PERIODO_MS (esperar() lo hace)."""
        if self._ultimo_ms is None:
            if not self._etapas:
                return False
            self._ultimo_ms = self._reloj_ms()  # solo quedan etapas por lanzar
        ahora = self._reloj_ms()
        dt = min((ahora - self._ultimo_ms) & MASCARA_TICKS, config.MAX_PASO_MS)
        self._ultimo_ms = ahora

        pendiente = False
        for eje, objetivo in self._objetivo.items():
            if objetivo is None:
                continue
            if self._espera_ms[eje] > 0:
                self._espera_ms[eje] -= dt
                pendiente = True
                continue

            pos = self._pos[eje]
            cerrando = abs(objetivo - self._calibracion[eje][1]) < abs(pos - self._calibracion[eje][1])
            vel_cierre, vel_apertura = self._vel_eje.get(eje, self._vel_global)
            velocidad = vel_cierre if cerrando else vel_apertura
            paso = velocidad * dt / 1000
            if abs(objetivo - pos) <= paso:
                pos = objetivo
                self._objetivo[eje] = None
            else:
                pos += paso if objetivo > pos else -paso
                pendiente = True
            self._pos[eje] = pos
            self._servos[eje].mover_a_us(pos)

        if not pendiente and self._etapas:
            # la etapa en curso termino: tras la pausa se lanza la siguiente
            self._espera_etapa_ms -= dt
            if self._espera_etapa_ms <= 0:
                self._lanzar(self._etapas.pop(0), True)
                self._espera_etapa_ms = config.PAUSA_ENTRE_ETAPAS_MS
            pendiente = True
        elif not pendiente:
            self._ultimo_ms = None
        return pendiente

    def esperar(self):
        """Avanza el movimiento hasta que todos los ejes llegan."""
        while self.actualizar():
            self._dormir_ms(config.PERIODO_MS)

    # --- Parametros: velocidad y angulos (pulsos) de abrir/cerrar ---

    def fijar_velocidad(self, cierre_us_s, apertura_us_s, eje=None):
        """Velocidad de cierre y de apertura en us de pulso por segundo
        (~1000 us = ~90 grados). Con `eje`, solo ese dedo; sin `eje`, todos
        (y se descartan las velocidades propias de cada dedo)."""
        for nombre, valor in (("cierre", cierre_us_s), ("apertura", apertura_us_s)):
            if (not isinstance(valor, (int, float)) or isinstance(valor, bool)
                    or not config.VELOCIDAD_MIN_US_S <= valor <= config.VELOCIDAD_MAX_US_S):
                raise ValueError("velocidad de {} fuera de {}-{} us/s: {!r}".format(
                    nombre, config.VELOCIDAD_MIN_US_S, config.VELOCIDAD_MAX_US_S, valor))
        if eje is None:
            self._vel_global = (cierre_us_s, apertura_us_s)
            self._vel_eje = {}
        else:
            self._revisar_eje(eje)
            self._vel_eje[eje] = (cierre_us_s, apertura_us_s)

    def velocidades(self):
        """{eje: (cierre_us_s, apertura_us_s)} vigentes."""
        return {eje: self._vel_eje.get(eje, self._vel_global) for eje in self.ejes()}

    def fijar_calibracion(self, eje, abierto_us, cerrado_us):
        """Cambia los pulsos de "abierto" y "cerrado" de un dedo (se valida
        igual que al cargar). NO mueve el servo y detiene el movimiento en
        curso de ese dedo. No se guarda hasta guardar_calibracion()."""
        self._revisar_eje(eje)
        _calibracion.validar(eje, abierto_us, cerrado_us)
        self._calibracion[eje] = (abierto_us, cerrado_us)
        self._objetivo[eje] = None
        self._espera_ms[eje] = 0
        if all(objetivo is None for objetivo in self._objetivo.values()):
            self._ultimo_ms = None

    def calibracion(self):
        """{eje: (abierto_us, cerrado_us)} vigentes."""
        return {eje: self._calibracion[eje] for eje in self.ejes()}

    def guardar_calibracion(self, ruta=None):
        """Guarda la calibracion vigente en calibracion.json (conserva lo que
        ya hubiera guardado de los ejes que esta mano no tiene)."""
        completa = _calibracion.cargar(ruta)
        completa.update(self.calibracion())
        _calibracion.guardar(completa, ruta)

    # --- Consulta ---

    def moviendo(self):
        """True si algun eje todavia va hacia su objetivo."""
        return bool(self._etapas) or any(objetivo is not None for objetivo in self._objetivo.values())

    def estado(self):
        """{eje: valor 0.0..1.0 actual, o None si el eje aun no tiene senal}."""
        return {
            eje: None if self._pos[eje] is None else round(self._valor_de_pulso(eje, self._pos[eje]), 3) + 0.0
            for eje in self.ejes()
        }

    def pulsos(self):
        """{eje: pulso actual en us (redondeado), o None si no tiene senal}."""
        return {eje: None if self._pos[eje] is None else int(round(self._pos[eje])) for eje in self.ejes()}


def aislar_pines(numeros_pin, crear_pin_en_bajo):
    """Fuerza a 0 V los pines de senal de los servos que NO se estan usando.
    Un pin de servo sin conducir (flotante) capta la senal PWM de los cables
    vecinos y el servo se mueve solo (visto en la prueba real: al mover el
    medio se movia tambien el indice). `crear_pin_en_bajo(n)`: en la placa
    es Pin(n, Pin.OUT, value=0)."""
    for numero in numeros_pin:
        crear_pin_en_bajo(numero)


def crear_mano(ejes=None, calibracion=None):
    """Mano real sobre la placa. `ejes`: cuales servos hay conectados (por
    defecto los 6); util en las primeras pruebas con uno o tres servos.
    Los servos no reciben senal hasta su primer movimiento."""
    import time

    from machine import PWM, Pin

    ejes = tuple(ejes) if ejes is not None else config.EJES
    if calibracion is None:
        calibracion = _calibracion.cargar()
    servos = {}
    for eje in ejes:
        if eje not in config.PINES:
            raise ValueError("eje desconocido: {!r}".format(eje))
        pwm = PWM(Pin(config.PINES[eje]), freq=config.FRECUENCIA_HZ, duty_u16=0)  # duty_ns=0 al crear falla en MicroPython 1.29
        servos[eje] = Servo(pwm, config.PULSO_MIN_US, config.PULSO_MAX_US)
    aislar_pines(
        [config.PINES[eje] for eje in config.EJES if eje not in servos],
        lambda numero: Pin(numero, Pin.OUT, value=0),
    )
    return Mano(servos, calibracion, time.ticks_ms, time.sleep_ms)
