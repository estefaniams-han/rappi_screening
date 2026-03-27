import streamlit as st
import plotly.express as px
import pandas as pd

from data_loader import load_data
from bot.agent import RappiAgent

st.set_page_config(
    page_title="Rappi Intelligence",
    page_icon="🛵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
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

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0f1117; }
::-webkit-scrollbar-thumb { background: #2d2f3e; border-radius: 4px; }

/* Layout */
.block-container { padding-top: 1.75rem !important; max-width: 1100px !important; }
footer, #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Datos y agente
# ---------------------------------------------------------------------------

@st.cache_resource
def get_data():
    return load_data()

@st.cache_resource
def get_agent(_metrics_df, _orders_df):
    return RappiAgent(_metrics_df, _orders_df)

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
    st.session_state.agent = get_agent(metrics_df, orders_df)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ---------------------------------------------------------------------------
# Gráficas
# ---------------------------------------------------------------------------

def render_chart(tool_result: dict | None):
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
        st.plotly_chart(fig, use_container_width=True)

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
            st.plotly_chart(fig, use_container_width=True)

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
        st.plotly_chart(fig, use_container_width=True)

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
            st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

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

for msg in st.session_state.messages:
    avatar = "🛵" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg.get("chart_data"):
            render_chart(msg["chart_data"])

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
        render_chart(tool_result)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "chart_data": tool_result,
    })
    st.rerun()
