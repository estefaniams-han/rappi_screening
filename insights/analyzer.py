import pandas as pd
import numpy as np
from data_loader import WEEK_COLS, WEEK_COLS_ORDERS

# Las 3 semanas más recientes y la actual
W0, W1, W2, W3 = "L0W_ROLL", "L1W_ROLL", "L2W_ROLL", "L3W_ROLL"

# Métricas donde MENOR es mejor (para invertir la lógica de deterioro)
LOWER_IS_BETTER = {"Restaurants Markdowns / GMV"}


def _pct_change(a, b):
    """Cambio porcentual de b→a. Retorna NaN si b es 0 o NaN."""
    if pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return (a - b) / abs(b) * 100


def _is_deterioration(metric: str, change_pct: float) -> bool:
    """True si el cambio representa deterioro para esa métrica."""
    if metric in LOWER_IS_BETTER:
        return change_pct > 0   # subió cuando debería bajar
    return change_pct < 0       # bajó cuando debería subir


# ---------------------------------------------------------------------------
# 1. Anomalías — cambios drásticos semana a semana (>10%)
# ---------------------------------------------------------------------------

def detect_anomalies(metrics_df: pd.DataFrame, threshold: float = 10.0) -> list[dict]:
    """
    Detecta zonas con cambios drásticos (>threshold%) entre L1W y L0W.
    Retorna lista de hallazgos ordenada por magnitud de cambio.
    """
    results = []
    df = metrics_df[[*["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "METRIC"], W0, W1]].dropna(subset=[W0, W1])

    for _, row in df.iterrows():
        change = _pct_change(row[W0], row[W1])
        if pd.isna(change) or abs(change) < threshold:
            continue

        deterioro = _is_deterioration(row["METRIC"], change)
        results.append({
            "country": row["COUNTRY"],
            "city": row["CITY"],
            "zone": row["ZONE"],
            "zone_type": row["ZONE_TYPE"],
            "metric": row["METRIC"],
            "value_prev": round(row[W1] * 100, 2),
            "value_curr": round(row[W0] * 100, 2),
            "change_pct": round(change, 2),
            "is_deterioration": deterioro,
            "severity": "alta" if abs(change) > 25 else "media",
        })

    results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return results


# ---------------------------------------------------------------------------
# 2. Tendencias preocupantes — deterioro consistente 3+ semanas seguidas
# ---------------------------------------------------------------------------

def detect_worrying_trends(metrics_df: pd.DataFrame, min_weeks: int = 3) -> list[dict]:
    """
    Detecta métricas en deterioro consistente durante min_weeks o más semanas.
    """
    results = []
    week_cols = WEEK_COLS[-min_weeks - 1:]  # necesitamos N+1 puntos para N cambios

    df = metrics_df[["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "METRIC"] + week_cols].dropna(subset=week_cols)

    for _, row in df.iterrows():
        values = [row[c] for c in week_cols]
        metric = row["METRIC"]

        # Calcula si cada semana fue peor que la anterior
        if metric in LOWER_IS_BETTER:
            # deterioro = valor sube semana a semana (WEEK_COLS va de más antiguo a más reciente)
            deteriorating = all(values[i] < values[i + 1] for i in range(len(values) - 1))
        else:
            # deterioro = valor baja semana a semana
            deteriorating = all(values[i] > values[i + 1] for i in range(len(values) - 1))

        if not deteriorating:
            continue

        total_change = _pct_change(values[-1], values[0])
        if pd.isna(total_change) or abs(total_change) < 5:
            continue

        results.append({
            "country": row["COUNTRY"],
            "city": row["CITY"],
            "zone": row["ZONE"],
            "zone_type": row["ZONE_TYPE"],
            "metric": row["METRIC"],
            "weeks_declining": min_weeks,
            "value_start": round(values[0] * 100, 2),
            "value_end": round(values[-1] * 100, 2),
            "total_change_pct": round(total_change, 2),
        })

    results.sort(key=lambda x: x["total_change_pct"])
    return results


# ---------------------------------------------------------------------------
# 3. Benchmarking — zonas similares con performance divergente
# ---------------------------------------------------------------------------

def detect_benchmarking(metrics_df: pd.DataFrame, z_threshold: float = 1.5) -> list[dict]:
    """
    Compara cada zona contra el promedio de su grupo (mismo país + zone_type).
    Detecta zonas que están >z_threshold desviaciones estándar por debajo del grupo.
    """
    results = []
    df = metrics_df[["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "METRIC", W0]].dropna(subset=[W0])

    for (country, zone_type, metric), group in df.groupby(["COUNTRY", "ZONE_TYPE", "METRIC"]):
        if len(group) < 3:
            continue

        mean = group[W0].mean()
        std = group[W0].std()
        if std == 0 or pd.isna(std):
            continue

        for _, row in group.iterrows():
            z = (row[W0] - mean) / std

            if metric in LOWER_IS_BETTER:
                underperform = z > z_threshold      # está por encima (peor)
            else:
                underperform = z < -z_threshold     # está por debajo (peor)

            if not underperform:
                continue

            results.append({
                "country": row["COUNTRY"],
                "city": row["CITY"],
                "zone": row["ZONE"],
                "zone_type": zone_type,
                "metric": metric,
                "zone_value": round(row[W0] * 100, 2),
                "group_avg": round(mean * 100, 2),
                "gap_pct": round((row[W0] - mean) / abs(mean) * 100, 2) if mean != 0 else 0,
                "z_score": round(z, 2),
            })

    results.sort(key=lambda x: abs(x["z_score"]), reverse=True)
    return results


# ---------------------------------------------------------------------------
# 4. Correlaciones — métricas que se mueven juntas
# ---------------------------------------------------------------------------

def detect_correlations(metrics_df: pd.DataFrame, threshold: float = 0.65) -> list[dict]:
    """
    Encuentra pares de métricas con correlación fuerte (>threshold) entre zonas.
    Útil para entender qué métricas se mueven juntas.
    """
    # Pivotear: una fila por zona, columnas = métricas
    pivot = metrics_df.pivot_table(
        index=["COUNTRY", "ZONE"],
        columns="METRIC",
        values=W0,
        aggfunc="first"
    )

    corr_matrix = pivot.corr()
    results = []

    metrics = corr_matrix.columns.tolist()
    for i, m1 in enumerate(metrics):
        for m2 in metrics[i + 1:]:
            corr = corr_matrix.loc[m1, m2]
            if pd.isna(corr) or abs(corr) < threshold:
                continue

            results.append({
                "metric_a": m1,
                "metric_b": m2,
                "correlation": round(corr, 3),
                "direction": "positiva" if corr > 0 else "negativa",
                "strength": "fuerte" if abs(corr) > 0.8 else "moderada",
            })

    results.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return results


# ---------------------------------------------------------------------------
# 5. Oportunidades — zonas con alto volumen pero métricas mejorables
# ---------------------------------------------------------------------------

def detect_opportunities(metrics_df: pd.DataFrame, orders_df: pd.DataFrame) -> list[dict]:
    """
    Identifica zonas de alto volumen de órdenes donde métricas clave están
    por debajo del promedio — alto impacto potencial si se mejoran.
    """
    # Calcula órdenes actuales por zona
    orders_curr = orders_df[["COUNTRY", "ZONE", "L0W"]].copy()
    orders_curr = orders_curr.rename(columns={"L0W": "orders"})
    orders_p75 = orders_curr["orders"].quantile(0.75)

    # Zonas de alto volumen
    high_vol_df = orders_curr[orders_curr["orders"] >= orders_p75]
    high_vol = high_vol_df.set_index(["COUNTRY", "ZONE"])["orders"].to_dict()

    # Métricas clave a revisar
    key_metrics = ["Perfect Orders", "Lead Penetration", "Non-Pro PTC > OP", "Gross Profit UE"]
    df = metrics_df[metrics_df["METRIC"].isin(key_metrics)][
        ["COUNTRY", "ZONE", "ZONE_TYPE", "METRIC", W0]
    ].dropna(subset=[W0])

    # Promedio global por métrica
    global_avg = df.groupby("METRIC")[W0].mean()

    results = []
    for (country, zone), zone_data in df.groupby(["COUNTRY", "ZONE"]):
        if (country, zone) not in high_vol:
            continue

        lagging = []
        for _, row in zone_data.iterrows():
            metric = row["METRIC"]
            avg = global_avg.get(metric)
            if avg is None or pd.isna(avg) or avg == 0:
                continue
            gap = (row[W0] - avg) / abs(avg) * 100
            if gap < -15:  # está >15% por debajo del promedio global
                lagging.append({
                    "metric": metric,
                    "value": round(row[W0] * 100, 2),
                    "global_avg": round(avg * 100, 2),
                    "gap_pct": round(gap, 2),
                })

        if not lagging:
            continue

        results.append({
            "country": country,
            "zone": zone,
            "zone_type": zone_data.iloc[0]["ZONE_TYPE"],
            "orders": int(high_vol[(country, zone)]),
            "lagging_metrics": lagging,
            "opportunity_score": len(lagging) * high_vol[(country, zone)],
        })

    results.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return results[:15]


# ---------------------------------------------------------------------------
# Función principal: corre todos los análisis
# ---------------------------------------------------------------------------

def run_all(metrics_df: pd.DataFrame, orders_df: pd.DataFrame) -> dict:
    """Ejecuta todos los detectores y retorna un dict con los resultados."""
    return {
        "anomalies":       detect_anomalies(metrics_df),
        "worrying_trends": detect_worrying_trends(metrics_df),
        "benchmarking":    detect_benchmarking(metrics_df),
        "correlations":    detect_correlations(metrics_df),
        "opportunities":   detect_opportunities(metrics_df, orders_df),
    }
