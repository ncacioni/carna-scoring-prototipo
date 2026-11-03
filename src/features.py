"""Preprocesamiento compartido entre el notebook de entrenamiento y la app."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.constants import ACCEPTED, DOMAINS, EXCEL_COLUMNS, FORBIDDEN_COLUMNS, PREDICTORS

NOMINAL_COLUMNS = ["canal_ingreso", "area_practica", "tipo_reclamo", "jurisdiccion"]
ORDINAL_COLUMNS = {
    "estado_prescripcion": ["No aplica", "Vigente", "Por vencer (menos de 6 meses)", "Vencido"],
    "documentacion_aportada": ["Ninguna", "Parcial", "Completa"],
}
MODEL_COLUMNS = NOMINAL_COLUMNS + list(ORDINAL_COLUMNS) + ["monto_estimado", "monto_informado"]

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "Carna_Dataset_Simulado.xlsx"


def load_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    """Lee la hoja "Consultas" (la fila 0 es la banda Obligatoria/Recomendada/Opcional) y normaliza nombres."""
    df = pd.read_excel(path, sheet_name="Consultas", header=1)
    df = df.rename(columns=EXCEL_COLUMNS)[list(EXCEL_COLUMNS.values())]
    df["fecha_consulta"] = pd.to_datetime(df["fecha_consulta"]).dt.date
    return df


def build_features(df: pd.DataFrame, domains: dict = DOMAINS) -> pd.DataFrame:
    # Solo se leen los 7 predictores oficiales: cualquier otra columna del df de entrada se descarta acá,
    # de modo que resultado_final_caso (u otra columna posterior a la decisión) no pueda filtrarse a X.
    df = df[PREDICTORS].copy()
    assert not FORBIDDEN_COLUMNS & set(df.columns)

    # nominales -> dtype category con las categorías FIJAS de DOMAINS (no .astype('category') a secas,
    # porque eso infiere categorías del propio df y puede divergir entre train y una consulta nueva)
    for col in NOMINAL_COLUMNS:
        df[col] = pd.Categorical(df[col], categories=domains[col])

    # ordinales -> enteros según el orden definido; valor no reconocido o vacío -> NaN (no -1)
    for col, order in ORDINAL_COLUMNS.items():
        codes = pd.Categorical(df[col], categories=order, ordered=True).codes.astype(float)
        df[col] = np.where(codes < 0, np.nan, codes)

    # señal de faltante + deja el NaN nativo para que XGBoost lo maneje
    df["monto_estimado"] = pd.to_numeric(df["monto_estimado"], errors="coerce").astype(float)
    df["monto_informado"] = df["monto_estimado"].notna().astype(int)

    return df[MODEL_COLUMNS]


def build_target(df: pd.DataFrame) -> pd.Series:
    return (df["resultado_admision"] == ACCEPTED).astype(int)
