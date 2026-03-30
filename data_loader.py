import pandas as pd
from pathlib import Path

COUNTRY_CODE_TO_NAME = {
    "AR": "Argentina", "BR": "Brasil", "CL": "Chile", "CO": "Colombia",
    "CR": "Costa Rica", "EC": "Ecuador", "MX": "México", "PE": "Perú", "UY": "Uruguay",
}

EXCEL_PATH = Path("data/raw/Rappi Operations Analysis Dummy Data.xlsx")

WEEK_COLS = ["L8W_ROLL", "L7W_ROLL", "L6W_ROLL", "L5W_ROLL",
             "L4W_ROLL", "L3W_ROLL", "L2W_ROLL", "L1W_ROLL", "L0W_ROLL"]

WEEK_COLS_ORDERS = ["L8W", "L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"]

ID_COLS = ["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "ZONE_PRIORITIZATION", "METRIC"]
ID_COLS_ORDERS = ["COUNTRY", "CITY", "ZONE", "METRIC"]


def _clean_df(df: pd.DataFrame, str_cols: list[str]) -> pd.DataFrame:
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
    df["COUNTRY"] = df["COUNTRY"].map(COUNTRY_CODE_TO_NAME).fillna(df["COUNTRY"])
    for col in ["ZONE", "CITY"]:
        if col in df.columns:
            df[col] = df[col].str.replace("_", " ", regex=False).str.title()
    return df


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    xl = pd.ExcelFile(EXCEL_PATH)

    metrics_df = xl.parse("RAW_INPUT_METRICS")
    available_week_cols = [c for c in WEEK_COLS if c in metrics_df.columns]
    metrics_df = _clean_df(
        metrics_df[ID_COLS + available_week_cols].copy(),
        str_cols=["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "ZONE_PRIORITIZATION", "METRIC"],
    )

    # Algunas filas de métricas de proporción (0-1) vienen almacenadas como porcentaje (>1).
    # Dividimos por 100 iterativamente hasta que todos los valores queden en rango válido.
    proportion_metrics = [m for m in metrics_df["METRIC"].unique() if m != "Gross Profit UE"]
    mask = metrics_df["METRIC"].isin(proportion_metrics)
    for col in available_week_cols:
        while (metrics_df.loc[mask, col] > 1).any():
            metrics_df.loc[mask & (metrics_df[col] > 1), col] /= 100

    orders_df = xl.parse("RAW_ORDERS")
    available_order_cols = [c for c in WEEK_COLS_ORDERS if c in orders_df.columns]
    orders_df = _clean_df(
        orders_df[ID_COLS_ORDERS + available_order_cols].copy(),
        str_cols=["COUNTRY", "CITY", "ZONE", "METRIC"],
    )

    return metrics_df, orders_df


def get_metrics_list(metrics_df: pd.DataFrame) -> list[str]:
    return sorted(metrics_df["METRIC"].unique().tolist())


def get_zones_list(metrics_df: pd.DataFrame) -> list[str]:
    return sorted(metrics_df["ZONE"].unique().tolist())


def get_countries_list(metrics_df: pd.DataFrame) -> list[str]:
    return sorted(metrics_df["COUNTRY"].unique().tolist())


METRICS_DESCRIPTION = {
    "Lead Penetration": "Tiendas activas en Rappi / total de prospectos identificados",
    "Perfect Orders": "Órdenes sin cancelaciones, defectos ni demora / total órdenes",
    "Gross Profit UE": "Margen bruto de ganancia por orden",
    "Pro Adoption": "Usuarios con suscripción Pro / total usuarios",
    "% PRO Users Who Breakeven": "Usuarios Pro que han cubierto el costo de su membresía",
    "MLTV Top Verticals Adoption": "Usuarios que compran en múltiples verticales (restaurantes, super, pharmacy, liquors)",
    "Non-Pro PTC > OP": "Conversión de usuarios No Pro de checkout a orden colocada",
    "Restaurants Markdowns / GMV": "Descuentos en restaurantes / GMV total de restaurantes",
    "Restaurants SS > ATC CVR": "Conversión de Select Store a Add to Cart en restaurantes",
    "Restaurants SST > SS CVR": "Conversión de lista a tienda específica en restaurantes",
    "Retail SST > SS CVR": "Conversión de lista a tienda específica en supermercados",
    "Turbo Adoption": "Usuarios del servicio Turbo (entrega rápida) / total usuarios con Turbo disponible",
    "% Restaurants Sessions With Optimal Assortment": "Sesiones con mínimo 40 restaurantes disponibles",
}
