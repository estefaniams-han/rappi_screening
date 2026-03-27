import pandas as pd
from data_loader import WEEK_COLS, WEEK_COLS_ORDERS

# Mapeo semana -> etiqueta legible
# L8W = hace 8 semanas, L0W = semana actual
def _make_labels(cols):
    labels = {}
    n = len(cols)
    for i, col in enumerate(cols):
        weeks_ago = n - 1 - i
        labels[col] = "Sem. actual" if weeks_ago == 0 else f"Hace {weeks_ago} sem."
    return labels

WEEK_LABELS = _make_labels(WEEK_COLS)
WEEK_LABELS_ORDERS = _make_labels(WEEK_COLS_ORDERS)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _filter_df(df: pd.DataFrame, country: str = None, city: str = None,
               zone_type: str = None, prioritization: str = None) -> pd.DataFrame:
    """Aplica filtros geográficos/categoricos al dataframe."""
    if country:
        df = df[df["COUNTRY"].str.upper() == country.upper()]
    if city:
        df = df[df["CITY"].str.lower() == city.lower()]
    if zone_type:
        df = df[df["ZONE_TYPE"].str.lower().str.contains(zone_type.lower())]
    if prioritization:
        df = df[df["ZONE_PRIORITIZATION"].str.lower().str.contains(prioritization.lower())]
    return df


def _get_week_col(week: str = "current") -> str:
    """Convierte alias ('current', 'L0W', 'last', etc.) a nombre de columna real."""
    aliases = {
        "current": "L0W_ROLL", "l0w": "L0W_ROLL", "esta semana": "L0W_ROLL",
        "last": "L1W_ROLL", "l1w": "L1W_ROLL", "semana pasada": "L1W_ROLL",
    }
    week_lower = week.lower().replace("_roll", "")
    if week_lower in aliases:
        return aliases[week_lower]
    # Busca por número: "L3W" -> "L3W_ROLL"
    for col in WEEK_COLS:
        if week_lower in col.lower():
            return col
    return "L0W_ROLL"  # default


# ---------------------------------------------------------------------------
# Tool 1: Top / Bottom zonas por métrica
# ---------------------------------------------------------------------------

def get_top_zones(metrics_df: pd.DataFrame, metric: str, n: int = 5,
                  week: str = "current", ascending: bool = False,
                  country: str = None, city: str = None,
                  zone_type: str = None) -> dict:
    """
    Retorna las N zonas con mayor (o menor) valor de una métrica en una semana dada.

    Parámetros:
        metric: nombre de la métrica (ej: "Lead Penetration")
        n: cuántas zonas mostrar
        week: semana a evaluar ("current", "L1W", etc.)
        ascending: True para bottom N, False para top N
        country, city, zone_type: filtros opcionales
    """
    week_col = _get_week_col(week)

    df = metrics_df[metrics_df["METRIC"].str.lower() == metric.lower()].copy()
    df = _filter_df(df, country=country, city=city, zone_type=zone_type)

    if df.empty:
        return {"error": f"No se encontraron datos para la métrica '{metric}'."}

    df = df[["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", week_col]].dropna(subset=[week_col])
    df = df.sort_values(week_col, ascending=ascending).head(n)
    df = df.rename(columns={week_col: "value"})
    df["value_pct"] = (df["value"] * 100).round(2)

    return {
        "metric": metric,
        "week": WEEK_LABELS.get(week_col, week_col),
        "type": "bottom" if ascending else "top",
        "n": n,
        "data": df.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Tool 2: Comparación entre grupos (ej: Wealthy vs Non Wealthy)
# ---------------------------------------------------------------------------

def compare_groups(metrics_df: pd.DataFrame, metric: str,
                   group_by: str = "ZONE_TYPE", week: str = "current",
                   country: str = None, city: str = None) -> dict:
    """
    Compara el promedio de una métrica entre grupos (por ZONE_TYPE o ZONE_PRIORITIZATION).

    Parámetros:
        metric: nombre de la métrica
        group_by: columna por la que agrupar ("ZONE_TYPE" o "ZONE_PRIORITIZATION")
        week: semana a evaluar
        country, city: filtros opcionales
    """
    week_col = _get_week_col(week)

    df = metrics_df[metrics_df["METRIC"].str.lower() == metric.lower()].copy()
    df = _filter_df(df, country=country, city=city)

    if df.empty:
        return {"error": f"No se encontraron datos para '{metric}'."}

    grouped = (
        df.groupby(group_by)[week_col]
        .agg(["mean", "median", "count"])
        .reset_index()
        .rename(columns={"mean": "avg", "median": "median", "count": "zones_count"})
    )
    grouped["avg_pct"] = (grouped["avg"] * 100).round(2)
    grouped["median_pct"] = (grouped["median"] * 100).round(2)

    return {
        "metric": metric,
        "week": WEEK_LABELS.get(week_col, week_col),
        "group_by": group_by,
        "country": country,
        "data": grouped.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Tool 3: Tendencia temporal de una zona
# ---------------------------------------------------------------------------

def get_zone_trend(metrics_df: pd.DataFrame, zone: str, metric: str,
                   n_weeks: int = 8) -> dict:
    """
    Retorna la evolución semanal de una métrica para una zona específica.

    Parámetros:
        zone: nombre de la zona (ej: "Chapinero")
        metric: nombre de la métrica
        n_weeks: cuántas semanas hacia atrás mostrar (máx 9)
    """
    n_weeks = min(n_weeks, 9)
    week_cols = WEEK_COLS[-(n_weeks):]  # últimas N semanas

    df = metrics_df[
        (metrics_df["METRIC"].str.lower() == metric.lower()) &
        (metrics_df["ZONE"].str.lower() == zone.lower())
    ].copy()

    if df.empty:
        # Búsqueda parcial si no encuentra exacto
        df = metrics_df[
            (metrics_df["METRIC"].str.lower() == metric.lower()) &
            (metrics_df["ZONE"].str.lower().str.contains(zone.lower()))
        ].copy()

    if df.empty:
        return {"error": f"No se encontró la zona '{zone}' con métrica '{metric}'."}

    row = df.iloc[0]
    trend = [
        {"week": WEEK_LABELS[col], "value": row[col], "value_pct": round(row[col] * 100, 2)}
        for col in week_cols if col in df.columns and pd.notna(row[col])
    ]

    # Calcula cambio total entre primera y última semana disponible
    values = [t["value"] for t in trend]
    change = ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0

    return {
        "zone": row["ZONE"],
        "city": row["CITY"],
        "country": row["COUNTRY"],
        "metric": metric,
        "n_weeks": n_weeks,
        "trend": trend,
        "total_change_pct": round(change, 2),
    }


# ---------------------------------------------------------------------------
# Tool 4: Agregación por dimensión (promedio por país, ciudad, etc.)
# ---------------------------------------------------------------------------

def aggregate_metric(metrics_df: pd.DataFrame, metric: str,
                     group_by: str = "COUNTRY", week: str = "current") -> dict:
    """
    Calcula el promedio de una métrica agrupado por una dimensión.

    Parámetros:
        metric: nombre de la métrica
        group_by: dimensión de agrupación ("COUNTRY", "CITY", "ZONE_TYPE", etc.)
        week: semana a evaluar
    """
    week_col = _get_week_col(week)

    df = metrics_df[metrics_df["METRIC"].str.lower() == metric.lower()].copy()

    if df.empty:
        return {"error": f"No se encontraron datos para '{metric}'."}

    grouped = (
        df.groupby(group_by)[week_col]
        .agg(["mean", "min", "max", "count"])
        .reset_index()
        .rename(columns={"mean": "avg", "min": "min_val", "max": "max_val", "count": "zones"})
        .sort_values("avg", ascending=False)
    )
    grouped["avg_pct"] = (grouped["avg"] * 100).round(2)
    grouped["min_pct"] = (grouped["min_val"] * 100).round(2)
    grouped["max_pct"] = (grouped["max_val"] * 100).round(2)

    return {
        "metric": metric,
        "week": WEEK_LABELS.get(week_col, week_col),
        "group_by": group_by,
        "data": grouped.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Tool 5: Análisis multivariable (zonas con condiciones en múltiples métricas)
# ---------------------------------------------------------------------------

def multivariable_filter(metrics_df: pd.DataFrame,
                         conditions: list[dict],
                         week: str = "current",
                         country: str = None) -> dict:
    """
    Encuentra zonas que cumplen múltiples condiciones simultáneamente.

    conditions: lista de dicts con keys:
        - metric: nombre de la métrica
        - operator: "above" | "below" | "above_avg" | "below_avg"
        - threshold: valor numérico (solo para above/below, en proporción 0-1)

    Ejemplo:
        [{"metric": "Lead Penetration", "operator": "above_avg"},
         {"metric": "Perfect Orders", "operator": "below_avg"}]
    """
    week_col = _get_week_col(week)

    # Pivotear datos: una fila por zona, columnas = métricas
    pivot = metrics_df.pivot_table(
        index=["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "ZONE_PRIORITIZATION"],
        columns="METRIC",
        values=week_col,
        aggfunc="first"
    ).reset_index()

    if country:
        pivot = pivot[pivot["COUNTRY"].str.upper() == country.upper()]

    mask = pd.Series([True] * len(pivot), index=pivot.index)

    for cond in conditions:
        metric = cond["metric"]
        operator = cond["operator"]

        if metric not in pivot.columns:
            continue

        col = pivot[metric].dropna()
        avg = col.mean()

        if operator == "above_avg":
            mask &= pivot[metric] > avg
        elif operator == "below_avg":
            mask &= pivot[metric] < avg
        elif operator == "above" and "threshold" in cond:
            mask &= pivot[metric] > cond["threshold"]
        elif operator == "below" and "threshold" in cond:
            mask &= pivot[metric] < cond["threshold"]

    result = pivot[mask][["COUNTRY", "CITY", "ZONE", "ZONE_TYPE"] +
                          [c["metric"] for c in conditions if c["metric"] in pivot.columns]]

    # Convierte a porcentaje las métricas numéricas
    metric_cols = [c["metric"] for c in conditions if c["metric"] in result.columns]
    for col in metric_cols:
        result[col] = (result[col] * 100).round(2)

    return {
        "week": WEEK_LABELS.get(week_col, week_col),
        "conditions": conditions,
        "zones_found": len(result),
        "data": result.head(20).to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Tool 6: Tendencia de órdenes + inferencia de crecimiento
# ---------------------------------------------------------------------------

def get_orders_trend(orders_df: pd.DataFrame, metrics_df: pd.DataFrame,
                     n_weeks: int = 5, top_n: int = 10,
                     country: str = None) -> dict:
    """
    Encuentra las zonas con mayor crecimiento en órdenes y cruza con métricas
    para ayudar a explicar el crecimiento.

    Parámetros:
        n_weeks: ventana de semanas para medir crecimiento
        top_n: cuántas zonas retornar
        country: filtro opcional
    """
    week_cols = WEEK_COLS_ORDERS[-(n_weeks):]
    first_col, last_col = week_cols[0], week_cols[-1]

    df = orders_df.copy()
    if country:
        df = df[df["COUNTRY"].str.upper() == country.upper()]

    df = df.dropna(subset=[first_col, last_col])
    df = df[df[first_col] > 0]  # evita divisiones por cero

    df["growth_pct"] = ((df[last_col] - df[first_col]) / df[first_col] * 100).round(2)
    df = df.sort_values("growth_pct", ascending=False).head(top_n)

    # Cruza con métricas clave para inferir causas
    key_metrics = ["Lead Penetration", "Perfect Orders", "Non-Pro PTC > OP",
                   "% Restaurants Sessions With Optimal Assortment"]

    correlations = []
    for _, row in df.iterrows():
        zone_metrics = metrics_df[
            (metrics_df["ZONE"] == row["ZONE"]) &
            (metrics_df["METRIC"].isin(key_metrics))
        ][["METRIC", "L0W_ROLL"]].set_index("METRIC")["L0W_ROLL"].to_dict()

        correlations.append({
            "zone": row["ZONE"],
            "city": row["CITY"],
            "country": row["COUNTRY"],
            "orders_start": row[first_col],
            "orders_current": row[last_col],
            "growth_pct": row["growth_pct"],
            "metrics": {k: round(v * 100, 2) for k, v in zone_metrics.items() if pd.notna(v)},
        })

    return {
        "n_weeks": n_weeks,
        "period": f"{WEEK_LABELS_ORDERS[first_col]} → {WEEK_LABELS_ORDERS[last_col]}",
        "top_growing_zones": correlations,
    }
