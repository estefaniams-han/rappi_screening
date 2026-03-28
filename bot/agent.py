import os
import json
import re
import inspect
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

load_dotenv(override=True)

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ---------------------------------------------------------------------------
# Definición de tools para Groq (formato OpenAI function calling)
# ---------------------------------------------------------------------------
# Groq usa el mismo formato de tools que OpenAI: una lista de dicts con
# "type": "function" y la definición de la función con sus parámetros.

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


# ---------------------------------------------------------------------------
# Normalizador de ubicaciones: fuzzy-match zona/ciudad contra los datos reales
# ---------------------------------------------------------------------------

def _normalize_locations(user_message: str, args: dict, metrics_df: pd.DataFrame) -> dict:
    """
    Corrige nombres de zona, ciudad y país para que coincidan con los datos reales.
    País: fuzzy match contra los nombres completos del DataFrame (Argentina, México, etc.)
    Zona/Ciudad/Métrica: fuzzy match case-insensitive.
    """
    normalized = dict(args)

    # Normaliza país: fuzzy match contra los nombres reales del DataFrame
    if normalized.get("country"):
        query = normalized["country"].strip().lower()
        country_candidates = metrics_df["COUNTRY"].dropna().unique()
        exact = [c for c in country_candidates if c.lower() == query]
        if exact:
            normalized["country"] = exact[0]
        else:
            partial = [c for c in country_candidates if query in c.lower() or c.lower() in query]
            if partial:
                normalized["country"] = min(partial, key=len)

    metric_candidates = metrics_df["METRIC"].dropna().unique()

    def _fuzzy_metric(name: str) -> str:
        """Fuzzy match de un nombre de métrica contra los datos reales."""
        query = name.strip().lower()
        exact = [c for c in metric_candidates if c.lower() == query]
        if exact:
            return exact[0]
        partial = [c for c in metric_candidates if query in c.lower() or c.lower() in query]
        if partial:
            return min(partial, key=len)
        return name

    # Fuzzy match para zona, ciudad y métrica (nivel superior)
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

    # Fuzzy match para métricas dentro de conditions (multivariable_filter)
    if "conditions" in normalized and isinstance(normalized["conditions"], list):
        for cond in normalized["conditions"]:
            if isinstance(cond, dict) and cond.get("metric"):
                cond["metric"] = _fuzzy_metric(cond["metric"])

    return normalized


# ---------------------------------------------------------------------------
# Despachador: mapea nombre de función -> función Python real
# ---------------------------------------------------------------------------

def _coerce_args(args: dict) -> dict:
    """Convierte strings a int/bool cuando el modelo los manda con tipo incorrecto."""
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
    """Ejecuta la tool correspondiente con los argumentos que decidió el LLM."""
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


# ---------------------------------------------------------------------------
# Agente principal
# ---------------------------------------------------------------------------

class RappiAgent:
    """
    Agente conversacional que usa Groq (Llama 3.3 70B) + function calling
    para responder preguntas sobre métricas operacionales de Rappi.

    Mantiene el historial de la conversación para tener memoria contextual.
    """

    def __init__(self, metrics_df: pd.DataFrame, orders_df: pd.DataFrame):
        self.metrics_df = metrics_df
        self.orders_df = orders_df
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        # Historial de la conversación: lista de dicts con role y content.
        # Siempre empieza con el system prompt que define el comportamiento del bot.
        self.history: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def chat(self, user_message: str) -> tuple[str, dict | None]:
        """
        Procesa un mensaje del usuario y retorna la respuesta del agente.

        Returns:
            response_text: respuesta en lenguaje natural
            tool_result: datos crudos de la tool (para graficar en la UI), o None
        """
        tool_result = None

        # Agrega el mensaje del usuario al historial
        self.history.append({"role": "user", "content": user_message})

        try:
            # --- Ronda 1: LLM decide si usar una tool o responder directo ---
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=self.history,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )

            message = response.choices[0].message

            # Si el modelo respondió con texto pero la pregunta parece requerir datos,
            # reintentamos forzando que use una tool (tool_choice="required").
            # Esto evita que el modelo pida confirmación innecesaria.
            ASK_PATTERNS = ["podrías decirme", "necesito más información",
                            "¿podrías", "¿podría", "could you", "please provide",
                            "asumiré", "en qué ciudad", "en qué país", "qué semana"]
            if not message.tool_calls and message.content:
                content_lower = message.content.lower()
                if any(p in content_lower for p in ASK_PATTERNS):
                    response = self.client.chat.completions.create(
                        model=MODEL,
                        messages=self.history,
                        tools=TOOL_DEFINITIONS,
                        tool_choice="required",
                    )
                    message = response.choices[0].message

            # Verifica si el LLM quiere llamar una o más funciones
            if message.tool_calls:
                self.history.append(message)

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_args = _normalize_locations(user_message, tool_args, self.metrics_df)

                    result = _dispatch_tool(tool_name, tool_args,
                                            self.metrics_df, self.orders_df)
                    tool_result = result

                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                # --- Ronda 2: LLM narra el resultado en lenguaje natural ---
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=self.history,
                )
                message = response.choices[0].message

            response_text = message.content or ""

        except groq.BadRequestError:
            # El modelo generó un tool call con schema inválido.
            # Limpiamos mensajes de tool del historial y reintentamos sin tools.
            self.history = [
                m for m in self.history
                if isinstance(m, dict) and m.get("role") in ("system", "user")
            ]
            try:
                fallback = self.client.chat.completions.create(
                    model=MODEL,
                    messages=self.history,
                )
                response_text = fallback.choices[0].message.content or ""
            except Exception:
                response_text = "Ocurrió un error procesando tu pregunta. Intenta reformularla."
                self.history.pop()

        # Guarda la respuesta final del asistente en el historial
        self.history.append({"role": "assistant", "content": response_text})

        return response_text, tool_result

    def reset(self):
        """Limpia el historial manteniendo solo el system prompt."""
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
