"""Pruebas del firmware en la PC, sin placa: PWM y reloj simulados.

    python -m unittest discover -s pruebas -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))

import calibracion  # noqa: E402
import config  # noqa: E402
from mano import Mano, aislar_pines  # noqa: E402
from servo import Servo  # noqa: E402


class PwmFalso:
    def __init__(self):
        self.llamadas = []  # duty_ns en orden

    def duty_ns(self, valor):
        self.llamadas.append(valor)


class RelojFalso:
    def __init__(self):
        self.ms = 1000

    def __call__(self):
        return self.ms

    def dormir(self, ms):
        self.ms += ms


def crear_mano(calib=None, ejes=None):
    reloj = RelojFalso()
    ejes = ejes or config.EJES
    pwms = {eje: PwmFalso() for eje in ejes}
    servos = {eje: Servo(pwms[eje], config.PULSO_MIN_US, config.PULSO_MAX_US) for eje in ejes}
    mano = Mano(servos, calib or config.CALIBRACION_DEFECTO, reloj, reloj.dormir)
    return mano, pwms, reloj


class PruebasServo(unittest.TestCase):
    def test_envia_el_pulso_en_nanosegundos(self):
        pwm = PwmFalso()
        servo = Servo(pwm, 600, 2300)
        self.assertEqual(servo.mover_a_us(1500), 1500)
        self.assertEqual(pwm.llamadas, [1500000])

    def test_recorta_a_los_limites_duros(self):
        pwm = PwmFalso()
        servo = Servo(pwm, 600, 2300)
        self.assertEqual(servo.mover_a_us(100), 600)
        self.assertEqual(servo.mover_a_us(9000), 2300)
        self.assertEqual(pwm.llamadas, [600000, 2300000])

    def test_soltar_corta_la_senal(self):
        pwm = PwmFalso()
        servo = Servo(pwm, 600, 2300)
        servo.mover_a_us(1500)
        servo.soltar()
        self.assertEqual(pwm.llamadas[-1], 0)
        self.assertIsNone(servo.pulso_us)


class PruebasCalibracion(unittest.TestCase):
    def test_acepta_un_par_valido_en_cualquier_sentido(self):
        calibracion.validar("indice", 1500, 1900)
        calibracion.validar("indice", 1900, 1500)

    def test_rechaza_pulsos_fuera_de_los_limites(self):
        with self.assertRaises(ValueError):
            calibracion.validar("indice", 1500, config.PULSO_MAX_US + 1)
        with self.assertRaises(ValueError):
            calibracion.validar("indice", config.PULSO_MIN_US - 1, 1500)

    def test_rechaza_recorrido_demasiado_corto(self):
        with self.assertRaises(ValueError):
            calibracion.validar("indice", 1500, 1550)

    def test_rechaza_eje_desconocido_y_tipos_raros(self):
        with self.assertRaises(ValueError):
            calibracion.validar("rodilla", 1500, 1900)
        with self.assertRaises(ValueError):
            calibracion.validar("indice", "1500", 1900)
        with self.assertRaises(ValueError):
            calibracion.validar("indice", True, 1900)

    def test_sin_archivo_usa_los_valores_por_defecto(self):
        with tempfile.TemporaryDirectory() as carpeta:
            self.assertEqual(calibracion.cargar(os.path.join(carpeta, "no_existe.json")),
                             config.CALIBRACION_DEFECTO)

    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "cal.json")
            calibracion.guardar({"indice": (1200, 1800)}, ruta)
            cargada = calibracion.cargar(ruta)
            self.assertEqual(tuple(cargada["indice"]), (1200, 1800))
            self.assertEqual(cargada["medio"], config.CALIBRACION_DEFECTO["medio"])

    def test_archivo_corrupto_lanza_error(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "cal.json")
            with open(ruta, "w") as archivo:
                archivo.write('{"indice": [100, 5000]}')
            with self.assertRaises(ValueError):
                calibracion.cargar(ruta)

    def test_guardar_no_escribe_datos_invalidos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "cal.json")
            with self.assertRaises(ValueError):
                calibracion.guardar({"indice": (100, 5000)}, ruta)
            self.assertFalse(os.path.exists(ruta))


class PruebasAislarPines(unittest.TestCase):
    def test_pone_en_bajo_solo_los_pines_pedidos(self):
        creados = []
        aislar_pines([9, 10, 11], creados.append)
        self.assertEqual(creados, [9, 10, 11])

    def test_sin_pines_no_hace_nada(self):
        creados = []
        aislar_pines([], creados.append)
        self.assertEqual(creados, [])


class PruebasMano(unittest.TestCase):
    def test_no_hay_senal_hasta_el_primer_movimiento(self):
        mano, pwms, _ = crear_mano()
        self.assertTrue(all(p.llamadas == [] for p in pwms.values()))
        self.assertEqual(set(mano.estado().values()), {None})

    def test_el_primer_movimiento_arranca_en_la_pose_abierta(self):
        mano, pwms, _ = crear_mano()
        mano.dedo("indice", 1.0)
        abierto_us = config.CALIBRACION_DEFECTO["indice"][0]
        self.assertEqual(pwms["indice"].llamadas[0], abierto_us * 1000)
        self.assertEqual(pwms["medio"].llamadas, [])  # los demas ejes siguen sin senal

    def test_llega_al_pulso_cerrado_y_abierto(self):
        mano, pwms, _ = crear_mano()
        abierto_us, cerrado_us = config.CALIBRACION_DEFECTO["indice"]
        mano.dedo("indice", 1.0)
        self.assertEqual(pwms["indice"].llamadas[-1], cerrado_us * 1000)
        self.assertEqual(mano.estado()["indice"], 1.0)
        mano.dedo("indice", 0.0)
        self.assertEqual(pwms["indice"].llamadas[-1], abierto_us * 1000)
        self.assertEqual(mano.estado()["indice"], 0.0)

    def test_valor_intermedio(self):
        mano, pwms, _ = crear_mano({**config.CALIBRACION_DEFECTO, "indice": (1000, 2000)})
        mano.dedo("indice", 0.25)
        self.assertEqual(pwms["indice"].llamadas[-1], 1250000)
        self.assertEqual(mano.estado()["indice"], 0.25)

    def test_sentido_invertido_con_abierto_mayor_que_cerrado(self):
        mano, pwms, _ = crear_mano({**config.CALIBRACION_DEFECTO, "indice": (1900, 1500)})
        mano.dedo("indice", 1.0)
        self.assertEqual(pwms["indice"].llamadas[0], 1900000)   # arranca abierto
        self.assertEqual(pwms["indice"].llamadas[-1], 1500000)  # cierra hacia el pulso menor
        self.assertEqual(mano.estado()["indice"], 1.0)

    def test_la_rampa_respeta_la_velocidad_maxima(self):
        mano, pwms, _ = crear_mano({**config.CALIBRACION_DEFECTO, "indice": (1000, 2000)})
        mano.dedo("indice", 1.0)
        pulsos = [n / 1000 for n in pwms["indice"].llamadas]
        # cada paso se da cada PERIODO_MS: nunca mas de velocidad * periodo
        maximo = config.VELOCIDAD_CIERRE_US_S * config.PERIODO_MS / 1000
        for anterior, actual in zip(pulsos, pulsos[1:]):
            self.assertLessEqual(abs(actual - anterior), maximo + 1)  # +1 por el redondeo a us entero
        self.assertGreater(len(pulsos), 10)

    def test_abrir_es_mas_lento_que_cerrar(self):
        mano, _, reloj = crear_mano({**config.CALIBRACION_DEFECTO, "indice": (1000, 2000)})
        t0 = reloj()
        mano.dedo("indice", 1.0)
        t_cierre = reloj() - t0
        t0 = reloj()
        mano.dedo("indice", 0.0)
        t_apertura = reloj() - t0
        self.assertGreater(t_apertura, t_cierre)

    def test_cerrar_arranca_los_servos_escalonados(self):
        mano, pwms, reloj = crear_mano()
        mano.cerrar(esperar=False)
        # avanzar de a un periodo y registrar cuando se mueve cada eje por primera vez
        primer_movimiento = {}
        base = {eje: len(p.llamadas) for eje, p in pwms.items()}
        t0 = reloj()
        while mano.actualizar():
            reloj.dormir(config.PERIODO_MS)
            for eje, p in pwms.items():
                if eje not in primer_movimiento and len(p.llamadas) > base[eje]:
                    primer_movimiento[eje] = reloj() - t0
        orden = [primer_movimiento[eje] for eje in config.EJES]
        self.assertEqual(orden, sorted(orden))
        self.assertGreater(orden[-1] - orden[0], 3 * config.RETARDO_ESCALON_MS)

    def test_abrir_y_cerrar_llevan_todos_los_ejes(self):
        mano, _, _ = crear_mano()
        mano.cerrar()
        self.assertEqual(set(mano.estado().values()), {1.0})
        mano.abrir()
        self.assertEqual(set(mano.estado().values()), {0.0})

    def test_los_dedos_son_independientes(self):
        mano, _, _ = crear_mano()
        mano.dedo("medio", 1.0)
        estado = mano.estado()
        self.assertEqual(estado["medio"], 1.0)
        self.assertIsNone(estado["indice"])

    def test_mover_varios_ejes_a_la_vez(self):
        mano, _, _ = crear_mano()
        mano.mover({"pulgar_flexion": 1.0, "pulgar_oposicion": 0.5})
        estado = mano.estado()
        self.assertEqual(estado["pulgar_flexion"], 1.0)
        self.assertEqual(estado["pulgar_oposicion"], 0.5)

    def test_valores_invalidos_no_mueven_nada(self):
        mano, pwms, _ = crear_mano()
        for malo in (-0.1, 1.1, "1", None, True):
            with self.assertRaises(ValueError):
                mano.dedo("indice", malo)
        with self.assertRaises(ValueError):
            mano.dedo("rodilla", 0.5)
        # un valor malo entre varios buenos: ninguno se mueve
        with self.assertRaises(ValueError):
            mano.mover({"indice": 1.0, "medio": 2.0})
        self.assertTrue(all(p.llamadas == [] for p in pwms.values()))

    def test_nunca_sale_de_los_limites_duros(self):
        mano, pwms, _ = crear_mano({**config.CALIBRACION_DEFECTO, "indice": (config.PULSO_MIN_US, config.PULSO_MAX_US)})
        mano.dedo("indice", 1.0)
        mano.dedo("indice", 0.0)
        for ns in pwms["indice"].llamadas:
            self.assertTrue(config.PULSO_MIN_US * 1000 <= ns <= config.PULSO_MAX_US * 1000)

    def test_detener_congela_donde_esta(self):
        mano, pwms, reloj = crear_mano({**config.CALIBRACION_DEFECTO, "indice": (1000, 2000)})
        mano.dedo("indice", 1.0, esperar=False)
        for _ in range(5):
            reloj.dormir(config.PERIODO_MS)
            mano.actualizar()
        mano.detener()
        ultimo = pwms["indice"].llamadas[-1]
        self.assertFalse(mano.actualizar())
        self.assertEqual(pwms["indice"].llamadas[-1], ultimo)
        self.assertTrue(1000000 < ultimo < 2000000)

    def test_soltar_corta_la_senal_y_el_siguiente_movimiento_arranca_abierto(self):
        mano, pwms, _ = crear_mano()
        mano.dedo("indice", 1.0)
        mano.soltar("indice")
        self.assertEqual(pwms["indice"].llamadas[-1], 0)
        self.assertIsNone(mano.estado()["indice"])
        mano.dedo("indice", 1.0)
        self.assertEqual(pwms["indice"].llamadas[len(pwms["indice"].llamadas) - 1], config.CALIBRACION_DEFECTO["indice"][1] * 1000)
        self.assertIn(config.CALIBRACION_DEFECTO["indice"][0] * 1000, pwms["indice"].llamadas[pwms["indice"].llamadas.index(0):])

    def test_pausa_larga_no_produce_un_salto(self):
        mano, pwms, reloj = crear_mano({**config.CALIBRACION_DEFECTO, "indice": (1000, 2000)})
        mano.dedo("indice", 1.0, esperar=False)
        reloj.ms += 5000  # el programa se quedo congelado 5 s
        mano.actualizar()
        avance = pwms["indice"].llamadas[-1] / 1000 - 1000
        self.assertLessEqual(avance, config.VELOCIDAD_CIERRE_US_S * config.MAX_PASO_MS / 1000 + 1)

    def test_funciona_con_un_subconjunto_de_ejes(self):
        mano, pwms, _ = crear_mano(ejes=["indice"])
        mano.cerrar()
        self.assertEqual(mano.ejes(), ("indice",))
        self.assertEqual(mano.estado(), {"indice": 1.0})
        with self.assertRaises(ValueError):
            mano.dedo("medio", 1.0)

    def test_reloj_que_da_la_vuelta(self):
        mano, pwms, reloj = crear_mano({**config.CALIBRACION_DEFECTO, "indice": (1000, 2000)})
        reloj.ms = 0x3FFFFFFF - 30  # a punto de dar la vuelta
        mano.dedo("indice", 1.0)
        self.assertEqual(mano.estado()["indice"], 1.0)


if __name__ == "__main__":
    unittest.main()
