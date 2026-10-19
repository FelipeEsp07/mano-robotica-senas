"""Prueba la app de Streamlit de punta a punta en modo simulado (sin navegador
ni placa), con streamlit.testing.v1.AppTest."""

import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "herramientas"))
sys.path.insert(0, os.path.join(AQUI, "..", "firmware"))

from streamlit.testing.v1 import AppTest  # noqa: E402

RUTA_APP = os.path.join(AQUI, "..", "herramientas", "app_mano.py")


def boton(app, etiqueta):
    for b in app.button:
        if b.label == etiqueta:
            return b
    raise AssertionError("no hay boton {!r}; hay: {}".format(etiqueta, [b.label for b in app.button]))


def app_conectada():
    app = AppTest.from_file(RUTA_APP, default_timeout=30).run()
    assert not app.exception, app.exception
    boton(app, "Conectar").click().run()
    assert not app.exception, app.exception
    return app


def estado(app):
    import json

    from enlace import parsear
    return parsear(app.session_state["enlace"].enviar("ESTADO"))[1]


class PruebasApp(unittest.TestCase):
    def test_sin_conectar_muestra_la_ayuda(self):
        app = AppTest.from_file(RUTA_APP, default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual([b.label for b in app.button], ["Conectar"])
        self.assertTrue(any("Conectar" in i.value for i in app.info))

    def test_conecta_en_modo_simulado_y_muestra_las_pestanas(self):
        app = app_conectada()
        self.assertEqual([t.label for t in app.tabs], ["Poses", "Un dedo", "Velocidad", "Ángulos", "Registro"])
        etiquetas = [b.label for b in app.button]
        for esperado in ("✊ Puño", "👌 OK", "🤘 Rock", "🖐️ Abrir mano", "Cerrar mano", "Desconectar"):
            self.assertIn(esperado, etiquetas)

    def test_las_tres_poses(self):
        from poses import POSES
        app = app_conectada()
        for etiqueta, pose in (("✊ Puño", "punio"), ("👌 OK", "ok"), ("🤘 Rock", "rock")):
            boton(app, etiqueta).click().run()
            self.assertFalse(app.exception, app.exception)
            self.assertEqual(estado(app)["valores"], POSES[pose], pose)

    def test_abrir_y_cerrar_mano(self):
        app = app_conectada()
        boton(app, "Cerrar mano").click().run()
        self.assertEqual(set(estado(app)["valores"].values()), {1.0})
        boton(app, "🖐️ Abrir mano").click().run()
        self.assertEqual(set(estado(app)["valores"].values()), {0.0})

    def test_mover_un_solo_dedo(self):
        app = app_conectada()
        app.selectbox(key="dedo_sel").select("medio").run()
        app.slider(key="pos_medio").set_value(40).run()
        boton(app, "Mover a esa posición").click().run()
        valores = estado(app)["valores"]
        self.assertEqual(valores["medio"], 0.4)
        self.assertIsNone(valores["indice"])

    def test_velocidad_de_un_solo_dedo_y_de_todos(self):
        app = app_conectada()
        app.selectbox(key="dedo_sel").select("indice").run()
        app.slider(key="vc_indice").set_value(900).run()
        app.slider(key="va_indice").set_value(250).run()
        boton(app, "Aplicar velocidad a Índice").click().run()
        velocidades = estado(app)["velocidades"]
        self.assertEqual(velocidades["indice"], [900, 250])
        self.assertEqual(velocidades["medio"], [700, 400])

        app.slider(key="vc_todos").set_value(500).run()
        app.slider(key="va_todos").set_value(300).run()
        boton(app, "Aplicar a todos los dedos").click().run()
        self.assertEqual({tuple(v) for v in estado(app)["velocidades"].values()}, {(500, 300)})

    def test_cambiar_angulos_en_microsegundos_y_en_grados(self):
        app = app_conectada()
        app.selectbox(key="ang_sel").select("indice").run()
        app.radio(key="unidad").set_value("Microsegundos (µs)").run()
        app.number_input(key="ab_indice_us").set_value(900.0).run()
        app.number_input(key="ce_indice_us").set_value(2400.0).run()
        boton(app, "Aplicar (sin guardar)").click().run()
        self.assertEqual(estado(app)["calibracion"]["indice"], [900, 2400])

        app.radio(key="unidad").set_value("Grados (aprox.)").run()
        app.number_input(key="ab_indice_g").set_value(45.0).run()   # 500 + 45 * 11.11 = 1000 us
        app.number_input(key="ce_indice_g").set_value(135.0).run()  # 2000 us
        boton(app, "Aplicar (sin guardar)").click().run()
        self.assertEqual(estado(app)["calibracion"]["indice"], [1000, 2000])

    def test_probar_abierto_y_cerrado_y_guardar(self):
        app = app_conectada()
        boton(app, "Probar cerrado").click().run()
        self.assertEqual(estado(app)["valores"]["indice"], 1.0)
        boton(app, "Probar abierto").click().run()
        self.assertEqual(estado(app)["valores"]["indice"], 0.0)
        boton(app, "💾 Guardar en la placa").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("GUARDAR → OK" in s.value for s in app.success))

    def test_un_valor_invalido_se_muestra_como_error_sin_romper_la_app(self):
        app = app_conectada()
        app.selectbox(key="ang_sel").select("indice").run()
        app.radio(key="unidad").set_value("Microsegundos (µs)").run()
        app.number_input(key="ab_indice_us").set_value(1500.0).run()
        app.number_input(key="ce_indice_us").set_value(1520.0).run()  # recorrido demasiado corto
        boton(app, "Aplicar (sin guardar)").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("ERR" in e.value for e in app.error))

    def test_registro_y_desconexion(self):
        app = app_conectada()
        boton(app, "✊ Puño").click().run()
        registro = app.session_state["registro"]
        self.assertEqual(registro[0][0], "POSE punio")
        boton(app, "Desconectar").click().run()
        self.assertEqual([b.label for b in app.button], ["Conectar"])


if __name__ == "__main__":
    unittest.main()
