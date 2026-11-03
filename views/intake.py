"""Pantalla 1 — Formulario de Intake (HU-001, HU-002)."""

import streamlit as st

from src import db
from src.constants import CLAIM_TYPES_BY_AREA, DOMAINS, REQUIRED_FIELDS
from src.ui import (cached_admission_rates, card, card_title, checklist, format_ars, get_engine, invalidate_lists,
                    open_inquiry, page_header, section_title)

FIELD_LABELS = {
    "fecha_consulta": "Fecha",
    "canal_ingreso": "Canal de ingreso",
    "area_practica": "Área de práctica",
    "tipo_reclamo": "Tipo de reclamo",
    "jurisdiccion": "Jurisdicción",
    "monto_estimado": "Monto estimado",
    "estado_prescripcion": "Plazo de prescripción",
    "documentacion_aportada": "Documentación aportada",
}
RECOMMENDED_FIELDS = ["jurisdiccion", "monto_estimado"]
HINT_FIELDS = ["area_practica", "estado_prescripcion", "documentacion_aportada", "jurisdiccion"]
PLACEHOLDER = "Seleccionar..."
SHORT_LABELS = {v: v for v in DOMAINS["jurisdiccion"]} | {"Provincia de Buenos Aires": "Prov. de Bs. As."}

# contador para poder vaciar el formulario después de un envío exitoso
form_id = st.session_state.setdefault("intake_form_id", 0)


def key(name: str) -> str:
    return f"{name}_{form_id}"


def is_filled(value) -> bool:
    return value is not None and value != ""


page_header("Nueva consulta", "Formulario de intake estandarizado: reemplaza el registro disperso actual y "
            "ordena desde el primer contacto la información que necesita el modelo.", "edit_note")

form_col, summary_col = st.columns([2.1, 1], gap="large")
data: dict = {}

with form_col:
    with card("sec_ingreso"):
        section_title(1, "Ingreso de la consulta", "¿Cuándo y por dónde llegó?")
        c1, c2 = st.columns([1, 2])
        data["fecha_consulta"] = c1.date_input("Fecha de consulta *", value=db.today_local(),
                                               max_value=db.today_local(), format="DD/MM/YYYY", key=key("fecha"))
        data["canal_ingreso"] = c2.segmented_control("Canal de ingreso *", DOMAINS["canal_ingreso"],
                                                     key=key("canal"), width="stretch")

    with card("sec_caso"):
        section_title(2, "El caso", "Elegí primero el área: la lista de tipos de reclamo se ajusta a ella. "
                      "Documentación y prescripción son obligatorias porque son las variables de mayor peso del modelo.")
        data["area_practica"] = st.segmented_control("Área de práctica *", DOMAINS["area_practica"],
                                                     key=key("area"), width="stretch")
        claim_types = CLAIM_TYPES_BY_AREA.get(data["area_practica"], [])
        data["tipo_reclamo"] = st.selectbox(
            "Tipo de reclamo *", claim_types, index=None, key=key(f"tipo_{data['area_practica']}"),
            placeholder=PLACEHOLDER if claim_types else "Elegí primero el área de práctica",
            disabled=not claim_types)
        c1, c2 = st.columns(2)
        data["documentacion_aportada"] = c1.segmented_control(
            "Documentación aportada *", ["Completa", "Parcial", "Ninguna"], key=key("documentacion"), width="stretch")
        data["estado_prescripcion"] = c2.selectbox("Estado del plazo de prescripción *",
                                                   DOMAINS["estado_prescripcion"], index=None,
                                                   placeholder=PLACEHOLDER, key=key("prescripcion"))

    with card("sec_complementaria"):
        section_title(3, "Información complementaria",
                      "Campos recomendados: no son obligatorios, pero cuanto más completos, más informativo el puntaje.")
        c1, c2 = st.columns(2)
        data["jurisdiccion"] = c1.segmented_control("Jurisdicción", DOMAINS["jurisdiccion"], key=key("jurisdiccion"),
                                                    format_func=SHORT_LABELS.get, width="stretch")
        data["monto_estimado"] = c2.number_input("Monto estimado (ARS)", min_value=0.0, value=None,
                                                 step=100_000.0, format="%.0f", placeholder="Ej.: 2500000",
                                                 key=key("monto"))

    with card("sec_observaciones"):
        section_title(4, "Observaciones", "Opcional. Texto libre: no se usa para calcular el puntaje.")
        data["observaciones"] = st.text_area("Observaciones", key=key("observaciones"), height=90,
                                             label_visibility="collapsed",
                                             placeholder="Notas de quien registra la consulta...")

missing = [FIELD_LABELS[f] for f in REQUIRED_FIELDS if not is_filled(data[f])]
required_done = len(REQUIRED_FIELDS) - len(missing)
recommended_done = sum(is_filled(data[f]) for f in RECOMMENDED_FIELDS)

with summary_col:
    with card("summary"):
        card_title("Resumen de la consulta")
        st.progress(required_done / len(REQUIRED_FIELDS),
                    text=f"Obligatorios: **{required_done} de {len(REQUIRED_FIELDS)}**")
        st.progress(recommended_done / len(RECOMMENDED_FIELDS),
                    text=f"Recomendados: **{recommended_done} de {len(RECOMMENDED_FIELDS)}**")

        rows = []
        for field in REQUIRED_FIELDS + RECOMMENDED_FIELDS:
            value = data[field]
            if field == "fecha_consulta" and value:
                value = value.strftime("%d/%m/%Y")
            elif field == "monto_estimado" and is_filled(value):
                value = format_ars(value)
            rows.append((FIELD_LABELS[field] + (" *" if field in REQUIRED_FIELDS else ""),
                         value if is_filled(value) else None))
        checklist(rows)

        # HU-001 AC1/AC2: el botón solo se habilita con los obligatorios completos
        if missing:
            st.info("Falta completar: **" + "**, **".join(missing) + "**.", icon=":material/info:")
        submitted = st.button("Calcular puntaje", type="primary", disabled=bool(missing),
                              icon=":material/calculate:", width="stretch")

    # Señales del histórico simulado: contexto para quien carga, no reemplazan al puntaje
    signals = []
    for field in HINT_FIELDS:
        value = data[field]
        if not is_filled(value):
            continue
        rates = cached_admission_rates(field)
        if value in rates.index:
            signals.append((FIELD_LABELS[field], value, rates.loc[value, "rate"], int(rates.loc[value, "n"])))
    if signals:
        with card("signals"):
            card_title("Señales del histórico")
            st.caption("Tasa de admisión de consultas similares en el histórico **simulado**. "
                       "Es contexto, no el puntaje del modelo.")
            for label, value, rate, n in signals:
                st.progress(rate, text=f"{label} = *{value}* → **{rate:.0%}** admitidas (n={n})")
            if any(rate == 0 for *_, rate, _ in signals):
                st.warning("En el histórico simulado, las consultas con esta característica fueron rechazadas "
                           "en todos los casos (fuera del área de práctica o plazo vencido).",
                           icon=":material/block:")

if submitted:
    if missing:  # defensa adicional: nunca se persiste una consulta incompleta
        st.error("Completá los campos obligatorios antes de continuar.")
        st.stop()
    data["observaciones"] = data["observaciones"].strip() or None
    from src.prediction import predict  # import diferido: xgboost/shap solo cuando hace falta

    engine = get_engine()
    with st.spinner("Registrando la consulta y calculando el puntaje..."):
        inquiry_id = db.insert_inquiry(engine, data)                       # HU-001 AC3 / HU-002
        score, shap_values, model_version = predict(db.get_predictors(engine, inquiry_id))
        db.insert_prediction(engine, inquiry_id, score, shap_values, model_version)  # HU-003 AC2
    invalidate_lists()
    st.session_state["intake_form_id"] = form_id + 1
    open_inquiry(inquiry_id)
