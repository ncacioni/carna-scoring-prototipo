"""Pantalla 3 — Cola de pendientes e historial de consultas (HU-005, HU-007)."""

import altair as alt
import pandas as pd
import streamlit as st

from src.constants import ACCEPTED, CLAIM_TYPES_BY_AREA, DOMAINS, REJECTED
from src.db import today_local
from src.ui import (NEGATIVE_COLOR, NEUTRAL_COLOR, POSITIVE_COLOR, SCORE_BANDS, card, card_title, kpi_card,
                    load_history, load_pending, open_inquiry, page_header, score_band, show_chart)

RESULT_SCALE = alt.Scale(domain=[ACCEPTED, REJECTED], range=[POSITIVE_COLOR, NEGATIVE_COLOR])
QUEUE_SCROLL_AFTER = 6

page_header("Listado e historial", "Priorizá las consultas pendientes y analizá los patrones de las decisiones "
            "ya tomadas.", "list_alt")
pending_tab, history_tab = st.tabs([":material/pending_actions: Pendientes", ":material/history: Historial"])

# ---------------------------------------------------------------- HU-005: cola priorizada
with pending_tab:
    pending = load_pending().copy()
    if pending.empty:
        st.info("No hay consultas pendientes de evaluación. Las nuevas consultas aparecen acá automáticamente.",
                icon=":material/inbox:")
    else:
        pending["banda"] = pending["puntaje_admision"].map(lambda s: score_band(s)[0] if pd.notna(s) else "Sin puntaje")
        waiting_days = (pd.Timestamp(today_local()) - pd.to_datetime(pending["fecha_consulta"])).dt.days

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi_card("Pendientes", str(len(pending)))
        with k2:
            kpi_card("Afinidad alta", str(int((pending["banda"] == "Alta").sum())),
                     help=f"Puntaje de {SCORE_BANDS[0][0]}% o más.")
        with k3:
            kpi_card("Puntaje promedio", f"{pending['puntaje_admision'].mean():.0f}%")
        with k4:
            kpi_card("Espera máxima", f"{int(waiting_days.max())} días", help="Días desde la fecha de consulta.")

        band_filter = st.segmented_control("Afinidad", ["Alta", "Media", "Baja"], selection_mode="multi",
                                           key="band_filter",
                                           help="Alta: 70% o más · Media: 40% a 69% · Baja: menos de 40%.")
        queue = pending[pending["banda"].isin(band_filter)] if band_filter else pending
        st.caption(f"{len(queue)} consultas ordenadas de mayor a menor puntaje de admisión "
                   "(estimación de prueba de concepto sobre datos simulados).")

        box = st.container(height=560, border=False) if len(queue) > QUEUE_SCROLL_AFTER else st.container()
        with box:
            for rank, row in enumerate(queue.itertuples(), start=1):
                score = row.puntaje_admision
                label, color, _ = score_band(score) if pd.notna(score) else ("Sin puntaje", "gray", None)
                with card(f"queue_{row.id_consulta}"):
                    c_rank, c_info, c_score, c_band, c_action = st.columns(
                        [0.35, 2.4, 1.8, 1.15, 0.8], vertical_alignment="center")
                    c_rank.html(f'<div class="cm-rank">{rank}</div>')
                    c_info.markdown(f"**{row.id_consulta}** · {row.area_practica}  \n"
                                    f":gray[{row.tipo_reclamo} · {row.fecha_consulta:%d/%m/%Y}]")
                    if pd.notna(score):
                        c_score.progress(score / 100, text=f"Puntaje **{score:.0f}%**")
                    else:
                        c_score.caption("Se calcula al abrir la consulta")
                    with c_band:
                        st.badge(f"Afinidad {label.lower()}" if pd.notna(score) else label, color=color)
                    if c_action.button("Abrir", key=f"open_{row.id_consulta}", icon=":material/arrow_forward:",
                                       width="stretch"):
                        open_inquiry(row.id_consulta)


# ---------------------------------------------------------------- HU-007: historial analítico
# Fragmento: cambiar un filtro recalcula solo el historial, no la cola de pendientes.
@st.fragment
def history_view():
    history = load_history()

    c1, c2, c3 = st.columns(3)
    areas = c1.multiselect("Área de práctica", DOMAINS["area_practica"], placeholder="Todas")
    type_options = [t for a in (areas or DOMAINS["area_practica"]) for t in CLAIM_TYPES_BY_AREA[a]]
    types = c2.multiselect("Tipo de reclamo", type_options, placeholder="Todos",
                           help="La lista se limita a las áreas seleccionadas.")
    results = c3.multiselect("Resultado de admisión", [ACCEPTED, REJECTED], placeholder="Todos")

    filtered = history
    if areas:
        filtered = filtered[filtered["area_practica"].isin(areas)]
    if types:
        filtered = filtered[filtered["tipo_reclamo"].isin(types)]
    if results:
        filtered = filtered[filtered["resultado_admision"].isin(results)]

    total = len(filtered)
    accepted = int((filtered["resultado_admision"] == ACCEPTED).sum())
    rejected = total - accepted
    reasons = filtered["motivo_rechazo"].value_counts()

    # AC3: proporción de admitidas / rechazadas sobre el subconjunto filtrado
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Consultas", f"{total:,}".replace(",", "."),
                 caption="con decisión registrada" if total == len(history) else f"de {len(history):,} en total".replace(",", "."))
    with k2:
        kpi_card("Admitidas", f"{accepted / total:.0%}" if total else "—", caption=f"{accepted} consultas")
    with k3:
        kpi_card("Rechazadas", f"{rejected / total:.0%}" if total else "—", caption=f"{rejected} consultas")
    with k4:
        kpi_card("Motivo de rechazo principal", f"{reasons.iloc[0] / rejected:.0%}" if not reasons.empty else "—",
                 caption=f"{reasons.index[0]} · {reasons.iloc[0]} consultas" if not reasons.empty else None,
                 help="Participación del motivo más frecuente sobre el total de rechazos del filtro.")

    if not total:
        st.info("Ninguna consulta cumple los filtros seleccionados.", icon=":material/filter_alt_off:")
        return

    left, right = st.columns([1.15, 1], gap="large")
    with left, card("by_area"):
        card_title("Admisión por área de práctica")
        by_area = (filtered.groupby(["area_practica", "resultado_admision"]).size().rename("n").reset_index())
        by_area["pct"] = by_area["n"] / by_area.groupby("area_practica")["n"].transform("sum")
        area_order = (filtered.assign(ok=filtered["resultado_admision"] == ACCEPTED)
                      .groupby("area_practica")["ok"].mean().sort_values(ascending=False).index.tolist())
        base = alt.Chart(by_area).encode(
            y=alt.Y("area_practica:N", sort=area_order, title=None, axis=alt.Axis(labelFontSize=12)),
            x=alt.X("n:Q", stack="normalize", title=None, axis=alt.Axis(format="%", grid=False)),
        )
        bars = base.mark_bar(height=22, stroke="white", strokeWidth=2).encode(
            color=alt.Color("resultado_admision:N", title=None, scale=RESULT_SCALE, legend=alt.Legend(orient="top")),
            order=alt.Order("resultado_admision:N", sort="ascending"),
            tooltip=[alt.Tooltip("area_practica:N", title="Área"), alt.Tooltip("resultado_admision:N", title="Resultado"),
                     alt.Tooltip("n:Q", title="Consultas"), alt.Tooltip("pct:Q", title="Proporción", format=".0%")],
        )
        labels = (alt.Chart(by_area[by_area["resultado_admision"] == ACCEPTED])
                  .mark_text(align="left", dx=6, color="white", fontWeight="bold")
                  .encode(y=alt.Y("area_practica:N", sort=area_order), x=alt.value(0),
                          text=alt.Text("pct:Q", format=".0%")))
        show_chart((bars + labels).properties(height=alt.Step(40)), width="stretch")

    with right, card("reasons"):
        card_title("Motivos de rechazo")
        if reasons.empty:
            st.caption("No hay consultas rechazadas en el filtro.")
        else:
            reasons_df = reasons.rename_axis("motivo").reset_index(name="n")
            reasons_df["pct"] = reasons_df["n"] / rejected
            base = alt.Chart(reasons_df).encode(
                y=alt.Y("motivo:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
                x=alt.X("n:Q", title=None, axis=alt.Axis(grid=False, labels=False, ticks=False, domain=False)),
            )
            show_chart(
                (base.mark_bar(color=NEGATIVE_COLOR, cornerRadiusEnd=4, height=16).encode(
                    tooltip=[alt.Tooltip("motivo:N", title="Motivo"), alt.Tooltip("n:Q", title="Consultas"),
                             alt.Tooltip("pct:Q", title="% de rechazos", format=".0%")])
                 + base.mark_text(align="left", dx=5, fontSize=12).encode(text="n:Q"))
                .properties(height=alt.Step(26)),
                width="stretch",
            )

    with card("monthly"):
        card_title("Evolución mensual")
        monthly = (filtered.assign(mes=filtered["fecha_consulta"].dt.to_period("M").dt.to_timestamp())
                   .groupby(["mes", "resultado_admision"]).size().rename("n").reset_index())
        totals = monthly.groupby("mes")["n"].sum()
        rate = (monthly[monthly["resultado_admision"] == ACCEPTED].set_index("mes")["n"]
                .reindex(totals.index, fill_value=0) / totals).rename("tasa").reset_index()
        rate["consultas"] = totals.values
        x_month = alt.X("yearmonth(mes):T", title=None, axis=alt.Axis(format="%b %y", labelAngle=0, grid=False))
        volume = alt.Chart(monthly).mark_bar(stroke="white", strokeWidth=1).encode(
            x=x_month,
            y=alt.Y("n:Q", title="Consultas"),
            color=alt.Color("resultado_admision:N", title=None, scale=RESULT_SCALE, legend=alt.Legend(orient="top")),
            order=alt.Order("resultado_admision:N", sort="ascending"),
            tooltip=[alt.Tooltip("yearmonth(mes):T", title="Mes", format="%B %Y"),
                     alt.Tooltip("resultado_admision:N", title="Resultado"), alt.Tooltip("n:Q", title="Consultas")],
        ).properties(height=200)
        overall = accepted / total
        rate_line = alt.Chart(rate).mark_line(color=POSITIVE_COLOR, strokeWidth=2, point=alt.OverlayMarkDef(size=40)).encode(
            x=x_month,
            y=alt.Y("tasa:Q", title="% admitidas", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
            tooltip=[alt.Tooltip("yearmonth(mes):T", title="Mes", format="%B %Y"),
                     alt.Tooltip("tasa:Q", title="Tasa de admisión", format=".0%"),
                     alt.Tooltip("consultas:Q", title="Consultas")],
        )
        avg_rule = alt.Chart(pd.DataFrame({"y": [overall]})).mark_rule(strokeDash=[4, 4], color=NEUTRAL_COLOR).encode(y="y:Q")
        # dos gráficos apilados con el mismo eje temporal (no doble eje), cada uno a todo el ancho de la tarjeta
        show_chart(volume, width="stretch")
        show_chart((rate_line + avg_rule).properties(height=130), width="stretch")
        st.caption(f"Línea punteada: tasa de admisión del período filtrado ({overall:.0%}).")

    with st.expander(f"Ver las {total:,} consultas del filtro".replace(",", "."), icon=":material/table_rows:"):
        st.dataframe(
            filtered, hide_index=True, width="stretch",
            column_order=["id_consulta", "fecha_consulta", "area_practica", "tipo_reclamo", "resultado_admision",
                          "motivo_rechazo", "fecha_decision", "puntaje_admision"],
            column_config={
                "id_consulta": "ID",
                "fecha_consulta": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                "area_practica": "Área de práctica",
                "tipo_reclamo": "Tipo de reclamo",
                "resultado_admision": "Resultado",
                "motivo_rechazo": "Motivo de rechazo",
                "fecha_decision": st.column_config.DatetimeColumn("Fecha de decisión", format="DD/MM/YYYY HH:mm",
                                                                  help="Vacía en el histórico simulado importado."),
                "puntaje_admision": st.column_config.NumberColumn("Puntaje", format="%.0f%%",
                                                                  help="Solo para consultas cargadas en el prototipo."),
            },
        )
        st.download_button("Descargar CSV", filtered.to_csv(index=False).encode("utf-8-sig"),
                           file_name="historial_consultas.csv", mime="text/csv", icon=":material/download:")


with history_tab:
    history_view()
