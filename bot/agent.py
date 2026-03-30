import os
import json
import unicodedata
from dotenv import load_dotenv
import groq
from groq import Groq
import pandas as pd

from bot.tools import (
    get_top_zones,
    compare_groups,
    get_zone_trend,
    aggregate_metric,
    multivariable_filter,
    get_orders_trend,
)
from bot.prompts import SYSTEM_PROMPT
from data_loader import COUNTRY_CODE_TO_NAME

load_dotenv(override=True)

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_top_zones",
            "description": (
                "Obtiene las N zonas con mayor o menor valor de una métrica operacional "
                "en una semana específica. Usar para preguntas de ranking o filtrado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric":    {"type": "string", "description": "Nombre exacto de la métrica"},
                    "n":         {"type": "string", "description": "Número de zonas a retornar (default 5)"},
                    "week":      {"type": "string", "description": "Semana: 'current', 'L1W', 'L2W', etc."},
                    "ascending": {"type": "string", "description": "true para bottom N, false para top N"},
                    "country":   {"type": "string", "description": "Código de país (AR, MX, CO, etc.)"},
                    "city":      {"type": "string", "description": "Nombre de ciudad"},
                    "zone_type": {"type": "string", "description": "'Wealthy' o 'Non Wealthy'"},
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_groups",
            "description": (
                "Compara el promedio de una métrica entre grupos: Wealthy vs Non Wealthy, "
                "o entre niveles de priorización. Usar para preguntas de comparación entre segmentos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric":   {"type": "string", "description": "Nombre de la métrica"},
                    "group_by": {"type": "string", "description": "'ZONE_TYPE' o 'ZONE_PRIORITIZATION'"},
                    "week":     {"type": "string", "description": "Semana a evaluar"},
                    "country":  {"type": "string", "description": "Código de país"},
                    "city":     {"type": "string", "description": "Nombre de ciudad"},
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_zone_trend",
            "description": (
                "Muestra la evolución semanal de una métrica para una zona específica. "
                "Usar para preguntas de tendencia temporal o historial de una zona."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "zone":    {"type": "string", "description": "Nombre de la zona o barrio"},
                    "metric":  {"type": "string", "description": "Nombre de la métrica"},
                    "n_weeks": {"type": "integer", "description": "Número de semanas hacia atrás (máx 9)"},
                },
                "required": ["zone", "metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_metric",
            "description": (
                "Calcula el promedio de una métrica agrupado por país, ciudad, tipo de zona, etc. "
                "Usar para preguntas de agregación o resumen general."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric":   {"type": "string", "description": "Nombre de la métrica"},
                    "group_by": {"type": "string", "description": "'COUNTRY', 'CITY', 'ZONE_TYPE', 'ZONE_PRIORITIZATION'"},
                    "week":     {"type": "string", "description": "Semana a evaluar"},
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multivariable_filter",
            "description": (
                "Encuentra zonas que cumplen condiciones simultáneas en múltiples métricas. "
                "Usar para preguntas como 'zonas con alto X pero bajo Y'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conditions": {
                        "type": "array",
                        "description": "Lista de condiciones con 'metric' y 'operator' (above_avg, below_avg, above, below)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "metric":    {"type": "string"},
                                "operator":  {"type": "string"},
                                "threshold": {"type": "number"},
                            },
                            "required": ["metric", "operator"],
                        },
                    },
                    "week":    {"type": "string", "description": "Semana a evaluar"},
                    "country": {"type": "string", "description": "Código de país para filtrar"},
                },
                "required": ["conditions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders_trend",
            "description": (
                "Identifica las zonas con mayor crecimiento en volumen de órdenes y cruza "
                "con métricas operacionales para inferir causas. Usar para preguntas de "
                "crecimiento o inferencia sobre órdenes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "n_weeks": {"type": "integer", "description": "Ventana de semanas para medir crecimiento"},
                    "top_n":   {"type": "integer", "description": "Número de zonas a retornar"},
                    "country": {"type": "string", "description": "Código de país"},
                },
            },
        },
    },
]

ASK_PATTERNS = [
    "podrías decirme", "necesito más información",
    "¿podrías", "¿podría", "could you", "please provide",
    "asumiré", "en qué ciudad", "en qué país", "qué semana",
    "¿te gustaría", "¿quieres", "¿deseas", "would you like",
    "do you want", "por favor", "proporciona", "dime",
    "no se puede obtener", "no puedo obtener", "no es posible obtener",
    "no tengo acceso", "no dispongo", "sin embargo, puedo",
]


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _normalize_locations(args: dict, metrics_df: pd.DataFrame) -> dict:
    normalized = dict(args)

    if normalized.get("country"):
        query = normalized["country"].strip()
        code_upper = query.upper()
        if code_upper in COUNTRY_CODE_TO_NAME:
            normalized["country"] = COUNTRY_CODE_TO_NAME[code_upper]
        else:
            query_lower = query.lower()
            country_candidates = metrics_df["COUNTRY"].dropna().unique()
            exact = [c for c in country_candidates if c.lower() == query_lower]
            if exact:
                normalized["country"] = exact[0]
            else:
                q_clean = _strip_accents(query_lower)
                partial = [c for c in country_candidates
                           if q_clean in _strip_accents(c.lower())
                           or _strip_accents(c.lower()) in q_clean]
                if partial:
                    normalized["country"] = min(partial, key=len)

    metric_candidates = metrics_df["METRIC"].dropna().unique()

    def _fuzzy_metric(name: str) -> str:
        query = name.strip().lower()
        exact = [c for c in metric_candidates if c.lower() == query]
        if exact:
            return exact[0]
        partial = [c for c in metric_candidates if query in c.lower() or c.lower() in query]
        if partial:
            return min(partial, key=len)
        return name

    for field, col in [("zone", "ZONE"), ("city", "CITY"), ("metric", "METRIC")]:
        if not normalized.get(field):
            continue
        query = normalized[field].strip().lower()
        candidates = metrics_df[col].dropna().unique()
        exact = [c for c in candidates if c.lower() == query]
        if exact:
            normalized[field] = exact[0]
            continue
        partial = [c for c in candidates if query in c.lower() or c.lower() in query]
        if len(partial) == 1:
            normalized[field] = partial[0]
        elif len(partial) > 1:
            normalized[field] = min(partial, key=len)

    if "conditions" in normalized and isinstance(normalized["conditions"], list):
        for cond in normalized["conditions"]:
            if isinstance(cond, dict) and cond.get("metric"):
                cond["metric"] = _fuzzy_metric(cond["metric"])

    return normalized


def _coerce_args(args: dict) -> dict:
    result = {}
    for k, v in args.items():
        if v == "" or v is None:
            continue
        if k in {"n", "n_weeks", "top_n"} and isinstance(v, str):
            result[k] = int(v) if v.strip().isdigit() else v
        elif k == "ascending" and isinstance(v, str):
            result[k] = v.strip().lower() == "true"
        else:
            result[k] = v
    return result


def _dispatch_tool(name: str, args: dict,
                   metrics_df: pd.DataFrame, orders_df: pd.DataFrame) -> dict:
    args = _coerce_args(args)
    if name == "get_top_zones":
        return get_top_zones(metrics_df, **args)
    elif name == "compare_groups":
        return compare_groups(metrics_df, **args)
    elif name == "get_zone_trend":
        return get_zone_trend(metrics_df, **args)
    elif name == "aggregate_metric":
        return aggregate_metric(metrics_df, **args)
    elif name == "multivariable_filter":
        return multivariable_filter(metrics_df, **args)
    elif name == "get_orders_trend":
        return get_orders_trend(orders_df, metrics_df, **args)
    else:
        return {"error": f"Tool desconocida: {name}"}


class RappiAgent:

    def __init__(self, metrics_df: pd.DataFrame, orders_df: pd.DataFrame):
        self.metrics_df = metrics_df
        self.orders_df = orders_df
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.history: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def chat(self, user_message: str) -> tuple[str, dict | None]:
        tool_result = None
        self.history.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=self.history,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
            message = response.choices[0].message

            if not message.tool_calls and message.content:
                if any(p in message.content.lower() for p in ASK_PATTERNS):
                    response = self.client.chat.completions.create(
                        model=MODEL,
                        messages=self.history,
                        tools=TOOL_DEFINITIONS,
                        tool_choice="required",
                    )
                    message = response.choices[0].message

            if message.tool_calls:
                self.history.append(message)

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_args = _normalize_locations(tool_args, self.metrics_df)

                    result = _dispatch_tool(tool_name, tool_args,
                                            self.metrics_df, self.orders_df)
                    tool_result = result

                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=self.history,
                )
                message = response.choices[0].message

            response_text = message.content or "No pude generar una respuesta. Intenta reformular la pregunta."

        except groq.BadRequestError:
            self.history = [{"role": "system", "content": self.history[0]["content"]}]
            response_text = "No pude procesar esa consulta correctamente. Intenta reformularla con más detalle."

        self.history.append({"role": "assistant", "content": response_text})
        return response_text, tool_result

    def reset(self):
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
