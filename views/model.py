"""Desempeño del modelo sobre el conjunto de evaluación (HU-008), leído de model/metadata.json."""

import altair as alt
import pandas as pd
import streamlit as st

from src.prediction import load_metadata
from src.ui import (NEUTRAL_COLOR, POSITIVE_COLOR, card, card_title, kpi_card, page_header, poc_banner,
                    show_chart)

MODEL_COLORS = {"XGBoost": POSITIVE_COLOR, "Regresión logística": "#eb6834", "Trivial (siempre Aceptada)": NEUTRAL_COLOR}
METRIC_LABELS = {"accuracy": "Exactitud", "precision": "Precisión", "recall": "Recall",
                 "f1_score": "F1-score", "roc_auc": "AUC-ROC"}

metadata = load_metadata()
metrics = metadata["test_metrics"]
(tn, fp), (fn, tp) = metadata["conf_matrix"]["values"]
n_test = tn + fp + fn + tp

page_header("Desempeño del modelo", f"XGBoost {metadata['model_version']} · evaluado sobre {n_test} consultas "
            "que el modelo no vio durante el entrenamiento.", "monitoring")
poc_banner("Métricas obtenidas sobre datos simulados: miden qué tan bien el modelo recupera los supuestos de la "
           "simulación, no su desempeño sobre consultas reales del estudio.")

# ---------------------------------------------------------------- métricas en lenguaje llano
explanations = {
    "accuracy": (f"Acierta en {metrics['accuracy']:.0%} de las consultas",
                 "Proporción de consultas (admitidas y rechazadas) que el modelo clasifica correctamente."),
    "precision": (f"De cada 10 que marca admisibles, {metrics['precision'] * 10:.1f} lo fueron".replace(".", ","),
                  "Cuando el modelo predice 'Aceptada', ¿con qué frecuencia acierta? Alta precisión = pocas falsas alarmas."),
    "recall": (f"Detecta {tp} de las {tp + fn} admitidas",
               "De las consultas que realmente fueron admitidas, ¿qué proporción identifica el modelo?"),
    "f1_score": ("Equilibrio entre precisión y recall",
                 "Media armónica de precisión y recall: resume ambas en un solo número."),
    "roc_auc": ("Capacidad de ordenar por puntaje",
                "Probabilidad de que una consulta admitida reciba mayor puntaje que una rechazada. 0,5 = azar; 1 = perfecto."),
}
for col, (key, (caption, help_text)) in zip(st.columns(5), explanations.items()):
    with col:
        kpi_card(METRIC_LABELS[key], f"{metrics[key]:.2f}".replace(".", ","), caption=caption, help=help_text)

# ---------------------------------------------------------------- matriz de confusión + lectura
left, right = st.columns([1.1, 1], gap="large")
with left, card("confusion"):
    card_title("Matriz de confusión")
    cells = pd.DataFrame([
        {"Real": "Rechazada", "Predicho": "Rechazada", "n": tn, "tipo": "Verdaderos negativos", "ok": True},
        {"Real": "Rechazada", "Predicho": "Aceptada", "n": fp, "tipo": "Falsos positivos", "ok": False},
        {"Real": "Aceptada", "Predicho": "Rechazada", "n": fn, "tipo": "Falsos negativos", "ok": False},
        {"Real": "Aceptada", "Predicho": "Aceptada", "n": tp, "tipo": "Verdaderos positivos", "ok": True},
    ])
    cells["pct"] = cells["n"] / n_test
    labels = ["Rechazada", "Aceptada"]
    base = alt.Chart(cells).encode(
        x=alt.X("Predicho:N", sort=labels, title="Predicción del modelo", axis=alt.Axis(labelAngle=0, orient="top")),
        y=alt.Y("Real:N", sort=labels, title="Decisión real (simulada)"),
    )
    heat = base.mark_rect(stroke="white", strokeWidth=3, cornerRadius=6).encode(
        color=alt.Color("n:Q", scale=alt.Scale(range=["#cde2fb", "#184f95"]), legend=None),
        tooltip=[alt.Tooltip("tipo:N", title="Celda"), alt.Tooltip("n:Q", title="Consultas"),
                 alt.Tooltip("pct:Q", title="% del total", format=".0%")],
    )
    text_color = alt.condition(f"datum.n > {max(tn, fp, fn, tp) * 0.45}", alt.value("white"), alt.value("#0b0b0b"))
    count = base.mark_text(fontSize=26, fontWeight="bold", dy=-8).encode(text="n:Q", color=text_color)
    kind = base.mark_text(fontSize=11, dy=16).encode(text="tipo:N", color=text_color)
    show_chart((heat + count + kind).properties(height=300), width="stretch")

with right, card("reading"):
    card_title("Cómo leerla")
    st.markdown(
        f":material/check_circle: **{tp}** consultas admitidas fueron reconocidas como admisibles.  \n"
        f":material/check_circle: **{tn}** consultas rechazadas fueron reconocidas como no admisibles.  \n"
        f":material/error: **{fp}** rechazadas recibieron puntaje alto (*falsos positivos*): el socio las revisaría "
        "con expectativa favorable y las terminaría descartando.  \n"
        f":material/error: **{fn}** admitidas recibieron puntaje bajo (*falsos negativos*): el riesgo de que una "
        "consulta valiosa quede al final de la cola."
    )
    if fn < fp:
        st.info(f"El modelo **tiende a favorecer la admisión**: casi no deja escapar consultas admisibles "
                f"(recall {metrics['recall']:.0%}), a costa de sobrestimar algunas rechazadas. Para una herramienta de "
                "priorización que no decide por sí sola, es el error menos costoso.", icon=":material/lightbulb:")

# ---------------------------------------------------------------- comparación + importancia
left, right = st.columns(2, gap="large")
with left, card("comparison"):
    card_title("Comparación con alternativas")
    comparison = (pd.DataFrame(metadata["comparison"]).T.rename(columns=METRIC_LABELS)
                  .rename_axis("modelo").reset_index()
                  .melt(id_vars="modelo", var_name="metrica", value_name="valor"))
    models = list(MODEL_COLORS)
    dots = alt.Chart(comparison).mark_point(filled=True, size=140, opacity=1, stroke="white", strokeWidth=1.5).encode(
        y=alt.Y("metrica:N", sort=list(METRIC_LABELS.values()), title=None, axis=alt.Axis(labelFontSize=12)),
        x=alt.X("valor:Q", title=None, scale=alt.Scale(domain=[0.4, 1.0]), axis=alt.Axis(format=".1f")),
        color=alt.Color("modelo:N", title=None, sort=models,
                        scale=alt.Scale(domain=models, range=list(MODEL_COLORS.values())),
                        legend=alt.Legend(orient="top", columns=3, labelLimit=260)),
        shape=alt.Shape("modelo:N", sort=models, legend=None),
        tooltip=[alt.Tooltip("modelo:N", title="Modelo"), alt.Tooltip("metrica:N", title="Métrica"),
                 alt.Tooltip("valor:Q", title="Valor", format=".3f")],
    )
    show_chart(dots.properties(height=alt.Step(42)), width="stretch")
    st.caption("XGBoost y la regresión logística rinden de forma muy similar sobre estos datos simulados (generados "
               "con reglas simples); ambos superan ampliamente al clasificador trivial. XGBoost se eligió por los "
               "criterios del Marco Teórico: relaciones no lineales sin especificarlas e integración con SHAP.")

with right, card("importance"):
    card_title("¿Qué variables pesan más?")
    importance = pd.Series(metadata["global_importance"]).rename_axis("variable").reset_index(name="impacto")
    importance["share"] = importance["impacto"] / importance["impacto"].sum()
    base = alt.Chart(importance).encode(
        y=alt.Y("variable:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240, labelFontSize=12)),
        x=alt.X("impacto:Q", title="Impacto medio |SHAP| (log-odds)", axis=alt.Axis(grid=False)),
    )
    show_chart(
        (base.mark_bar(color=POSITIVE_COLOR, cornerRadiusEnd=4, height=16).encode(
            tooltip=[alt.Tooltip("variable:N", title="Variable"), alt.Tooltip("impacto:Q", title="Impacto", format=".3f"),
                     alt.Tooltip("share:Q", title="% del impacto total", format=".0%")])
         + base.mark_text(align="left", dx=5, fontSize=11).encode(text=alt.Text("share:Q", format=".0%")))
        .properties(height=alt.Step(30)),
        width="stretch",
    )
    zero = importance.loc[importance["impacto"] == 0, "variable"].tolist()
    st.caption("La documentación y el plazo de prescripción explican la mayor parte de las decisiones, en línea con "
               "la lógica con la que se generó la simulación." +
               (f" Sin influencia: {', '.join(v.lower() for v in zero)}." if zero else ""))

# ---------------------------------------------------------------- ficha técnica
with st.expander("Ficha técnica del entrenamiento", icon=":material/description:"):
    split = metadata["split"]
    hp = metadata["hyperparameters"]
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Datos**  \n{metadata['dataset']}  \n"
                f"Entrenamiento: {split['n_train']} · Evaluación: {split['n_test']} (estratificado, semilla {split['random_state']})")
    c2.markdown("**Hiperparámetros** (búsqueda en grilla + validación cruzada 5 particiones sobre entrenamiento)  \n" +
                "  \n".join(f"`{k}` = {hp[k]}" for k in ["max_depth", "n_estimators", "learning_rate",
                                                         "subsample", "colsample_bytree"] if k in hp))
    c3.markdown(f"**Artefacto**  \n`{metadata['model_file']}`  \nSHA-256: `{metadata['model_sha256']}`  \n"
                f"Entrenado el {metadata['trained_on']}  \n" +
                " · ".join(f"{k} {v}" for k, v in metadata["versions"].items()))
    st.caption("Detalle completo en notebooks/01_eda.ipynb y notebooks/02_model_training.ipynb.")
