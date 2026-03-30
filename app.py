import streamlit as st
import plotly.express as px
import pandas as pd
import io

from data_loader import load_data
from bot.agent import RappiAgent
from insights.analyzer import run_all
from insights.reporter import generate_report
from insights.pdf_export import insights_to_pdf, chat_result_to_pdf

_CSS = """
<style>
/* === DARK MODE === */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main, .stApp {
    background-color: #0f1117 !important;
    color: #e5e7eb !important;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #1a1d27 !important;
    border-right: 1px solid #2d2f3e !important;
}
[data-testid="stSidebar"] > div { padding: 0rem 1rem 1.4rem !important; }
[data-testid="stSidebarContent"] { padding-top: 0 !important; }
[data-testid="stSidebar"] .element-container { margin-top: 0 !important; }

/* Stats */
.stat-row { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
.stat-box {
    flex: 1;
    background: #12151f;
    border: 1px solid #2a2d3e;
    border-radius: 10px;
    padding: 0.75rem;
    text-align: center;
}
.stat-box .val { font-size: 1.4rem; font-weight: 700; color: #FF6B35; line-height: 1; }
.stat-box .lbl { font-size: 0.72rem; color: #6b7280; margin-top: 3px; }

/* Section labels */
.section-label {
    font-size: 0.68rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 1.3rem 0 0.45rem 0;
}

/* Botones de sugerencias */
[data-testid="stButton"] > button {
    background: #12151f !important;
    border: 1px solid #2a2d3e !important;
    border-radius: 8px !important;
    color: #d1d5db !important;
    font-size: 0.81rem !important;
    padding: 0.5rem 0.75rem !important;
    text-align: left !important;
    white-space: normal !important;
    height: auto !important;
    line-height: 1.45 !important;
    transition: all 0.15s !important;
    width: 100% !important;
}
[data-testid="stButton"] > button:hover {
    border-color: #FF6B35 !important;
    color: #FF6B35 !important;
    background: #1a1208 !important;
}

/* Header */
/* Sidebar brand */
.brand-card {
    background: linear-gradient(180deg, #151827 0%, #121522 100%);
    border: 1px solid #23263a;
    border-radius: 12px;
    padding: 0.9rem 0.85rem;
    display: flex;
    align-items: center;
    gap: 0.7rem;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02);
    margin-top: 0;
}
.brand-badge {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    display: grid;
    place-items: center;
    background: #1c2032;
    border: 1px solid #2b2f45;
    font-size: 1.05rem;
}
.brand-title {
    font-weight: 700;
    font-size: 1.02rem;
    color: #f9fafb;
    letter-spacing: -0.01em;
    line-height: 1.1;
}
.brand-subtitle {
    font-size: 0.75rem;
    color: #8b93a7;
    margin-top: 3px;
}

/* Chat messages — más contraste */
[data-testid="stChatMessageContent"] {
    background-color: #161926 !important;
    border: 1px solid #252840 !important;
    border-radius: 12px !important;
    color: #e5e7eb !important;
    padding: 1rem 1.1rem !important;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}
[data-testid="stChatMessageContent"] p,
[data-testid="stChatMessageContent"] li {
    font-size: 0.91rem !important;
    color: #d1d5db !important;
    line-height: 1.6 !important;
}
/* Evita texto pegado al borde y compacta párrafos */
[data-testid="stChatMessageContent"] p { margin: 0 0 0.6rem 0 !important; }
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0 !important; }
[data-testid="stChatMessageContent"] blockquote {
    margin: 0.75rem 0 0 0 !important;
    padding: 0.6rem 0.8rem !important;
    background: #111420 !important;
    border-left: 3px solid #FF6B35 !important;
    border-radius: 8px !important;
    color: #cbd5e1 !important;
}
[data-testid="stChatMessageContent"] blockquote p,
[data-testid="stChatMessageContent"] blockquote li {
    color: #cbd5e1 !important;
    font-size: 0.88rem !important;
}

/* Chat input */
[data-testid="stChatInput"] {
    background-color: #1a1d27 !important;
    border-color: #2d2f3e !important;
    max-width: 1100px !important;
    margin: 0 auto !important;
}
[data-testid="stChatInput"] textarea {
    background-color: #1a1d27 !important;
    color: #e5e7eb !important;
    font-size: 0.9rem !important;
}

/* Spinner */
[data-testid="stSpinner"] { color: #FF6B35 !important; }

/* Download buttons */
[data-testid="stDownloadButton"] > button {
    background: #12151f !important;
    border: 1px solid #2a2d3e !important;
    border-radius: 8px !important;
    color: #d1d5db !important;
    font-size: 0.78rem !important;
    padding: 0.3rem 0.6rem !important;
    transition: all 0.15s !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #FF6B35 !important;
    color: #FF6B35 !important;
    background: #1a1208 !important;
}

/* Tabs */
[data-baseweb="tab-list"] {
    gap: 0.25rem !important;
    overflow: visible !important;
}
[data-baseweb="tab"] {
    padding: 0.5rem 1.5rem !important;
    white-space: nowrap !important;
    overflow: visible !important;
    min-width: fit-content !important;
}
[data-baseweb="tab"] p, [data-baseweb="tab"] span {
    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: unset !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0f1117; }
::-webkit-scrollbar-thumb { background: #2d2f3e; border-radius: 4px; }

/* Layout */
.block-container { padding-top: 1.75rem !important; max-width: 1100px !important; }
footer, #MainMenu { visibility: hidden; }
</style>
"""

st.set_page_config(
    page_title="Rappi Intelligence",
    page_icon="🛵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Datos y agente
# ---------------------------------------------------------------------------

@st.cache_resource
def get_data():
    return load_data()

metrics_df, orders_df = get_data()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("""
    <div class="brand-card" style="margin-bottom:1.1rem;">
        <div class="brand-badge">🛵</div>
        <div>
            <div class="brand-title">Rappi Intelligence</div>
            <div class="brand-subtitle">Asistente de analítica operativa</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-box"><div class="val">{metrics_df['ZONE'].nunique()}</div><div class="lbl">Zonas</div></div>
        <div class="stat-box"><div class="val">{metrics_df['COUNTRY'].nunique()}</div><div class="lbl">Países</div></div>
        <div class="stat-box"><div class="val">13</div><div class="lbl">Métricas</div></div>
    </div>
    """, unsafe_allow_html=True)

    SUGGESTED = {
        "Filtrado": [
            "Top 5 zonas con mayor Lead Penetration",
            "5 zonas con menor Perfect Orders",
        ],
        "Comparación": [
            "Perfect Order: Wealthy vs Non Wealthy en México",
            "Gross Profit UE por nivel de priorización",
        ],
        "Tendencias": [
            "Evolución de Gross Profit UE en Sur de Quito, últimas 8 semanas",
            "¿Cómo cambió el Pro Adoption en San Martin de Porras?",
        ],
        "Agregación": [
            "Promedio de Lead Penetration por país",
            "Promedio de Perfect Orders por tipo de zona",
        ],
        "Multivariable": [
            "Zonas con alto Lead Penetration pero bajo Perfect Order",
            "Zonas con bajo Gross Profit UE y baja Pro Adoption",
        ],
        "Órdenes": [
            "Zonas con mayor crecimiento en órdenes en las últimas 5 semanas",
            "Crecimiento en órdenes en Colombia",
        ],
    }

    st.markdown('<div class="section-label">Sugerencias</div>', unsafe_allow_html=True)
    for category, questions in SUGGESTED.items():
        with st.expander(category, expanded=False):
            for q in questions:
                if st.button(q, key=f"q_{q}", use_container_width=True):
                    st.session_state.pending_question = q

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Limpiar conversación", use_container_width=True):
        st.session_state.messages = []
        if "agent" in st.session_state:
            st.session_state.agent.reset()
        st.rerun()

# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------

if "agent" not in st.session_state:
    st.session_state.agent = RappiAgent(metrics_df, orders_df)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ---------------------------------------------------------------------------
# Gráficas
# ---------------------------------------------------------------------------

def render_chart(tool_result: dict | None, key: str = "chart"):
    if not tool_result or "error" in tool_result or not tool_result.get("data"):
        return

    df = pd.DataFrame(tool_result["data"])
    metric = tool_result.get("metric", "")
    week = tool_result.get("week", "")
    COLORS = ["#FF6B35", "#FF9F1C", "#2EC4B6", "#3A86FF", "#8338EC",
              "#FB5607", "#FFBE0B", "#06D6A0", "#EF476F"]
    BG = "#0f1117"
    GRID = "#1f2232"

    # Top/Bottom zonas — barras horizontales
    if "type" in tool_result and "ZONE" in df.columns and "value_pct" in df.columns:
        fig = px.bar(df, x="value_pct", y="ZONE", orientation="h",
                     color="COUNTRY", title=f"{metric} — {week}",
                     labels={"value_pct": "%", "ZONE": ""},
                     color_discrete_sequence=COLORS)
        fig.update_layout(yaxis={"categoryorder": "total ascending"},
                          height=300, plot_bgcolor=BG, paper_bgcolor=BG,
                          font_family="Inter", title_font_size=13, font_color="#e5e7eb",
                          margin=dict(l=0, r=10, t=35, b=0),
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        fig.update_xaxes(showgrid=True, gridcolor=GRID)
        st.plotly_chart(fig, use_container_width=True, key=key)

    # Comparación entre grupos
    elif tool_result.get("group_by") and "avg_pct" in df.columns:
        group_col = tool_result["group_by"]
        if group_col in df.columns:
            fig = px.bar(df, x=group_col, y="avg_pct",
                         title=f"{metric} promedio — {week}",
                         labels={"avg_pct": "Promedio (%)"},
                         color=group_col, text="avg_pct",
                         color_discrete_sequence=COLORS)
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(showlegend=False, height=300,
                              plot_bgcolor=BG, paper_bgcolor=BG,
                              font_family="Inter", title_font_size=13, font_color="#e5e7eb",
                              margin=dict(l=0, r=0, t=35, b=0))
            fig.update_yaxes(showgrid=True, gridcolor=GRID)
            st.plotly_chart(fig, use_container_width=True, key=key)

    # Tendencia temporal — línea
    elif "trend" in tool_result:
        df_t = pd.DataFrame(tool_result["trend"])
        zone = tool_result.get("zone", "")
        change = tool_result.get("total_change_pct", 0)
        line_color = "#22c55e" if change >= 0 else "#ef4444"
        fig = px.line(df_t, x="week", y="value_pct", markers=True,
                      title=f"{metric} · {zone}",
                      labels={"value_pct": "%", "week": ""},
                      color_discrete_sequence=[line_color])
        fig.update_traces(line_width=2.5, marker_size=7)
        change_label = f"{'▲' if change >= 0 else '▼'} {abs(change):.1f}% total"
        fig.add_annotation(xref="paper", yref="paper", x=0.98, y=0.08,
                           text=change_label, showarrow=False,
                           font=dict(color=line_color, size=12, family="Inter"),
                           bgcolor="white", bordercolor=line_color,
                           borderwidth=1, borderpad=5, xanchor="right")
        fig.update_layout(height=300, plot_bgcolor=BG, paper_bgcolor=BG,
                          font_family="Inter", title_font_size=13, font_color="#e5e7eb",
                          margin=dict(l=0, r=0, t=35, b=0))
        fig.update_yaxes(showgrid=True, gridcolor=GRID)
        st.plotly_chart(fig, use_container_width=True, key=key)

    # Agregación
    elif "zones" in df.columns and "avg_pct" in df.columns:
        group_col = tool_result.get("group_by", "group")
        if group_col in df.columns:
            fig = px.bar(df.head(12), x="avg_pct", y=group_col, orientation="h",
                         title=f"{metric} promedio por {group_col} — {week}",
                         labels={"avg_pct": "%", group_col: ""},
                         color="avg_pct", color_continuous_scale="Oranges",
                         text="avg_pct")
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(yaxis={"categoryorder": "total ascending"},
                              coloraxis_showscale=False, height=350,
                              plot_bgcolor=BG, paper_bgcolor=BG,
                              font_family="Inter", title_font_size=13, font_color="#e5e7eb",
                              margin=dict(l=0, r=40, t=35, b=0))
            fig.update_xaxes(showgrid=True, gridcolor=GRID)
            st.plotly_chart(fig, use_container_width=True, key=key)

# ---------------------------------------------------------------------------
# Tabs: Chatbot | Insights
# ---------------------------------------------------------------------------

tab_chat, tab_insights = st.tabs(["Chatbot", "Insights automáticos"])

# ---------------------------------------------------------------------------
# Tab: Insights
# ---------------------------------------------------------------------------

with tab_insights:
    st.markdown("### Reporte ejecutivo semanal")
    st.caption("Detección automática de anomalías, tendencias, benchmarking y oportunidades.")

    if "insights_data" not in st.session_state:
        st.session_state.insights_data = None
    if "insights_report" not in st.session_state:
        st.session_state.insights_report = None

    if st.button("Generar insights", type="primary"):
        with st.spinner("Analizando datos..."):
            st.session_state.insights_data = run_all(metrics_df, orders_df)
        with st.spinner("Generando reporte con IA..."):
            st.session_state.insights_report = generate_report(st.session_state.insights_data)

    if st.session_state.insights_data:
        data = st.session_state.insights_data

        # --- Botones de exportación al inicio ---
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            if data["anomalies"]:
                pd.DataFrame(data["anomalies"]).to_excel(writer, sheet_name="Anomalías", index=False)
            if data["worrying_trends"]:
                pd.DataFrame(data["worrying_trends"]).to_excel(writer, sheet_name="Tendencias", index=False)
            if data["benchmarking"]:
                pd.DataFrame(data["benchmarking"]).to_excel(writer, sheet_name="Benchmarking", index=False)
            if data["correlations"]:
                pd.DataFrame(data["correlations"]).to_excel(writer, sheet_name="Correlaciones", index=False)
            if data["opportunities"]:
                opp_rows = []
                for o in data["opportunities"]:
                    for m in o["lagging_metrics"]:
                        unit = m.get("unit", "%")
                        row = {
                            "zone": o["zone"],
                            "country": o["country"],
                            "zone_type": o["zone_type"],
                            "orders/sem": o["orders"],
                            "metric": m["metric"],
                            "unit": unit,
                            "value": m["value"],
                            "global_avg": m["global_avg"],
                        }
                        if unit != "%" and m.get("abs_gap") is not None:
                            row["gap"] = f"{m['abs_gap']:+.4f} {unit}"
                        else:
                            row["gap"] = f"{m['gap_pct']:.1f}%"
                        opp_rows.append(row)
                pd.DataFrame(opp_rows).to_excel(writer, sheet_name="Oportunidades", index=False)
        _, exc1, exc2 = st.columns([6, 1, 1])
        with exc1:
            st.download_button("↓ Excel", data=buf.getvalue(),
                               file_name="rappi_insights.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
        with exc2:
            st.download_button("↓ PDF",
                               data=insights_to_pdf(data, st.session_state.insights_report or ""),
                               file_name="rappi_insights.pdf", mime="application/pdf",
                               use_container_width=True)
        st.divider()

    if st.session_state.insights_report:
        st.markdown(st.session_state.insights_report)
        st.divider()

    if st.session_state.insights_data:
        data = st.session_state.insights_data

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Anomalías", len(data["anomalies"]))
        col2.metric("Tendencias", len(data["worrying_trends"]))
        col3.metric("Benchmarking", len(data["benchmarking"]))
        col4.metric("Correlaciones", len(data["correlations"]))
        col5.metric("Oportunidades", len(data["opportunities"]))

        # --- Anomalías ---
        if data["anomalies"]:
            st.markdown("#### Anomalías (cambios bruscos semana a semana)")
            df_anom = pd.DataFrame(data["anomalies"])
            df_anom["estado"] = df_anom["is_deterioration"].map({True: "Deterioro", False: "Mejora"})
            def _fmt_anom_change(row):
                if row.get("unit", "%") != "%" and row.get("abs_change") is not None:
                    return f"{row['abs_change']:+.4f} {row['unit']}"
                return f"{row['change_pct']:+.1f}%"
            df_anom["cambio"] = df_anom.apply(_fmt_anom_change, axis=1)
            st.dataframe(
                df_anom[["country", "city", "zone", "metric", "unit", "value_prev", "value_curr", "cambio", "estado", "severity"]],
                use_container_width=True, hide_index=True
            )

        # --- Tendencias preocupantes ---
        if data["worrying_trends"]:
            st.markdown("#### Tendencias preocupantes (deterioro consistente 3+ semanas)")
            df_trend = pd.DataFrame(data["worrying_trends"])
            def _fmt_change(row):
                if row.get("unit", "%") != "%" and row.get("abs_change") is not None:
                    return f"{row['abs_change']:+.4f} {row['unit']}"
                return f"{row['total_change_pct']:+.1f}%"
            df_trend["cambio"] = df_trend.apply(_fmt_change, axis=1)
            st.dataframe(
                df_trend[["country", "city", "zone", "metric", "unit", "value_start", "value_end", "cambio", "weeks_declining"]],
                use_container_width=True, hide_index=True
            )

        # --- Benchmarking ---
        if data["benchmarking"]:
            st.markdown("#### Benchmarking (zonas por debajo de su grupo)")
            df_bench = pd.DataFrame(data["benchmarking"][:20])
            COLORS = ["#FF6B35", "#FF9F1C", "#2EC4B6", "#3A86FF", "#8338EC"]
            BG = "#0f1117"

            def _bench_chart(df_sub, unit_label, key):
                if df_sub.empty:
                    return
                fig = px.scatter(
                    df_sub, x="group_avg", y="zone_value",
                    color="metric", hover_data=["zone", "country", "z_score"],
                    title=f"Valor de zona vs promedio del grupo ({unit_label})",
                    labels={"zone_value": f"Valor zona ({unit_label})",
                            "group_avg": f"Promedio grupo ({unit_label})"},
                    color_discrete_sequence=COLORS,
                )
                mn, mx = df_sub["group_avg"].min(), df_sub["group_avg"].max()
                fig.add_shape(type="line", x0=mn, y0=mn, x1=mx, y1=mx,
                              line=dict(color="#4b5563", dash="dash"))
                fig.update_layout(height=350, plot_bgcolor=BG, paper_bgcolor=BG,
                                  font_color="#e5e7eb", font_family="Inter", title_font_size=13,
                                  margin=dict(l=0, r=0, t=35, b=0))
                st.plotly_chart(fig, use_container_width=True, key=key)

            _bench_chart(df_bench[df_bench["unit"] == "%"], "%", "bench_chart_pct")
            _bench_chart(df_bench[df_bench["unit"] != "%"], "USD/orden", "bench_chart_usd")

        # --- Correlaciones ---
        if data["correlations"]:
            st.markdown("#### Correlaciones entre métricas")
            df_corr = pd.DataFrame(data["correlations"])
            st.dataframe(
                df_corr[["metric_a", "metric_b", "correlation", "direction", "strength"]],
                use_container_width=True, hide_index=True
            )

        # --- Oportunidades ---
        if data["opportunities"]:
            st.markdown("#### Oportunidades de alto impacto")
            rows = []
            for o in data["opportunities"]:
                for m in o["lagging_metrics"]:
                    unit = m.get("unit", "%")
                    row = {
                        "zone": o["zone"],
                        "country": o["country"],
                        "orders/sem": o["orders"],
                        "metric": m["metric"],
                        "unit": unit,
                        "value": m["value"],
                        "global avg": m["global_avg"],
                    }
                    if unit != "%" and m.get("abs_gap") is not None:
                        row["gap"] = f"{m['abs_gap']:+.4f} {unit}"
                    else:
                        row["gap"] = f"{m['gap_pct']:.1f}%"
                    rows.append(row)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)



# ---------------------------------------------------------------------------
# Chat (inside tab)
# ---------------------------------------------------------------------------

with tab_chat:
    if not st.session_state.messages:
        with st.chat_message("assistant", avatar="🛵"):
            st.markdown(
                "Hola 👋 Soy el asistente de operaciones de Rappi. "
                "Puedo responder preguntas sobre métricas por zona, ciudad y país.\n\n"
                "Prueba con algo como:\n"
                "- *¿Cuáles son las 5 zonas con mayor Lead Penetration esta semana?*\n"
                "- *Compara Perfect Order entre Wealthy y Non Wealthy en Colombia*\n"
                "- *¿Qué zonas crecen más en órdenes en las últimas 5 semanas?*"
            )

    for i, msg in enumerate(st.session_state.messages):
        avatar = "🛵" if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            cd = msg.get("chart_data")
            data_rows = cd.get("data") or cd.get("top_growing_zones") if cd else None
            # Botones arriba a la derecha si hay datos exportables
            if data_rows:
                query = ""
                if i > 0 and st.session_state.messages[i - 1]["role"] == "user":
                    query = st.session_state.messages[i - 1]["content"]
                df_export = pd.DataFrame(data_rows)
                _, c1, c2 = st.columns([6, 1, 1])
                with c1:
                    st.download_button(
                        "↓ CSV",
                        data=df_export.to_csv(index=False).encode("utf-8"),
                        file_name=f"rappi_resultado_{i}.csv",
                        mime="text/csv",
                        key=f"csv_{i}",
                        use_container_width=True,
                    )
                with c2:
                    st.download_button(
                        "↓ PDF",
                        data=chat_result_to_pdf(cd, query),
                        file_name=f"rappi_resultado_{i}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{i}",
                        use_container_width=True,
                    )
            st.markdown(msg["content"])
            if cd:
                render_chart(cd, key=f"chart_{i}")

    # Input — puede venir del teclado o del sidebar
    prompt = st.chat_input("Escribe tu pregunta...")

    if st.session_state.pending_question:
        prompt = st.session_state.pending_question
        st.session_state.pending_question = None

    if prompt:
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant", avatar="🛵"):
            with st.spinner(""):
                response_text, tool_result = st.session_state.agent.chat(prompt)
            st.markdown(response_text)
            render_chart(tool_result, key="chart_new")

        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text,
            "chart_data": tool_result,
        })
        st.rerun()
