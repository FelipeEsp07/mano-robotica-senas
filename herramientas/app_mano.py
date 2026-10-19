"""App de Streamlit para manejar la mano robotica.

    streamlit run herramientas/app_mano.py

Modos: "Simulado" (mano virtual, sin placa) o "Placa por USB" (arranca
servidor_serial en la placa; mientras la app esta conectada el REPL no esta
disponible: desconectar en la barra lateral lo libera).
"""

import streamlit as st

from enlace import EnlaceSerial, EnlaceSimulado, listar_puertos, parsear
from unidades import grados_a_us, us_a_grados

st.set_page_config(page_title="Mano robótica", page_icon="🖐️", layout="wide")

NOMBRES_EJE = {
    "indice": "Índice",
    "medio": "Medio",
    "anular": "Anular",
    "menique": "Meñique",
    "pulgar_flexion": "Pulgar · flexión",
    "pulgar_oposicion": "Pulgar · oposición",
}
NOMBRES_POSE = {"punio": "✊ Puño", "ok": "👌 OK", "rock": "🤘 Rock"}
MAX_REGISTRO = 40


# ───────────────────────── Comunicación ─────────────────────────

def enlace():
    return st.session_state.get("enlace")


def comando(linea, anotar=True):
    """Manda `linea` a la mano y devuelve (ok, datos). Con `anotar` (lo normal)
    queda en el registro y su resultado se muestra en pantalla; el sondeo
    periodico de ESTADO va con anotar=False."""
    try:
        respuesta = enlace().enviar(linea)
        ok, datos = parsear(respuesta)
    except Exception as error:  # puerto desconectado, sin respuesta, etc.
        respuesta, ok, datos = "ERROR de comunicación: {}".format(error), False, str(error)
    if anotar:
        registro = st.session_state.setdefault("registro", [])
        registro.insert(0, (linea, respuesta))
        del registro[MAX_REGISTRO:]
        st.session_state["ultimo_resultado"] = (ok, "{} → {}".format(linea, respuesta))
    return ok, datos


def conectar(modo, puerto):
    try:
        nuevo = EnlaceSimulado() if modo == "Simulado (sin placa)" else EnlaceSerial(puerto)
        nuevo.iniciar_servidor()
    except Exception as error:
        st.session_state["error_conexion"] = str(error)
        return
    st.session_state["error_conexion"] = None
    st.session_state["enlace"] = nuevo
    st.session_state["registro"] = []


def desconectar():
    if enlace() is not None:
        try:
            enlace().cerrar()
        except Exception:
            pass
    st.session_state["enlace"] = None


# ───────────────────────── Vista de la mano ─────────────────────────

def dibujar_mano(estado):
    columnas = ["pulgar_oposicion", "pulgar_flexion", "indice", "medio", "anular", "menique"]
    barras = []
    for eje in columnas:
        if eje not in estado["ejes"]:
            continue
        valor = estado["valores"].get(eje)
        pulso = estado["pulsos"].get(eje)
        relleno = 0 if valor is None else round(max(0.0, min(1.0, valor)) * 100)
        texto = "sin señal" if valor is None else "{} % · {} µs".format(relleno, pulso)
        barras.append(
            '<div style="flex:1;text-align:center;font-size:12px">'
            '<div style="height:110px;border:1px solid #8886;border-radius:10px;position:relative;overflow:hidden">'
            '<div style="position:absolute;left:0;right:0;top:0;height:{r}%;background:#e8590c;opacity:{o}"></div>'
            "</div>{nombre}<br><small>{t}</small></div>".format(
                r=relleno, o=0.9 if valor is not None else 0.2, nombre=NOMBRES_EJE[eje], t=texto)
        )
    st.markdown(
        '<div style="display:flex;gap:10px">' + "".join(barras) + "</div>"
        '<div style="font-size:12px;opacity:.7;margin-top:4px">Relleno = cuánto está cerrado cada dedo '
        "(0 % abierto, 100 % cerrado).</div>",
        unsafe_allow_html=True,
    )


# ───────────────────────── Pestañas ─────────────────────────

def pestana_poses(estado):
    st.subheader("Poses")
    columnas = st.columns(len(estado["poses"]) + 2)
    for columna, pose in zip(columnas, estado["poses"]):
        columna.button(NOMBRES_POSE.get(pose, pose), key="pose_" + pose, use_container_width=True,
                       on_click=comando, args=("POSE " + pose,))
    columnas[-2].button("🖐️ Abrir mano", use_container_width=True, on_click=comando, args=("ABRIR",))
    columnas[-1].button("Cerrar mano", use_container_width=True, on_click=comando, args=("CERRAR",))
    st.caption("Las poses usan la velocidad vigente (pestaña Velocidad). Un dedo que no esté conectado se ignora.")


def pestana_dedo(estado):
    st.subheader("Mover un solo dedo")
    eje = st.selectbox("Dedo", estado["ejes"], format_func=NOMBRES_EJE.get, key="dedo_sel")
    actual = estado["valores"].get(eje)
    posicion = st.slider("Posición (0 % abierto · 100 % cerrado)", 0, 100,
                         int(round((actual or 0) * 100)), key="pos_" + eje)
    a, b, c, d = st.columns(4)
    a.button("Mover a esa posición", key="mover_" + eje, use_container_width=True,
             on_click=comando, args=("DEDO {} {}".format(eje, posicion / 100),))
    b.button("Abrir", key="abrir_" + eje, use_container_width=True, on_click=comando, args=("DEDO {} 0".format(eje),))
    c.button("Cerrar", key="cerrar_" + eje, use_container_width=True, on_click=comando, args=("DEDO {} 1".format(eje),))
    d.button("Soltar este dedo", key="soltar_" + eje, use_container_width=True, on_click=comando, args=("SOLTAR " + eje,))

    with st.expander("Velocidad solo de este dedo", expanded=True):
        vc, va = estado["velocidades"][eje]
        minimo, maximo = estado["limites_vel"]
        cierre = st.slider("Velocidad al cerrar (µs/s)", minimo, maximo, int(vc), key="vc_" + eje)
        apertura = st.slider("Velocidad al abrir (µs/s)", minimo, maximo, int(va), key="va_" + eje)
        st.button("Aplicar velocidad a {}".format(NOMBRES_EJE[eje]), key="vel_" + eje, on_click=comando,
                  args=("VEL {} {} {}".format(cierre, apertura, eje),))


def pestana_velocidad(estado):
    st.subheader("Velocidad de toda la mano")
    minimo, maximo = estado["limites_vel"]
    vc, va = next(iter(estado["velocidades"].values()))
    cierre = st.slider("Velocidad al cerrar (µs/s)", minimo, maximo, int(vc), key="vc_todos")
    apertura = st.slider("Velocidad al abrir (µs/s)", minimo, maximo, int(va), key="va_todos")
    st.button("Aplicar a todos los dedos", on_click=comando, args=("VEL {} {}".format(cierre, apertura),))
    st.caption("~1000 µs/s equivalen a unos 90°/s. Abrir conviene más lento que cerrar: el dedo vuelve solo "
               "y un hilo que se afloja rápido se enreda. Esto reemplaza las velocidades propias de cada dedo.")
    st.dataframe(
        [{"Dedo": NOMBRES_EJE[e], "Cerrar (µs/s)": v[0], "Abrir (µs/s)": v[1]}
         for e, v in estado["velocidades"].items()],
        hide_index=True, use_container_width=True,
    )


def pestana_angulos(estado):
    st.subheader("Ángulos de abrir y cerrar")
    eje = st.selectbox("Dedo", estado["ejes"], format_func=NOMBRES_EJE.get, key="ang_sel")
    unidad = st.radio("Unidad", ["Grados (aprox.)", "Microsegundos (µs)"], horizontal=True, key="unidad")
    en_grados = unidad.startswith("Grados")
    minimo_us, maximo_us = estado["limites_us"]
    abierto_us, cerrado_us = estado["calibracion"][eje]

    if en_grados:
        limites = (us_a_grados(minimo_us), us_a_grados(maximo_us))
        valores = (us_a_grados(abierto_us), us_a_grados(cerrado_us))
        paso = 1.0
        a_us = grados_a_us
    else:
        limites = (float(minimo_us), float(maximo_us))
        valores = (float(abierto_us), float(cerrado_us))
        paso = 10.0
        a_us = float
    clave = "{}_{}".format(eje, "g" if en_grados else "us")
    c1, c2 = st.columns(2)
    abierto = c1.number_input("Abierto", limites[0], limites[1], round(valores[0], 1), paso, key="ab_" + clave)
    cerrado = c2.number_input("Cerrado", limites[0], limites[1], round(valores[1], 1), paso, key="ce_" + clave)
    abierto_nuevo, cerrado_nuevo = int(round(a_us(abierto))), int(round(a_us(cerrado)))
    sentido = "invertido (cierra al bajar el pulso)" if cerrado_nuevo < abierto_nuevo else "normal (cierra al subir el pulso)"
    st.caption("Pulsos: abierto **{} µs** · cerrado **{} µs** · sentido {}. Límite del firmware: {}–{} µs.".format(
        abierto_nuevo, cerrado_nuevo, sentido, minimo_us, maximo_us))

    a, b, c, d = st.columns(4)
    a.button("Aplicar (sin guardar)", key="aplicar_" + clave, use_container_width=True, on_click=comando,
             args=("ANGULOS {} {} {}".format(eje, abierto_nuevo, cerrado_nuevo),))
    b.button("Probar abierto", key="pa_" + clave, use_container_width=True, on_click=comando,
             args=("DEDO {} 0".format(eje),))
    c.button("Probar cerrado", key="pc_" + clave, use_container_width=True, on_click=comando,
             args=("DEDO {} 1".format(eje),))
    d.button("💾 Guardar en la placa", key="guardar_" + clave, use_container_width=True, on_click=comando,
             args=("GUARDAR",))
    st.warning("Flujo: 1) ajusta los valores, 2) «Aplicar», 3) «Probar abierto / cerrado» mirando el dedo, "
               "4) cuando quede bien, «Guardar». Si el servo zumba al llegar a un extremo, retrocede: está forzando "
               "el tope y se calienta. Aplicar no mueve el servo; las pruebas sí.")
    st.dataframe(
        [{"Dedo": NOMBRES_EJE[e], "Abierto (µs)": p[0], "Cerrado (µs)": p[1],
          "Abierto (°≈)": round(us_a_grados(p[0])), "Cerrado (°≈)": round(us_a_grados(p[1]))}
         for e, p in estado["calibracion"].items()],
        hide_index=True, use_container_width=True,
    )


def pestana_registro():
    st.subheader("Registro de comandos")
    st.dataframe([{"Comando": c, "Respuesta": r[:200]} for c, r in st.session_state.get("registro", [])],
                 hide_index=True, use_container_width=True)


# ───────────────────────── Página ─────────────────────────

with st.sidebar:
    st.header("Conexión")
    modo = st.radio("Modo", ["Simulado (sin placa)", "Placa por USB"], disabled=enlace() is not None, key="modo")
    puerto = None
    if modo == "Placa por USB":
        puertos = listar_puertos()
        puerto = st.selectbox("Puerto", [p for p, _ in puertos] or ["(ninguno)"], disabled=enlace() is not None,
                              format_func=lambda p: next((f"{p} · {d}" for q, d in puertos if q == p), p))
        st.caption("Usa el puerto del chip CH343 (el que mostró el REPL, p. ej. COM5). La app arranca "
                   "servidor_serial en la placa; hay que haberla subido antes (README, sección 11).")
    if enlace() is None:
        st.button("Conectar", type="primary", on_click=conectar, args=(modo, puerto), use_container_width=True)
    else:
        st.success("Conectado: {}".format(enlace().puerto))
        st.button("Desconectar", on_click=desconectar, use_container_width=True)
        st.button("⏹ Detener", on_click=comando, args=("DETENER",), use_container_width=True)
        st.button("Soltar todos los servos", on_click=comando, args=("SOLTAR",), use_container_width=True)
    if st.session_state.get("error_conexion"):
        st.error(st.session_state["error_conexion"])

st.title("🖐️ Mano robótica")

if enlace() is None:
    st.info("Elige un modo y pulsa **Conectar** en la barra lateral. El modo *Simulado* sirve para probar la app "
            "sin la mano.")
    st.stop()

ok, estado = comando("ESTADO", anotar=False)
if not ok or not estado:
    st.error("No se pudo leer el estado de la mano: {}".format(estado))
    st.stop()

resultado = st.session_state.get("ultimo_resultado")
dibujar_mano(estado)
if isinstance(enlace(), EnlaceSimulado):
    st.caption("Modo simulado · el último movimiento habría tardado {:.1f} s con las velocidades vigentes."
               .format(enlace().ultima_duracion_s))
if resultado:
    (st.success if resultado[0] else st.error)(resultado[1])
st.button("Actualizar estado")

tabs = st.tabs(["Poses", "Un dedo", "Velocidad", "Ángulos", "Registro"])
with tabs[0]:
    pestana_poses(estado)
with tabs[1]:
    pestana_dedo(estado)
with tabs[2]:
    pestana_velocidad(estado)
with tabs[3]:
    pestana_angulos(estado)
with tabs[4]:
    pestana_registro()
