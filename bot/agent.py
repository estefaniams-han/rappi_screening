import os
import json
from dotenv import load_dotenv
import requests
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

MODEL = "llama-3.3-70b-versatile"

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
        self.api_key = os.getenv("GROQ_API_KEY")
        # Cloudflare bloquea el user-agent por defecto de los SDKs de Python.
        # Usamos requests con user-agent de curl para bypassearlo.
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.4.0",
        })

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

        def _call_groq(messages: list, use_tools: bool = True) -> dict:
            """Hace una llamada a la API de Groq y retorna el mensaje de respuesta como dict."""
            payload = {"model": MODEL, "messages": messages}
            if use_tools:
                payload["tools"] = TOOL_DEFINITIONS
                payload["tool_choice"] = "auto"
            r = self.session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]

        # --- Ronda 1: LLM decide si usar una tool o responder directo ---
        message = _call_groq(self.history)

        # Verifica si el LLM quiere llamar una o más funciones
        if message.get("tool_calls"):
            # Guarda el turno del asistente en el historial
            self.history.append(message)

            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])

                # Ejecuta la función Python con los datos reales
                result = _dispatch_tool(tool_name, tool_args,
                                        self.metrics_df, self.orders_df)
                tool_result = result

                # Devuelve el resultado al historial para que el LLM lo narre
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })

            # --- Ronda 2: LLM narra el resultado en lenguaje natural ---
            message = _call_groq(self.history, use_tools=False)

        response_text = message.get("content") or ""

        # Guarda la respuesta final del asistente en el historial
        self.history.append({"role": "assistant", "content": response_text})

        return response_text, tool_result

    def reset(self):
        """Limpia el historial manteniendo solo el system prompt."""
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
