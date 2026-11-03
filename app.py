"""Punto de entrada Streamlit: gate de autenticación + navegación."""

import hmac
import os

import streamlit as st

from src.ui import inject_css, warm_up_model

st.set_page_config(page_title="Scoring de admisión · Carna, Mango & Asoc.", page_icon=":material/balance:",
                   layout="wide",
                   initial_sidebar_state="expanded" if st.session_state.get("authenticated") else "collapsed")
inject_css()  # antes del login, para que también tome los estilos


def get_app_password() -> str | None:
    """Secreto del hosting (variable de entorno, como lo entrega Hugging Face Spaces) o secrets.toml local."""
    if os.environ.get("APP_PASSWORD"):
        return os.environ["APP_PASSWORD"]
    try:
        return st.secrets["APP_PASSWORD"]
    except (KeyError, FileNotFoundError):
        return None


def check_access() -> bool:
    if st.session_state.get("authenticated"):
        return True

    expected = get_app_password()
    if not expected:
        st.error("Falta configurar APP_PASSWORD (variable de entorno / secreto del hosting, o .streamlit/secrets.toml).")
        return False

    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        st.space("large")
        with st.container(key="login_card"):
            st.html('<div class="cm-login__mark">balance</div>'
                    '<h1 class="cm-login__title">Scoring de admisión</h1>'
                    '<p class="cm-login__subtitle">Carna, Mango &amp; Asoc. · Prototipo de apoyo a la decisión</p>')
            with st.form("login", border=False):
                password = st.text_input("Contraseña del estudio", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Ingresar", type="primary", icon=":material/lock_open:",
                                                  width="stretch")
            if submitted:
                if hmac.compare_digest(password.encode(), str(expected).encode()):
                    st.session_state["authenticated"] = True
                    st.rerun()
                st.error("Contraseña incorrecta.", icon=":material/error:")
            st.html('<div class="cm-login__foot">Acceso restringido al equipo del estudio · Datos 100% simulados</div>')
    return False


if not check_access():
    st.stop()

warm_up_model()  # ~2,5 s una sola vez por proceso; los reruns siguientes no lo pagan

st.logo("assets/logo.svg", size="large", icon_image=":material/balance:")
navigation = st.navigation({
    "Consultas": [
        st.Page("views/intake.py", title="Nueva consulta", icon=":material/edit_note:", default=True),
        st.Page("views/result.py", title="Resultado de la predicción", icon=":material/insights:"),
        st.Page("views/inquiries.py", title="Listado e historial", icon=":material/list_alt:"),
    ],
    "Modelo": [
        st.Page("views/model.py", title="Desempeño del modelo", icon=":material/monitoring:"),
    ],
})

with st.sidebar:
    st.caption("Prototipo académico (TFG) entrenado sobre datos **100% simulados**. "
               "El puntaje apoya, sin reemplazar, el criterio de los socios.")
    if st.button("Cerrar sesión", icon=":material/logout:"):
        st.session_state.clear()
        st.rerun()

navigation.run()
