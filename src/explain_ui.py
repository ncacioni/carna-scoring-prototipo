"""Visualizaciones de la Pantalla 2: medidor del puntaje, cascada SHAP y resumen en lenguaje natural."""

import math

import altair as alt
import pandas as pd

from src.ui import BRAND, NEGATIVE_COLOR, NEUTRAL_COLOR, POSITIVE_COLOR, score_band

TRACK_COLOR = "#ebe8df"

MIN_VISIBLE_SHIFT = 0.5  # pp: por debajo de esto la variable se agrupa en "Otras variables"


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def to_percentage(logodds: float) -> float:
    return _sigmoid(logodds) * 100


def display_value(column: str, inquiry: dict) -> str:
    """Valor de la consulta para una variable del modelo, en texto legible."""
    if column == "monto_informado":
        return "Sí" if inquiry.get("monto_estimado") is not None else "No"
    value = inquiry.get(column)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "No informado"
    if column == "monto_estimado":
        return "$ " + f"{float(value):,.0f}".replace(",", ".")
    return str(value)


def gauge_chart(score: float) -> alt.LayerChart:
    """Medidor semicircular 0-100 con el puntaje al centro."""
    _, _, color = score_band(score)
    theta = alt.Scale(domain=[0, 100], range=[-math.pi / 2, math.pi / 2])
    width, cx, cy, outer = 260, 130, 122, 112  # centro del semicírculo en el borde inferior
    data = pd.DataFrame({"start": [0, 0], "end": [100, score], "layer": ["track", "value"]})
    arc = alt.Chart(data).mark_arc(innerRadius=outer - 30, outerRadius=outer, cornerRadius=6).encode(
        theta=alt.Theta("start:Q", scale=theta),
        theta2="end:Q",
        x=alt.value(cx), y=alt.value(cy),
        color=alt.Color("layer:N", scale=alt.Scale(domain=["track", "value"], range=[TRACK_COLOR, color]),
                        legend=None),
        order=alt.Order("layer:N", sort="ascending"),
    )
    number = alt.Chart(pd.DataFrame({"t": [f"{score:.0f}%"]})).mark_text(
        fontSize=46, fontWeight="bold", baseline="bottom", color=BRAND["ink"], font="Source Serif 4").encode(text="t:N", x=alt.value(cx), y=alt.value(cy))
    scale_labels = alt.Chart(pd.DataFrame({"t": ["0", "100"], "px": [cx - outer + 15, cx + outer - 15]})).mark_text(
        fontSize=11, baseline="top", color=NEUTRAL_COLOR).encode(
        text="t:N", x=alt.X("px:Q", scale=None), y=alt.value(cy + 4))
    return (arc + number + scale_labels).properties(width=width, height=cy + 20).configure_view(stroke=None)


def waterfall_frame(shap_values: list[dict], base_logodds: float, inquiry: dict) -> pd.DataFrame:
    """Cascada en espacio de probabilidad (puntos porcentuales).

    SHAP es aditivo en log-odds; se acumula en ese espacio en el orden de magnitud y cada paso se
    convierte a probabilidad, de modo que el último paso coincide exactamente con el puntaje del modelo.
    """
    steps, small = [], 0.0
    current = base_logodds
    base_pct = _sigmoid(base_logodds) * 100
    steps.append({"paso": "Punto de partida: promedio del histórico", "inicio": 0.0, "fin": base_pct,
                  "tipo": "Referencia", "etiqueta": f"{base_pct:.0f}%"})
    for item in sorted(shap_values, key=lambda v: abs(v["contribucion"]), reverse=True):
        before = _sigmoid(current) * 100
        current += item["contribucion"]
        after = _sigmoid(current) * 100
        if abs(after - before) < MIN_VISIBLE_SHIFT:
            small += after - before
            continue
        steps.append({
            "paso": f"{item['variable']}: {display_value(item['columna'], inquiry)}",
            "inicio": before, "fin": after,
            "tipo": "Sube el puntaje" if after > before else "Baja el puntaje",
            "etiqueta": f"{after - before:+.0f} pp",
        })
    if abs(small) >= 0.05:
        end = steps[-1]["fin"]
        steps.append({"paso": "Otras variables", "inicio": end, "fin": end + small,
                      "tipo": "Sube el puntaje" if small > 0 else "Baja el puntaje", "etiqueta": f"{small:+.1f} pp"})
    final = _sigmoid(current) * 100
    steps.append({"paso": "Puntaje de esta consulta", "inicio": 0.0, "fin": final,
                  "tipo": "Referencia", "etiqueta": f"{final:.0f}%"})
    df = pd.DataFrame(steps)
    df["orden"] = range(len(df))
    df["delta"] = df["fin"] - df["inicio"]
    return df


def waterfall_chart(frame: pd.DataFrame) -> alt.LayerChart:
    order = frame["paso"].tolist()
    color = alt.Color("tipo:N", title=None, legend=alt.Legend(orient="top", labelFontSize=12),
                      scale=alt.Scale(domain=["Sube el puntaje", "Baja el puntaje", "Referencia"],
                                      range=[POSITIVE_COLOR, NEGATIVE_COLOR, NEUTRAL_COLOR]))
    base = alt.Chart(frame).encode(
        y=alt.Y("paso:N", sort=order, title=None, axis=alt.Axis(labelLimit=360, labelFontSize=12.5)),
    )
    bars = base.mark_bar(height=20, cornerRadius=3).encode(
        x=alt.X("inicio:Q", title="Puntaje (%)", scale=alt.Scale(domain=[0, 112], nice=False),
                axis=alt.Axis(values=[0, 25, 50, 75, 100], gridOpacity=0.5)),
        x2="fin:Q",
        color=color,
        tooltip=[alt.Tooltip("paso:N", title="Paso"), alt.Tooltip("etiqueta:N", title="Efecto"),
                 alt.Tooltip("fin:Q", title="Puntaje acumulado", format=".1f")],
    )
    # etiqueta siempre a la derecha de la barra (las negativas cerca de 0 chocarían con el eje)
    labels = base.mark_text(align="left", dx=6, fontSize=12, fontWeight="bold").encode(
        x="right_edge:Q", text="etiqueta:N").transform_calculate(right_edge="max(datum.inicio, datum.fin)")
    # conectores verticales entre pasos consecutivos
    links = frame.iloc[:-1].assign(siguiente=frame["paso"].shift(-1).iloc[:-1])
    connectors = alt.Chart(links).mark_rule(strokeDash=[3, 3], color=NEUTRAL_COLOR, opacity=0.6).encode(
        x="fin:Q", y=alt.Y("paso:N", sort=order), y2="siguiente:N")
    return (bars + connectors + labels).properties(height=alt.Step(36))


def explanation_text(shap_values: list[dict], inquiry: dict, top: int = 2) -> str:
    """Resumen en lenguaje natural de los factores principales, con el valor de cada uno en la consulta."""
    def describe(items):
        parts = [f"**{v['variable'].lower()}** ({display_value(v['columna'], inquiry)})" for v in items]
        return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " y " + parts[-1]

    ranked = sorted(shap_values, key=lambda v: abs(v["contribucion"]), reverse=True)
    up = [v for v in ranked if v["contribucion"] >= 0.05][:top]
    down = [v for v in ranked if v["contribucion"] <= -0.05][:top]
    sentences = []
    if up:
        sentences.append(f"Lo que más **eleva** el puntaje: {describe(up)}.")
    if down:
        sentences.append(f"Lo que más lo **reduce**: {describe(down)}.")
    if not sentences:
        sentences.append("Ninguna variable se aparta de forma marcada del promedio del histórico.")
    return " ".join(sentences)


def shap_table(shap_values: list[dict], inquiry: dict) -> pd.DataFrame:
    """Detalle técnico (log-odds) para trazabilidad."""
    return pd.DataFrame([
        {"Variable": v["variable"], "Valor en la consulta": display_value(v["columna"], inquiry),
         "Aporte SHAP (log-odds)": v["contribucion"],
         "Sentido": "Sube" if v["contribucion"] > 0 else ("Baja" if v["contribucion"] < 0 else "Neutro")}
        for v in sorted(shap_values, key=lambda v: abs(v["contribucion"]), reverse=True)
    ])
