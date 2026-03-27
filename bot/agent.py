import os
import json
from dotenv import load_dotenv
from openai import OpenAI
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

load_dotenv()

MODEL = "llama3.1:8b-instruct-q3_K_M"
OLLAMA_BASE_URL = "http://localhost:11434/v1"

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
                    "n":         {"type": "integer", "description": "Número de zonas a retornar (default 5)"},
                    "week":      {"type": "string", "description": "Semana: 'current', 'L1W', 'L2W', etc."},
                    "ascending": {"type": "boolean", "description": "True para bottom N, False para top N"},
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
# Parser de fallback: modelos locales a veces mandan el tool call en content
# ---------------------------------------------------------------------------

def _parse_tool_call_from_content(content: str) -> tuple[str, dict] | None:
    """
    Algunos modelos locales (llama3.1, qwen) mandan el JSON del tool call
    en el campo 'content' en vez de 'tool_calls'. Este parser lo detecta
    y extrae nombre + argumentos para que el agente pueda ejecutarlo igual.
    """
    if not content or not content.strip().startswith("{"):
        return None
    try:
        data = json.loads(content.strip())
        name = data.get("name") or data.get("function")
        # Acepta tanto "arguments" como "parameters" según el modelo
        args = data.get("arguments") or data.get("parameters") or {}
        if name and name in {
            "get_top_zones", "compare_groups", "get_zone_trend",
            "aggregate_metric", "multivariable_filter", "get_orders_trend"
        }:
            return name, args
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Despachador: mapea nombre de función -> función Python real
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, args: dict,
                   metrics_df: pd.DataFrame, orders_df: pd.DataFrame) -> dict:
    """Ejecuta la tool correspondiente con los argumentos que decidió el LLM."""
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
        # Ollama expone una API compatible con OpenAI en localhost
        # api_key="ollama" es un placeholder — Ollama no requiere autenticación
        self.client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

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

        # --- Ronda 1: LLM decide si usar una tool o responder directo ---
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=self.history,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",  # el LLM decide si usar tool o responder directo
        )

        message = response.choices[0].message

        # Verifica si el LLM quiere llamar una función.
        # Primero revisa tool_calls (API nativa), luego el fallback de content JSON.
        tool_calls_to_run = []

        if message.tool_calls:
            # Camino feliz: el modelo usó el formato correcto de tool calling
            self.history.append(message)
            for tc in message.tool_calls:
                tool_calls_to_run.append((tc.function.name,
                                          json.loads(tc.function.arguments),
                                          tc.id))
        else:
            # Fallback: modelos locales a veces mandan el JSON en content
            parsed = _parse_tool_call_from_content(message.content or "")
            if parsed:
                tool_name, tool_args = parsed
                fake_id = "local_tool_0"
                # Guardamos el turno del asistente antes de ejecutar
                self.history.append({"role": "assistant", "content": message.content})
                tool_calls_to_run.append((tool_name, tool_args, fake_id))

        if tool_calls_to_run:
            for tool_name, tool_args, tool_id in tool_calls_to_run:
                result = _dispatch_tool(tool_name, tool_args,
                                        self.metrics_df, self.orders_df)
                tool_result = result

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # --- Ronda 2: LLM narra el resultado en lenguaje natural ---
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=self.history,
            )
            message = response.choices[0].message

        response_text = message.content or ""

        # Guarda la respuesta final del asistente en el historial
        self.history.append({"role": "assistant", "content": response_text})

        return response_text, tool_result

    def reset(self):
        """Limpia el historial manteniendo solo el system prompt."""
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
