import io
from datetime import date
from fpdf import FPDF


# ---------------------------------------------------------------------------
# PDF base con header/footer
# ---------------------------------------------------------------------------

class _RappiPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(255, 107, 53)   # #FF6B35
        self.cell(0, 10, "Rappi Intelligence", align="L")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, date.today().strftime("%d/%m/%Y"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(45, 47, 62)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _safe(text: str) -> str:
    """Elimina caracteres fuera del rango latin-1 para Helvetica."""
    return text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2019", "'").encode("latin-1", "replace").decode("latin-1")


def _section_title(pdf: _RappiPDF, title: str):
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(255, 107, 53)
    pdf.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(255, 107, 53)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_text_color(30, 30, 30)


def _table(pdf: _RappiPDF, headers: list[str], rows: list[list], col_widths: list[float] = None):
    """Dibuja una tabla simple con headers y filas."""
    n = len(headers)
    if col_widths is None:
        col_widths = [190 / n] * n

    # Header
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(255, 107, 53)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(headers, col_widths):
        pdf.cell(w, 7, _safe(str(h)), border=0, fill=True)
    pdf.ln()

    # Rows
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 30, 30)
    for i, row in enumerate(rows):
        pdf.set_fill_color(245, 245, 245) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        for val, w in zip(row, col_widths):
            pdf.cell(w, 6, _safe(str(val)[:40]), border=0, fill=True)
        pdf.ln()
    pdf.ln(4)


def _markdown_body(pdf: _RappiPDF, text: str):
    """Renderiza texto markdown (bold, bullets) en el PDF."""
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    w = pdf.epw
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue
        pdf.set_x(pdf.l_margin)
        # Líneas que son solo un header bold: **Título** → naranja
        if stripped.startswith("**") and stripped.endswith("**") and stripped.count("**") == 2:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(255, 107, 53)
            pdf.multi_cell(w, 6, _safe(stripped.replace("**", "")))
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
        # Bullets — markdown=True renderiza **bold** inline
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(w - 4, 5, _safe("- " + stripped[2:]), markdown=True)
        # Numerados
        elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] == ".":
            pdf.multi_cell(w, 5, _safe(stripped), markdown=True)
        # Texto normal (puede tener **bold** inline)
        else:
            pdf.multi_cell(w, 5, _safe(stripped), markdown=True)
    pdf.ln(2)


# ---------------------------------------------------------------------------
# Export público: Insights PDF
# ---------------------------------------------------------------------------

def _make_pdf() -> _RappiPDF:
    """Crea e inicializa un PDF con los márgenes y página base."""
    pdf = _RappiPDF()
    pdf.set_margins(10, 15, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    return pdf


def insights_to_pdf(insights: dict, report_text: str) -> bytes:
    """
    Genera un PDF completo con el reporte ejecutivo y las tablas de insights.

    Returns:
        bytes del PDF listo para st.download_button
    """
    pdf = _make_pdf()

    # Título
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 12, "Reporte Ejecutivo Semanal", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Reporte LLM (el propio markdown ya incluye los títulos de sección)
    if report_text:
        _markdown_body(pdf, report_text)
        pdf.ln(4)

    # Anomalías
    anomalies = insights.get("anomalies", [])
    if anomalies:
        _section_title(pdf, f"Anomalías ({len(anomalies)} detectadas)")
        headers = ["País", "Ciudad", "Zona", "Métrica", "Anterior %", "Actual %", "Cambio %", "Estado"]
        rows = [
            [
                a["country"], a["city"], a["zone"][:25], a["metric"][:30],
                f"{a['value_prev']:.1f}", f"{a['value_curr']:.1f}",
                f"{a['change_pct']:+.1f}",
                "Deterioro" if a["is_deterioration"] else "Mejora",
            ]
            for a in anomalies[:20]
        ]
        _table(pdf, headers, rows, [22, 22, 30, 38, 18, 18, 20, 22])

    # Tendencias
    trends = insights.get("worrying_trends", [])
    if trends:
        _section_title(pdf, f"Tendencias preocupantes ({len(trends)} detectadas)")
        headers = ["País", "Ciudad", "Zona", "Métrica", "Inicio %", "Fin %", "Cambio %"]
        rows = [
            [
                t["country"], t["city"], t["zone"][:25], t["metric"][:32],
                f"{t['value_start']:.1f}", f"{t['value_end']:.1f}",
                f"{t['total_change_pct']:+.1f}",
            ]
            for t in trends[:20]
        ]
        _table(pdf, headers, rows, [22, 22, 30, 40, 20, 20, 26])

    # Oportunidades
    opportunities = insights.get("opportunities", [])
    if opportunities:
        _section_title(pdf, f"Oportunidades de alto impacto ({len(opportunities)} zonas)")
        rows = []
        for o in opportunities:
            for m in o["lagging_metrics"]:
                rows.append([
                    o["country"], o["zone"][:25], f"{o['orders']:,}",
                    m["metric"][:30], f"{m['value']:.1f}", f"{m['global_avg']:.1f}", f"{m['gap_pct']:.1f}%",
                ])
        headers = ["País", "Zona", "Órdenes", "Métrica", "Valor %", "Avg global %", "Gap"]
        _table(pdf, headers, rows, [20, 30, 22, 40, 18, 28, 22])

    # Correlaciones
    correlations = insights.get("correlations", [])
    if correlations:
        _section_title(pdf, "Correlaciones entre métricas")
        headers = ["Métrica A", "Métrica B", "Correlación", "Dirección", "Fuerza"]
        rows = [
            [c["metric_a"][:35], c["metric_b"][:35], f"{c['correlation']:.3f}", c["direction"], c["strength"]]
            for c in correlations
        ]
        _table(pdf, headers, rows, [50, 50, 25, 30, 25])

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Export público: resultado de chatbot PDF
# ---------------------------------------------------------------------------

def chat_result_to_pdf(tool_result: dict, query: str = "") -> bytes:
    """
    Genera un PDF con el resultado de una consulta del chatbot.

    Returns:
        bytes del PDF listo para st.download_button
    """
    pdf = _make_pdf()

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 10, "Resultado de consulta", new_x="LMARGIN", new_y="NEXT")

    if query:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 6, _safe(f"Consulta: {query}"))
        pdf.ln(3)

    metric = tool_result.get("metric", "")
    week = tool_result.get("week", "")
    if metric:
        _section_title(pdf, f"{metric} — {week}" if week else metric)

    data = tool_result.get("data") or tool_result.get("top_growing_zones", [])
    if not data:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 8, "Sin datos para exportar.")
        return bytes(pdf.output())

    # Detecta tipo de resultado y construye tabla
    if isinstance(data, list) and data:
        headers = list(data[0].keys())
        rows = [[str(row.get(h, ""))[:40] for h in headers] for row in data]
        col_w = 190 / len(headers)
        _table(pdf, headers, rows, [col_w] * len(headers))

    return bytes(pdf.output())
