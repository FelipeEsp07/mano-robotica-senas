"""Pruebas de poses, comandos, servidor serial y enlaces, sin placa.

    python -m unittest discover -s pruebas -v
"""

import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "firmware"))
sys.path.insert(0, os.path.join(AQUI, "..", "herramientas"))

import config  # noqa: E402
from control import Control  # noqa: E402
from enlace import EnlaceSerial, EnlaceSimulado, parsear  # noqa: E402
from mano import Mano  # noqa: E402
from poses import POSES  # noqa: E402
from servidor_serial import Servidor  # noqa: E402
from servo import Servo  # noqa: E402
from unidades import grados_a_us, us_a_grados  # noqa: E402


class PwmFalso:
    def __init__(self):
        self.llamadas = []

    def duty_ns(self, valor):
        self.llamadas.append(valor)


class Reloj:
    def __init__(self):
        self.ms = 1000

    def __call__(self):
        return self.ms

    def dormir(self, ms):
        self.ms += ms


def crear(ejes=None):
    reloj = Reloj()
    ejes = tuple(ejes or config.EJES)
    pwms = {e: PwmFalso() for e in ejes}
    servos = {e: Servo(pwms[e], config.PULSO_MIN_US, config.PULSO_MAX_US) for e in ejes}
    mano = Mano(servos, dict(config.CALIBRACION_DEFECTO), reloj, reloj.dormir)
    return mano, Control(mano), pwms, reloj


def datos(respuesta):
    ok, cuerpo = parsear(respuesta)
    assert ok, respuesta
    return cuerpo


class PruebasPoses(unittest.TestCase):
    def test_son_las_tres_pedidas(self):
        self.assertEqual(set(POSES), {"punio", "ok", "rock"})

    def test_todas_definen_los_seis_ejes_en_rango(self):
        for nombre, pose in POSES.items():
            self.assertEqual(set(pose), set(config.EJES), nombre)
            for eje, valor in pose.items():
                self.assertTrue(0.0 <= valor <= 1.0, (nombre, eje))

    def test_punio_cierra_todo_por_completo(self):
        self.assertEqual(set(POSES["punio"].values()), {1.0})


class PruebasControl(unittest.TestCase):
    def test_ping(self):
        _, control, _, _ = crear()
        self.assertEqual(control.ejecutar("PING"), "OK")

    def test_pose_lleva_cada_eje_a_su_valor(self):
        mano, control, _, _ = crear()
        for nombre, pose in POSES.items():
            self.assertEqual(control.ejecutar("POSE " + nombre, esperar=True), "OK")
            self.assertEqual(mano.estado(), pose, nombre)

    def test_pose_ignora_los_ejes_sin_servo(self):
        mano, control, _, _ = crear(["indice", "medio", "anular"])
        self.assertEqual(control.ejecutar("POSE rock", esperar=True), "OK")
        self.assertEqual(mano.estado(), {"indice": 0.0, "medio": 1.0, "anular": 1.0})

    def test_los_comandos_no_distinguen_mayusculas(self):
        mano, control, _, _ = crear()
        self.assertEqual(control.ejecutar("pose PUNIO", esperar=True), "OK")
        self.assertEqual(mano.estado()["indice"], 1.0)

    def test_dedo_mueve_solo_ese_eje(self):
        mano, control, _, _ = crear()
        control.ejecutar("DEDO medio 0.5", esperar=True)
        estado = mano.estado()
        self.assertEqual(estado["medio"], 0.5)
        self.assertIsNone(estado["indice"])

    def test_mover_varios_ejes(self):
        mano, control, _, _ = crear()
        control.ejecutar("MOVER indice=1 medio=0.25", esperar=True)
        self.assertEqual((mano.estado()["indice"], mano.estado()["medio"]), (1.0, 0.25))

    def test_abrir_y_cerrar(self):
        mano, control, _, _ = crear()
        control.ejecutar("CERRAR", esperar=True)
        self.assertEqual(set(mano.estado().values()), {1.0})
        control.ejecutar("ABRIR", esperar=True)
        self.assertEqual(set(mano.estado().values()), {0.0})

    def test_sin_esperar_el_movimiento_avanza_con_actualizar(self):
        mano, control, _, reloj = crear(["indice"])
        control.ejecutar("DEDO indice 1")
        self.assertTrue(mano.moviendo())
        while mano.actualizar():
            reloj.dormir(config.PERIODO_MS)
        self.assertEqual(mano.estado()["indice"], 1.0)

    def test_velocidad_global_y_por_dedo(self):
        mano, control, _, _ = crear()
        control.ejecutar("VEL 500 300")
        self.assertEqual(set(mano.velocidades().values()), {(500, 300)})
        control.ejecutar("VEL 900 200 indice")
        velocidades = mano.velocidades()
        self.assertEqual(velocidades["indice"], (900, 200))
        self.assertEqual(velocidades["medio"], (500, 300))
        control.ejecutar("VEL 600 350")  # el global descarta lo propio de cada dedo
        self.assertEqual(set(mano.velocidades().values()), {(600, 350)})

    def test_un_dedo_mas_lento_tarda_mas(self):
        def duracion(vel):
            mano, control, _, reloj = crear(["indice"])
            control.ejecutar("VEL {} {}".format(vel, vel))
            control.ejecutar("DEDO indice 1")
            t0 = reloj()
            while mano.actualizar():
                reloj.dormir(config.PERIODO_MS)
            return reloj() - t0
        self.assertGreater(duracion(300), duracion(900) * 2)

    def test_velocidad_fuera_de_rango_se_rechaza(self):
        _, control, _, _ = crear()
        for linea in ("VEL 5 400", "VEL 700 99999", "VEL 700 400 rodilla", "VEL 700", "VEL a b"):
            self.assertTrue(control.ejecutar(linea).startswith("ERR"), linea)

    def test_angulos_cambian_la_calibracion_sin_mover_el_servo(self):
        mano, control, pwms, _ = crear()
        self.assertEqual(control.ejecutar("ANGULOS indice 900 2400"), "OK")
        self.assertEqual(mano.calibracion()["indice"], (900, 2400))
        self.assertEqual(pwms["indice"].llamadas, [])
        control.ejecutar("DEDO indice 1", esperar=True)
        self.assertEqual(pwms["indice"].llamadas[-1], 2400 * 1000)

    def test_angulos_invalidos_se_rechazan_y_no_cambian_nada(self):
        mano, control, _, _ = crear()
        antes = mano.calibracion()
        for linea in ("ANGULOS indice 100 2400", "ANGULOS indice 900 5000", "ANGULOS indice 1500 1520",
                      "ANGULOS rodilla 900 2000", "ANGULOS indice 900"):
            self.assertTrue(control.ejecutar(linea).startswith("ERR"), linea)
        self.assertEqual(mano.calibracion(), antes)

    def test_guardar_escribe_la_calibracion_y_conserva_lo_demas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "cal.json")
            antes = config.RUTA_CALIBRACION
            config.RUTA_CALIBRACION = ruta
            try:
                mano, control, _, _ = crear(["indice", "medio"])
                control.ejecutar("ANGULOS indice 900 2400")
                self.assertEqual(control.ejecutar("GUARDAR"), "OK")
                with open(ruta) as archivo:
                    guardado = json.load(archivo)
                self.assertEqual(guardado["indice"], [900, 2400])
                self.assertEqual(guardado["anular"], list(config.CALIBRACION_DEFECTO["anular"]))
            finally:
                config.RUTA_CALIBRACION = antes

    def test_estado_es_json_completo(self):
        _, control, _, _ = crear()
        e = datos(control.ejecutar("ESTADO"))
        self.assertEqual(e["ejes"], list(config.EJES))
        self.assertEqual(e["poses"], ["ok", "punio", "rock"])
        self.assertEqual(e["limites_us"], [config.PULSO_MIN_US, config.PULSO_MAX_US])
        self.assertEqual(set(e["calibracion"]), set(config.EJES))
        self.assertFalse(e["moviendo"])

    def test_estado_no_muestra_menos_cero(self):
        _, control, _, _ = crear()
        control.ejecutar("DEDO anular 0", esperar=True)
        self.assertNotIn("-0.0", control.ejecutar("ESTADO"))

    def test_detener_y_soltar(self):
        mano, control, pwms, _ = crear(["indice"])
        control.ejecutar("DEDO indice 1")
        self.assertEqual(control.ejecutar("DETENER"), "OK")
        self.assertFalse(mano.moviendo())
        self.assertEqual(control.ejecutar("SOLTAR indice"), "OK")
        self.assertEqual(pwms["indice"].llamadas[-1], 0)

    def test_errores_de_uso_nunca_lanzan(self):
        _, control, _, _ = crear()
        for linea in ("", "   ", "VOLAR", "POSE", "POSE baile", "DEDO indice", "DEDO indice 2", "DEDO indice abc",
                      "DEDO rodilla 1", "MOVER", "MOVER indice", "MOVER indice=2", "SOLTAR rodilla"):
            self.assertTrue(control.ejecutar(linea).startswith("ERR"), repr(linea))

    def test_no_se_puede_invocar_un_metodo_interno(self):
        _, control, _, _ = crear()
        self.assertTrue(control.ejecutar("__class__").startswith("ERR"))


class PruebasEtapas(unittest.TestCase):
    """Cerrar = dedos primero y pulgar despues; abrir = pulgar primero."""

    DEDOS = ("indice", "medio", "anular", "menique")
    PULGAR = ("pulgar_flexion", "pulgar_oposicion")

    def correr(self, linea):
        """Ejecuta `linea` sin esperar y avanza el reloj; devuelve, por eje, el
        instante (ms) en que recibio senal por primera vez y en que llego."""
        mano, control, pwms, reloj = crear()
        t0 = reloj()
        control.ejecutar(linea)
        primera, llegada = {}, {}
        while True:
            seguir = mano.actualizar()
            for eje, pwm in pwms.items():
                if eje not in primera and pwm.llamadas:
                    primera[eje] = reloj() - t0
                if eje not in llegada and mano._pos[eje] is not None and mano._objetivo[eje] is None:
                    llegada[eje] = reloj() - t0
            if not seguir:
                break
            reloj.dormir(config.PERIODO_MS)
        return mano, primera, llegada

    def test_cerrar_mueve_los_dedos_y_despues_el_pulgar(self):
        mano, primera, llegada = self.correr("CERRAR")
        ultimo_dedo = max(llegada[d] for d in self.DEDOS)
        for eje in self.PULGAR:
            self.assertGreater(primera[eje], ultimo_dedo, eje)  # el pulgar no arranca antes de que lleguen los 4
        self.assertEqual(set(mano.estado().values()), {1.0})

    def test_hay_una_pausa_entre_los_dedos_y_el_pulgar(self):
        _, primera, llegada = self.correr("CERRAR")
        espera = min(primera[e] for e in self.PULGAR) - max(llegada[d] for d in self.DEDOS)
        self.assertGreaterEqual(espera, config.PAUSA_ENTRE_ETAPAS_MS - config.PERIODO_MS)

    def test_abrir_mueve_primero_el_pulgar(self):
        mano, control, pwms, reloj = crear()
        control.ejecutar("CERRAR", esperar=True)
        antes = {d: len(pwms[d].llamadas) for d in self.DEDOS}
        control.ejecutar("ABRIR")
        # mientras el pulgar se abre, los dedos no reciben ordenes nuevas
        while mano.estado()["pulgar_flexion"] != 0.0 or mano.estado()["pulgar_oposicion"] != 0.0:
            mano.actualizar()
            reloj.dormir(config.PERIODO_MS)
            for d in self.DEDOS:
                self.assertEqual(len(pwms[d].llamadas), antes[d], d)
        mano.esperar()
        self.assertEqual(set(mano.estado().values()), {0.0})

    def test_las_poses_tambien_dejan_el_pulgar_para_el_final(self):
        from poses import POSES
        for nombre in POSES:
            mano, primera, llegada = self.correr("POSE " + nombre)
            ultimo_dedo = max(llegada[d] for d in self.DEDOS)
            for eje in self.PULGAR:
                self.assertGreaterEqual(primera[eje], ultimo_dedo, (nombre, eje))
            self.assertEqual(mano.estado(), POSES[nombre], nombre)

    def test_sin_pulgar_conectado_cierra_solo_los_dedos(self):
        mano, control, _, _ = crear(["indice", "medio", "anular", "menique"])
        control.ejecutar("CERRAR", esperar=True)
        self.assertEqual(set(mano.estado().values()), {1.0})

    def test_con_esperar_se_completan_las_dos_etapas(self):
        mano, control, _, _ = crear()
        control.ejecutar("CERRAR", esperar=True)
        self.assertFalse(mano.moviendo())
        self.assertEqual(set(mano.estado().values()), {1.0})

    def test_detener_cancela_las_etapas_pendientes(self):
        mano, control, pwms, reloj = crear()
        control.ejecutar("CERRAR")
        mano.actualizar()
        control.ejecutar("DETENER")
        self.assertFalse(mano.moviendo())
        for _ in range(100):
            reloj.dormir(config.PERIODO_MS)
            mano.actualizar()
        for eje in self.PULGAR:
            self.assertEqual(pwms[eje].llamadas, [], eje)  # el pulgar nunca llego a recibir senal

    def test_una_orden_directa_cancela_las_etapas_pendientes(self):
        mano, control, pwms, reloj = crear()
        control.ejecutar("CERRAR")
        control.ejecutar("DEDO indice 0")
        while mano.actualizar():
            reloj.dormir(config.PERIODO_MS)
        self.assertEqual(mano.estado()["indice"], 0.0)
        for eje in self.PULGAR:
            self.assertEqual(pwms[eje].llamadas, [], eje)

    def test_valores_invalidos_no_mueven_nada(self):
        mano, _, pwms, _ = crear()
        with self.assertRaises(ValueError):
            mano.mover_por_etapas([{"indice": 1.0}, {"pulgar_flexion": 3.0}])
        self.assertTrue(all(p.llamadas == [] for p in pwms.values()))


class PruebasServidor(unittest.TestCase):
    def test_responde_una_linea_con_arroba_por_comando(self):
        _, control, _, _ = crear()
        salida = []
        servidor = Servidor(control, salida.append)
        servidor.alimentar("PING\nPOSE ba")
        servidor.alimentar("ile\r\n\r\nDEDO medio 0.5\n")
        self.assertEqual(salida[0], "@OK\n")
        self.assertTrue(salida[1].startswith("@ERR pose desconocida"))
        self.assertEqual(salida[2], "@OK\n")
        self.assertEqual(len(salida), 3)

    def test_un_fallo_interno_no_tumba_el_servidor(self):
        class Roto:
            def ejecutar(self, linea):
                raise RuntimeError("boom")

        salida = []
        servidor = Servidor(Roto(), salida.append)
        servidor.alimentar("PING\n")
        self.assertEqual(salida, ["@ERR interno: boom\n"])


class SerieFalsa:
    """Imita el puerto de la placa: lo que se escribe entra a un Servidor real,
    y su salida (con ruido de REPL por delante) queda para leer."""

    def __init__(self, puerto, baudios, timeout=None, con_ruido=True):
        _, control, _, _ = crear(["indice", "medio", "anular"])
        self._salida_bytes = b""
        self._servidor = Servidor(control, self._escribir)
        self._listo = False
        self._con_ruido = con_ruido
        self.cerrado = False
        self.escrito = b""

    def _escribir(self, texto):
        self._salida_bytes += texto.encode()

    def write(self, datos):
        self.escrito += datos
        if b"servidor_serial.iniciar()" in datos:
            self._salida_bytes += (b">>> import servidor_serial; servidor_serial.iniciar()\r\n" if self._con_ruido else b"")
            self._salida_bytes += b"@LISTO ejes=indice,medio,anular\n"
            self._listo = True
        elif self._listo and datos.strip() and not datos.startswith(b"\x03"):
            self._servidor.alimentar(datos.decode())

    @property
    def in_waiting(self):
        return len(self._salida_bytes)

    def read(self, n):
        trozo, self._salida_bytes = self._salida_bytes[:n], self._salida_bytes[n:]
        return trozo

    def reset_input_buffer(self):
        self._salida_bytes = b""

    def close(self):
        self.cerrado = True


class PruebasEnlaces(unittest.TestCase):
    def test_parsear(self):
        self.assertEqual(parsear("OK"), (True, None))
        self.assertEqual(parsear('OK {"a": 1}'), (True, {"a": 1}))
        self.assertEqual(parsear("ERR mal"), (False, "mal"))
        self.assertFalse(parsear("???")[0])

    def test_serial_arranca_el_servidor_y_manda_comandos(self):
        enlace = EnlaceSerial("COM-FALSO", abrir_serie=SerieFalsa)
        enlace.iniciar_servidor(timeout_s=2)
        self.assertEqual(enlace.enviar("PING"), "OK")
        self.assertEqual(enlace.enviar("DEDO medio 1"), "OK")
        ok, estado = parsear(enlace.enviar("ESTADO"))
        self.assertTrue(ok)
        self.assertEqual(estado["ejes"], ["indice", "medio", "anular"])
        ok, mensaje = parsear(enlace.enviar("POSE baile"))
        self.assertFalse(ok)
        self.assertIn("pose desconocida", mensaje)

    def test_serial_sin_respuesta_lanza_timeout(self):
        enlace = EnlaceSerial("COM-FALSO", abrir_serie=SerieFalsa)  # sin iniciar_servidor: la placa no contesta
        with self.assertRaises(TimeoutError):
            enlace.enviar("PING", timeout_s=0.3)

    def test_serial_falla_claro_si_la_placa_no_arranca_el_servidor(self):
        class Muda(SerieFalsa):
            def write(self, datos):
                self.escrito += datos

        enlace = EnlaceSerial("COM-FALSO", abrir_serie=Muda)
        with self.assertRaises(RuntimeError):
            enlace.iniciar_servidor(timeout_s=0.3)

    def test_serial_cerrar_manda_ctrl_c_y_cierra(self):
        enlace = EnlaceSerial("COM-FALSO", abrir_serie=SerieFalsa)
        enlace.cerrar()
        self.assertTrue(enlace._serie.cerrado)
        self.assertTrue(enlace._serie.escrito.endswith(b"\x03"))

    def test_simulado_ejecuta_y_calcula_la_duracion(self):
        enlace = EnlaceSimulado()
        self.assertEqual(enlace.enviar("POSE punio"), "OK")
        self.assertGreater(enlace.ultima_duracion_s, 0.5)
        enlace.enviar("VEL 3000 3000")
        enlace.enviar("POSE punio")
        # ya estaba ahi: solo cuentan la pausa entre etapas y el arranque escalonado
        self.assertLess(enlace.ultima_duracion_s, 1.0)
        ok, estado = parsear(enlace.enviar("ESTADO"))
        self.assertEqual(estado["valores"], POSES["punio"])

    def test_simulado_guardar_no_escribe_en_la_carpeta_actual(self):
        enlace = EnlaceSimulado()
        enlace.enviar("ANGULOS indice 900 2400")
        antes = os.path.exists("calibracion.json")
        self.assertEqual(enlace.enviar("GUARDAR"), "OK")
        self.assertEqual(os.path.exists("calibracion.json"), antes)


class SerieMudaHastaReinicio(SerieFalsa):
    """Placa que no contesta nada hasta que le dan un pulso de RTS (como la
    ESP32 cuando arranca en silencio)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dtr = False
        self.reinicios = 0
        self._despierta = False
        self._rts = False

    @property
    def rts(self):
        return self._rts

    @rts.setter
    def rts(self, valor):
        if valor:
            self.reinicios += 1
            self._despierta = True
        self._rts = valor

    def write(self, datos):
        if self._despierta:
            super().write(datos)
        else:
            self.escrito += datos


class PruebasReinicioAutomatico(unittest.TestCase):
    def test_reinicia_la_placa_si_no_arranca_y_reintenta(self):
        from unittest import mock
        enlace = EnlaceSerial("COM-FALSO", abrir_serie=SerieMudaHastaReinicio)
        with mock.patch("enlace.time.sleep"):
            enlace.iniciar_servidor(timeout_s=0.3)
        self.assertEqual(enlace._serie.reinicios, 1)
        self.assertEqual(enlace.enviar("PING"), "OK")

    def test_no_reinicia_si_el_servidor_arranca_a_la_primera(self):
        enlace = EnlaceSerial("COM-FALSO", abrir_serie=SerieFalsa)
        enlace.iniciar_servidor(timeout_s=2)  # SerieFalsa no tiene rts: ni se intenta reiniciar
        self.assertEqual(enlace.enviar("PING"), "OK")


class PruebasUnidades(unittest.TestCase):
    def test_centro_y_extremos(self):
        self.assertAlmostEqual(us_a_grados(1500), 90)
        self.assertAlmostEqual(us_a_grados(500), 0)
        self.assertAlmostEqual(us_a_grados(2500), 180)
        self.assertAlmostEqual(grados_a_us(us_a_grados(1234)), 1234)


if __name__ == "__main__":
    unittest.main()
