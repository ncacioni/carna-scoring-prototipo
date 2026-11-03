"""Capa de interfaz compartida: tokens de marca, CSS, componentes, caché de lecturas y gráficos.

Todo selector CSS apunta a clases estables: `.st-key-<key>` (generada por st.container(key=...)) y
`data-testid` documentados. Nada depende de clases hasheadas de emotion (`.st-emotion-cache-*`).
"""

import html
import re

import pandas as pd
import streamlit as st

from src import db
from src.constants import POC_WARNING

BRAND = {
    "navy": "#13294b",
    "navy_2": "#1f3d6e",
    "gold": "#c9a86a",
    "paper": "#f7f6f2",
    "surface": "#ffffff",
    "ink": "#1c2230",
    "ink_2": "#52514e",
    "muted": "#74736d",
    "border": "#e1ddd2",
    "positive": "#2a78d6",
    "negative": "#e34948",
    "warning_bg": "#fbf1d9",
    "warning_ink": "#6b4a00",
}

_CSS = """
<style>
/* ---------- layout general ---------- */
[data-testid="stMainBlockContainer"] { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1280px; }
h1, h2, h3 { letter-spacing: -0.01em; }

/* ---------- tarjetas: cualquier st.container(key="card_...") ---------- */
[class*="st-key-card"] {
  background: %(surface)s;
  border: 1px solid %(border)s;
  border-radius: 14px;
  padding: 1.25rem 1.4rem;
  box-shadow: 0 1px 2px rgba(19,41,75,.04), 0 6px 18px -10px rgba(19,41,75,.18);
}

/* ---------- métricas nativas ---------- */
[data-testid="stMetric"] {
  background: %(surface)s;
  border: 1px solid %(border)s;
  border-radius: 12px;
  padding: .9rem 1.1rem;
}
[data-testid="stMetricLabel"] p {
  text-transform: uppercase; letter-spacing: .06em; font-size: .72rem; font-weight: 600; color: %(ink_2)s;
}

/* ---------- encabezado de página ---------- */
.cm-header { display: flex; align-items: flex-start; gap: 1rem; margin: 0 0 1.4rem 0; }
.cm-header__icon {
  flex: none; width: 48px; height: 48px; border-radius: 12px;
  display: grid; place-items: center;
  background: %(navy)s; color: %(gold)s;
  font-family: "Material Symbols Rounded"; font-size: 28px; line-height: 1;
}
.cm-header__eyebrow {
  font-size: .72rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: %(gold)s;
  margin-bottom: .15rem;
}
.cm-header__title {
  font-family: "Source Serif 4", Georgia, serif; font-weight: 700; font-size: 2.1rem; line-height: 1.15;
  color: %(ink)s; margin: 0;
}
.cm-header__subtitle { color: %(ink_2)s; margin-top: .35rem; font-size: .98rem; max-width: 70ch; }

/* ---------- banner de prueba de concepto (HU-003 AC3) ---------- */
.cm-poc {
  display: flex; gap: .75rem; align-items: center;
  background: %(warning_bg)s; color: %(warning_ink)s;
  border: 1px solid #ecd9a6; border-left: 5px solid #c98500;
  border-radius: 10px; padding: .7rem 1rem; margin-bottom: 1.1rem; font-size: .93rem;
}
.cm-poc__icon { font-family: "Material Symbols Rounded"; font-size: 22px; line-height: 1; }

/* ---------- KPI / puntaje ---------- */
.cm-kpi__label {
  font-size: .72rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: %(ink_2)s;
}
.cm-kpi__value {
  font-family: "Source Serif 4", Georgia, serif; font-weight: 700; font-size: 3.4rem; line-height: 1;
  color: %(ink)s; margin: .35rem 0 .2rem;
}
.cm-kpi__value small { font-size: 1.4rem; color: %(ink_2)s; font-weight: 600; }
.cm-kpi__hint { font-size: .82rem; color: %(muted)s; }
.cm-meter { height: 10px; border-radius: 999px; background: #ebe8df; overflow: hidden; margin-top: .6rem; }
.cm-meter > span { display: block; height: 100%%; border-radius: 999px; }

/* ---------- chips de datos de la consulta ---------- */
.cm-facts { display: grid; grid-template-columns: max-content 1fr; gap: .35rem 1rem; font-size: .92rem; }
.cm-facts dt { color: %(ink_2)s; }
.cm-facts dd { margin: 0; color: %(ink)s; font-weight: 500; }

/* ---------- sidebar ---------- */
.cm-brand { padding: .2rem 0 1rem; border-bottom: 1px solid rgba(255,255,255,.12); margin-bottom: .8rem; }
.cm-brand__name { font-family: "Source Serif 4", Georgia, serif; font-size: 1.15rem; font-weight: 700; color: #fff; }
.cm-brand__tag { font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: %(gold)s; }

/* ---------- login ---------- */
.st-key-login_card {
  background: %(surface)s; border: 1px solid %(border)s; border-radius: 18px;
  padding: 2.2rem 2.2rem 1.6rem; box-shadow: 0 24px 60px -30px rgba(19,41,75,.45);
  border-top: 5px solid %(navy)s;
}
.cm-login__mark {
  width: 56px; height: 56px; border-radius: 14px; background: %(navy)s; color: %(gold)s;
  display: grid; place-items: center; font-family: "Material Symbols Rounded"; font-size: 32px; margin-bottom: 1rem;
}
.cm-login__title { font-family: "Source Serif 4", Georgia, serif; font-size: 1.75rem; font-weight: 700; color: %(ink)s; margin: 0; }
.cm-login__subtitle { color: %(ink_2)s; font-size: .95rem; margin: .3rem 0 1.2rem; }
.cm-login__foot { color: %(muted)s; font-size: .78rem; margin-top: .9rem; text-align: center; }

/* ---------- botón primario ---------- */
[data-testid="stBaseButton-primary"] { font-weight: 600; box-shadow: 0 6px 14px -8px rgba(31,61,110,.7); }

/* ---------- encabezado de Streamlit: transparente y sin bloquear clics sobre el contenido ---------- */
[data-testid="stHeader"] { background: transparent; pointer-events: none; z-index: 999992; }  /* por encima del sidebar (999991) para que el logo y el botón de expandir se vean en el riel */
[data-testid="stHeader"] * { pointer-events: auto; }

/* ---------- sidebar colapsado como riel de íconos ----------
   Streamlit lo deja en ancho 0 y lo desplaza fuera de pantalla; acá se lo fija en 68px, solo con íconos,
   y el logo + botón de expandir (que Streamlit pone en el encabezado) se ubican dentro del riel. */
[data-testid="stSidebar"][aria-expanded="false"] {
  transform: none !important; width: 68px !important; min-width: 68px !important; max-width: 68px !important;
  visibility: visible !important; overflow: visible !important;
}
[data-testid="stSidebar"][aria-expanded="false"] > div,
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarContent"] {
  width: 68px !important; overflow: visible !important;
}
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarHeader"],
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarUserContent"],
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stNavSectionHeader"],
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavSeparator"] { display: none !important; }
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNav"] { padding-top: 6.2rem; }
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavItems"] { padding: 0 !important; }
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLinkContainer"] { margin: .2rem 0; }
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLink"] {
  justify-content: center; width: 46px; height: 42px; margin: 0 auto; padding: 0; position: relative;
}
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLink"] [data-testid="stIconMaterial"] { font-size: 1.35rem; }
/* nombre de la página como globo al pasar el mouse */
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLink"] span[label] {
  display: none; position: absolute; left: 56px; top: 50%%; transform: translateY(-50%%); z-index: 1000;
  background: %(navy)s; color: #fff; border: 1px solid %(gold)s; border-radius: 8px;
  padding: .3rem .65rem; white-space: nowrap; box-shadow: 0 8px 20px -10px rgba(0,0,0,.5);
}
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLink"]:hover span[label] { display: block; }
[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarNavLink"] span[label] p { color: #fff; font-size: .85rem; }
/* logo y botón de expandir dentro del riel */
[data-testid="stHeaderLogo"] { position: fixed; top: 1.1rem; left: 17px; z-index: 1000; }
[data-testid="stExpandSidebarButton"] {
  position: fixed; top: 3.7rem; left: 15px; z-index: 1000; color: %(gold)s !important;
  border-radius: 8px; width: 38px; height: 34px;
}
[data-testid="stExpandSidebarButton"]:hover { background: rgba(255,255,255,.08); }
[data-testid="stExpandSidebarButton"] span, [data-testid="stHeaderLogo"] span, [data-testid="stHeaderLogo"] svg { color: %(gold)s !important; fill: currentColor; }
[data-testid="stHeaderLogo"] [data-testid="stIconMaterial"] { font-size: 1.7rem; }
/* ---------- KPI dentro de tarjeta: la tarjeta ya da el marco ---------- */
[class*="st-key-card"] [data-testid="stMetric"] { border: none; padding: 0; background: transparent; }
[class*="st-key-card_kpi"] { padding: 1rem 1.2rem .8rem; }

/* ---------- título de sección numerado ---------- */
.cm-section { display: flex; align-items: center; gap: .7rem; margin-bottom: .15rem; }
.cm-section__step {
  flex: none; width: 28px; height: 28px; border-radius: 50%%; display: grid; place-items: center;
  background: %(navy)s; color: %(gold)s; font-weight: 700; font-size: .85rem;
}
.cm-section__title { font-family: "Source Serif 4", Georgia, serif; font-weight: 600; font-size: 1.2rem; color: %(ink)s; }
.cm-section__caption { color: %(muted)s; font-size: .86rem; margin: 0 0 .5rem 2.45rem; }

/* ---------- título de tarjeta ---------- */
.cm-card-title { font-family: "Source Serif 4", Georgia, serif; font-weight: 600; font-size: 1.15rem; color: %(ink)s; margin-bottom: .2rem; }
.cm-check { list-style: none; margin: .4rem 0 .6rem !important; padding: 0 !important; font-size: .88rem; }
.cm-check li { display: grid; grid-template-columns: 20px 1fr auto; gap: .5rem; align-items: center;
  padding: .32rem 0; border-bottom: 1px dashed %(border)s; }
.cm-check li:last-child { border-bottom: none; }
.cm-check__icon { font-family: "Material Symbols Rounded"; font-size: 18px; line-height: 1; }
.cm-check li.done .cm-check__icon { color: %(positive)s; }
.cm-check li.todo .cm-check__icon { color: #b9b6ac; }
.cm-check__label { color: %(ink_2)s; }
.cm-check__value { color: %(ink)s; font-weight: 600; text-align: right; max-width: 15ch;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cm-check li.todo .cm-check__value { color: #b9b6ac; font-weight: 400; }
.cm-rank { font-family: "Source Serif 4", Georgia, serif; font-weight: 700; font-size: 1.6rem; color: %(gold)s; text-align: center; }
</style>
""" % BRAND


def inject_css() -> None:
    """Llamar una vez por ejecución, desde app.py, antes de navigation.run()."""
    st.html(_CSS)  # solo <style>: Streamlit lo manda al contenedor de eventos, no ocupa espacio


def _esc(text: str) -> str:
    return html.escape(str(text))


def page_header(title: str, subtitle: str | None = None, icon: str | None = None,
                eyebrow: str | None = "Carna, Mango & Asoc.") -> None:
    """Encabezado de página. `icon` = nombre de Material Symbol sin prefijo (p. ej. "edit_note")."""
    icon_html = f'<div class="cm-header__icon">{_esc(icon)}</div>' if icon else ""
    eyebrow_html = f'<div class="cm-header__eyebrow">{_esc(eyebrow)}</div>' if eyebrow else ""
    subtitle_html = f'<div class="cm-header__subtitle">{_esc(subtitle)}</div>' if subtitle else ""
    st.html(f'<div class="cm-header">{icon_html}<div>{eyebrow_html}'
            f'<h1 class="cm-header__title">{_esc(title)}</h1>{subtitle_html}</div></div>')


def poc_banner(text: str) -> None:
    """Advertencia de prueba de concepto (HU-003 AC3): fija, visible, arriba de todo."""
    st.html(f'<div class="cm-poc" role="alert"><span class="cm-poc__icon">science</span>'
            f'<span>{_esc(text)}</span></div>')


def section_title(step: int | str, title: str, caption: str | None = None) -> None:
    caption_html = f'<div class="cm-section__caption">{_esc(caption)}</div>' if caption else ""
    st.html(f'<div class="cm-section"><span class="cm-section__step">{_esc(step)}</span>'
            f'<span class="cm-section__title">{_esc(title)}</span></div>{caption_html}')


def card_title(text: str) -> None:
    st.html(f'<div class="cm-card-title">{_esc(text)}</div>')


def checklist(rows: list[tuple[str, str | None]]) -> None:
    """Lista de campos con estado completo/pendiente y su valor (resumen del formulario de intake)."""
    items = "".join(
        f'<li class="{"done" if value else "todo"}"><span class="cm-check__icon">'
        f'{"check_circle" if value else "radio_button_unchecked"}</span>'
        f'<span class="cm-check__label">{_esc(label)}</span>'
        f'<span class="cm-check__value">{_esc(value) if value else "—"}</span></li>'
        for label, value in rows)
    st.html(f'<ul class="cm-check">{items}</ul>')


def kpi_card(label: str, value: str, caption: str | None = None, help: str | None = None) -> None:
    with card("kpi_" + re.sub(r"\W+", "_", label.lower())):
        st.metric(label, value, help=help)
        if caption:
            st.caption(caption)


def score_band(score: float) -> tuple[str, str, str]:
    """Devuelve (etiqueta, color de st.badge, color hex) para un puntaje 0-100."""
    for threshold, label, badge_color, hex_color in SCORE_BANDS:
        if score >= threshold:
            return label, badge_color, hex_color
    return SCORE_BANDS[-1][1:]


def show_chart(chart, **kwargs) -> None:
    """st.altair_chart con fondo transparente, para que el gráfico se integre a la tarjeta que lo contiene."""
    st.altair_chart(chart.configure(background="transparent"), **kwargs)


def card(key: str):
    """Contenedor-tarjeta: `with card("score"): ...` -> clase st-key-card_score."""
    return st.container(key=f"card_{key}")


POSITIVE_COLOR = BRAND["positive"]  # empuja hacia "Aceptada"
NEGATIVE_COLOR = BRAND["negative"]  # empuja hacia "Rechazada"
NEUTRAL_COLOR = "#8a8984"           # referencias (punto de partida, resultado)

# Bandas cualitativas del puntaje: ordenan el criterio, no son probabilidades reales (HU-003 AC3).
# (umbral, etiqueta, color de st.badge, color hex)
SCORE_BANDS = [(70, "Alta", "blue", POSITIVE_COLOR), (40, "Media", "orange", "#eda100"), (0, "Baja", "red", NEGATIVE_COLOR)]

CURRENT_INQUIRY_KEY = "current_inquiry"


# ---------------------------------------------------------------- datos (cacheados)

@st.cache_resource
def get_engine():
    return db.create_db_engine()


@st.cache_data(ttl=60, show_spinner=False)
def load_pending() -> pd.DataFrame:
    return db.list_pending(get_engine())


@st.cache_data(ttl=60, show_spinner=False)
def load_history() -> pd.DataFrame:
    return db.list_history(get_engine())


@st.cache_data(ttl=3600, show_spinner=False)
def load_partners() -> dict[str, int]:
    return {p["nombre"]: p["id_socio"] for p in db.list_partners(get_engine())}


@st.cache_data(ttl=600, show_spinner=False)
def cached_admission_rates(column: str) -> pd.DataFrame:
    return db.admission_rate_by(get_engine(), column)


def invalidate_lists() -> None:
    """Llamar después de cada escritura (nueva consulta, predicción o decisión)."""
    load_pending.clear()
    load_history.clear()
    cached_admission_rates.clear()


def warm_up_model() -> None:
    """Precarga modelo y explainer (una vez por proceso) para que el primer 'Calcular puntaje' no espere."""
    from src.prediction import load_model
    load_model()


# ---------------------------------------------------------------- navegación y formato

def show_poc_warning():
    """HU-003 AC3: advertencia fija, arriba de todo, antes del puntaje."""
    poc_banner(POC_WARNING)


def open_inquiry(inquiry_id: str):
    st.session_state[CURRENT_INQUIRY_KEY] = inquiry_id
    st.switch_page("views/result.py")


def format_ars(value) -> str:
    if value is None or pd.isna(value):
        return "No informado"
    return "$ " + f"{float(value):,.0f}".replace(",", ".")
