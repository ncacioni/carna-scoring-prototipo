"""Pantalla 2 — Resultado de la predicción (HU-003, HU-004, HU-006)."""

import streamlit as st

from src import db
from src.constants import ACCEPTED, DOMAINS, REJECTED
from src.explain_ui import (display_value, explanation_text, gauge_chart, shap_table, to_percentage,
                            waterfall_chart, waterfall_frame)
from src.prediction import base_value, load_metadata
from src.ui import (CURRENT_INQUIRY_KEY, card, card_title, get_engine, invalidate_lists, load_partners,
                    load_pending, page_header, score_band, show_chart, show_poc_warning)

DECISION_LABELS = {"Admitir": ":material/check_circle: Admitir", "Rechazar": ":material/cancel: Rechazar"}
STATUS_BADGES = {None: ("Pendiente", "gray", ":material/schedule:"),
                 ACCEPTED: ("Aceptada", "blue", ":material/check_circle:"),
                 REJECTED: ("Rechazada", "red", ":material/cancel:")}
INQUIRY_FIELDS = [("Canal de ingreso", "canal_ingreso", ":material/call:"),
                  ("Tipo de reclamo", "tipo_reclamo", ":material/description:"),
                  ("Jurisdicción", "jurisdiccion", ":material/location_on:"),
                  ("Monto estimado", "monto_estimado", ":material/payments:"),
                  ("Prescripción", "estado_prescripcion", ":material/hourglass_bottom:"),
                  ("Documentación", "documentacion_aportada", ":material/folder_open:")]

engine = get_engine()

# 1. Advertencia fija, antes que cualquier otra cosa (HU-003 AC3)
show_poc_warning()

pending_ids = load_pending()["id_consulta"].tolist()
current = st.session_state.get(CURRENT_INQUIRY_KEY)
options = ([current] if current and current not in pending_ids else []) + pending_ids

head, picker = st.columns([3, 1.2], vertical_alignment="bottom")
with head:
    page_header("Resultado de la predicción", "Puntaje estimado y factores que lo explican, como base común "
                "para la evaluación de los socios.", "insights")
if not options:
    st.info("No hay consultas pendientes. Cargá una nueva desde **Nueva consulta**.", icon=":material/inbox:")
    st.stop()
inquiry_id = picker.selectbox("Consulta", options, index=options.index(current) if current in options else 0,
                              help="Por defecto, la última consulta cargada; también se puede elegir cualquier pendiente.")
st.session_state[CURRENT_INQUIRY_KEY] = inquiry_id
inquiry = db.get_inquiry(engine, inquiry_id)

# HU-003 AC1: si la consulta todavía no tiene predicción, se procesa ahora y se guarda
prediction = db.get_latest_prediction(engine, inquiry_id)
if prediction is None:
    from src.prediction import predict
    score, shap_values, model_version = predict(db.get_predictors(engine, inquiry_id))
    db.insert_prediction(engine, inquiry_id, score, shap_values, model_version)
    invalidate_lists()
    prediction = db.get_latest_prediction(engine, inquiry_id)
score = prediction["puntaje_admision"]
shap_values = prediction["variables_shap"]
band_label, band_color, _ = score_band(score)

status_label, status_color, status_icon = STATUS_BADGES[inquiry["resultado_admision"]]
with st.container(horizontal=True, gap="small"):
    st.badge(inquiry_id, icon=":material/tag:", color="primary")
    st.badge(f"{inquiry['fecha_consulta']:%d/%m/%Y}", icon=":material/calendar_today:", color="gray")
    st.badge(inquiry["area_practica"], icon=":material/gavel:", color="gray")
    st.badge(status_label, icon=status_icon, color=status_color)

# 2. Puntaje (medidor) + por qué (cascada SHAP, HU-004)
score_col, why_col = st.columns([1, 2.1], gap="medium")
with score_col, card("score"):
    card_title("Puntaje de admisión")
    show_chart(gauge_chart(score), width="content")
    st.badge(f"Afinidad {band_label.lower()}", color=band_color, icon=":material/donut_large:")
    st.caption(f"Ubica la consulta respecto de los criterios aprendidos del histórico **simulado**. "
               f"Promedio del histórico: {to_percentage(base_value()):.0f}%.")
    st.caption(f"Modelo {prediction['version_modelo']} · {prediction['fecha_prediccion']:%d/%m/%Y %H:%M}")

with why_col, card("why"):
    card_title("¿Por qué este puntaje?")
    st.markdown(explanation_text(shap_values, inquiry))
    if prediction["version_modelo"] == load_metadata()["model_version"]:
        frame = waterfall_frame(shap_values, base_value(), inquiry)
        show_chart(waterfall_chart(frame), width="stretch")
        st.caption("Cada barra muestra cuántos puntos porcentuales (pp) suma o resta esa característica, partiendo "
                   "del promedio del histórico hasta llegar al puntaje de esta consulta, de la de mayor a menor "
                   "influencia. Refleja los supuestos de los datos simulados: es un apoyo al criterio profesional, "
                   "no un criterio jurídico.")
    else:
        st.caption("La predicción se calculó con otra versión del modelo; se muestra solo el detalle técnico.")
    with st.expander("Detalle técnico (valores SHAP en log-odds)", icon=":material/data_object:"):
        st.dataframe(shap_table(shap_values, inquiry), hide_index=True, width="stretch",
                     column_config={"Aporte SHAP (log-odds)": st.column_config.NumberColumn(format="%+.3f")})

# 3. Datos de la consulta
with card("facts"):
    card_title("Datos de la consulta")
    for row in (INQUIRY_FIELDS[:3], INQUIRY_FIELDS[3:]):
        for col, (label, column, icon) in zip(st.columns(3), row):
            col.caption(f"{icon} {label}")
            col.markdown(f"**{display_value(column, inquiry)}**")
    if inquiry["observaciones"]:
        st.caption(f":material/sticky_note_2: {inquiry['observaciones']}")


# 4. Decisión del socio (HU-006). Fragmento: elegir socio/decisión/motivo no recalcula toda la página.
@st.fragment
def decision_panel():
    with card("decision"):
        card_title("Decisión de admisión")
        if inquiry["resultado_admision"]:
            decided_on = f" el {inquiry['fecha_decision']:%d/%m/%Y a las %H:%M}" if inquiry["fecha_decision"] else ""
            reason = f" Motivo: **{inquiry['motivo_rechazo']}**." if inquiry["motivo_rechazo"] else ""
            (st.success if inquiry["resultado_admision"] == ACCEPTED else st.error)(
                f"Consulta **{inquiry['resultado_admision'].lower()}**{decided_on}.{reason}", icon=status_icon)
            return

        partner_ids = load_partners()
        c1, c2 = st.columns(2)
        partner = c1.segmented_control("Socio que registra la decisión", list(partner_ids),
                                       key=f"partner_{inquiry_id}")
        decision = c2.segmented_control("Decisión", list(DECISION_LABELS), format_func=DECISION_LABELS.get,
                                        key=f"decision_{inquiry_id}")
        reason = None
        if decision == "Rechazar":
            reason = st.selectbox("Motivo de rechazo *", DOMAINS["motivo_rechazo"], index=None,
                                  placeholder="Seleccionar motivo...", key=f"reason_{inquiry_id}")  # HU-006 AC2

        ready = partner is not None and decision is not None and (decision == "Admitir" or reason is not None)
        if ready:
            summary = "admitida" if decision == "Admitir" else f"rechazada por «{reason}»"
            st.caption(f"Se registrará la consulta como **{summary}**, a nombre de {partner}.")
        elif decision == "Rechazar":
            st.caption("Para rechazar una consulta es obligatorio seleccionar un motivo de rechazo.")
        else:
            st.caption("Elegí el socio y la decisión para habilitar la confirmación.")

        if st.button("Confirmar decisión", type="primary", disabled=not ready, icon=":material/gavel:"):
            result = ACCEPTED if decision == "Admitir" else REJECTED
            db.record_decision(engine, inquiry_id, result, reason, partner_ids[partner])
            invalidate_lists()
            st.toast(f"{inquiry_id}: {result}.", icon=":material/task_alt:")
            st.rerun(scope="app")  # la consulta sale de pendientes pero sigue seleccionada, con la decisión registrada


decision_panel()
