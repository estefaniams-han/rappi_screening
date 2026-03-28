import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv(override=True)

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

REPORT_PROMPT = """Eres un analista de operaciones senior de Rappi. Tu tarea es generar un reporte ejecutivo
semanal basado en los hallazgos automáticos del sistema de monitoreo.

El reporte debe ser conciso, orientado a la acción y escrito en español.
Usa formato Markdown con secciones claras. Máximo 400 palabras.

Estructura:
1. **Resumen Ejecutivo** (2-3 oraciones con los hallazgos más importantes)
2. **Alertas Críticas** (anomalías y tendencias preocupantes — máx 3 bullets)
3. **Oportunidades de Alto Impacto** (zonas con mayor potencial — máx 3 bullets)
4. **Recomendaciones** (2-3 acciones concretas)

Usa los datos tal como vienen. No inventes cifras adicionales. Si no hay datos en alguna sección, omítela."""


def generate_report(insights: dict) -> str:
    """
    Genera un reporte ejecutivo en lenguaje natural a partir de los insights detectados.

    Args:
        insights: dict con keys anomalies, worrying_trends, benchmarking, correlations, opportunities

    Returns:
        Texto Markdown del reporte
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    # Prepara un resumen compacto de los insights para el LLM
    summary = _build_summary(insights)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REPORT_PROMPT},
            {"role": "user", "content": f"Aquí están los hallazgos del sistema:\n\n{summary}"},
        ],
        temperature=0.4,
    )

    text = response.choices[0].message.content or "No se pudo generar el reporte."
    return _fix_markdown_spacing(text)


def _fix_markdown_spacing(text: str) -> str:
    """Asegura línea en blanco después de cada header markdown bold."""
    import re
    # Añade salto de línea vacío después de **Título** si va seguido directo de texto
    return re.sub(r"(\*\*[^*]+\*\*)\s*\n([^\n])", r"\1\n\n\2", text)


def _build_summary(insights: dict) -> str:
    """Convierte los insights a texto compacto para el LLM."""
    parts = []

    anomalies = insights.get("anomalies", [])
    if anomalies:
        top = anomalies[:5]
        lines = [
            f"- {a['zone']} ({a['country']}): {a['metric']} cambió {a['change_pct']:+.1f}% "
            f"({'deterioro' if a['is_deterioration'] else 'mejora'}, severidad {a['severity']})"
            for a in top
        ]
        parts.append("ANOMALÍAS (cambios bruscos semana a semana):\n" + "\n".join(lines))

    trends = insights.get("worrying_trends", [])
    if trends:
        top = trends[:5]
        lines = [
            f"- {t['zone']} ({t['country']}): {t['metric']} cayó {t['total_change_pct']:.1f}% "
            f"en {t['weeks_declining']} semanas consecutivas"
            for t in top
        ]
        parts.append("TENDENCIAS PREOCUPANTES (deterioro consistente):\n" + "\n".join(lines))

    benchmarking = insights.get("benchmarking", [])
    if benchmarking:
        top = benchmarking[:5]
        lines = [
            f"- {b['zone']} ({b['country']}): {b['metric']} = {b['zone_value']:.1f}% "
            f"vs promedio del grupo {b['group_avg']:.1f}% (z={b['z_score']:.1f})"
            for b in top
        ]
        parts.append("BENCHMARKING (zonas por debajo de su grupo):\n" + "\n".join(lines))

    correlations = insights.get("correlations", [])
    if correlations:
        top = correlations[:3]
        lines = [
            f"- {c['metric_a']} ↔ {c['metric_b']}: correlación {c['correlation']:.2f} ({c['strength']})"
            for c in top
        ]
        parts.append("CORRELACIONES RELEVANTES:\n" + "\n".join(lines))

    opportunities = insights.get("opportunities", [])
    if opportunities:
        top = opportunities[:5]
        lagging_strs = []
        for o in top:
            metrics_str = ", ".join(
                f"{m['metric']} ({m['gap_pct']:.1f}% bajo promedio)"
                for m in o["lagging_metrics"]
            )
            lagging_strs.append(
                f"- {o['zone']} ({o['country']}): {o['orders']:,} órdenes/sem — métricas rezagadas: {metrics_str}"
            )
        parts.append("OPORTUNIDADES DE ALTO IMPACTO:\n" + "\n".join(lagging_strs))

    if not parts:
        return "No se detectaron hallazgos significativos esta semana."

    return "\n\n".join(parts)
