"""Inferencia online: carga del modelo serializado + puntaje + explicación SHAP.

La app nunca reentrena: solo carga el artefacto producido por notebooks/02_model_training.ipynb.
"""

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.constants import NATURAL_LABELS, PREDICTORS, REQUIRED_PREDICTORS
from src.features import build_features

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"


@lru_cache(maxsize=1)
def load_metadata() -> dict:
    """Solo lee metadata.json y domains.json (sin importar xgboost/shap): alcanza para la página de desempeño."""
    metadata = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
    metadata["domains"] = json.loads((MODEL_DIR / "domains.json").read_text(encoding="utf-8"))
    return metadata


@lru_cache(maxsize=1)
def load_model():
    """Devuelve (modelo, explainer, metadata). metadata.json indica qué .joblib está vigente."""
    import joblib  # imports pesados (~2,4 s) diferidos hasta el primer uso del modelo
    import shap

    metadata = load_metadata()
    model = joblib.load(MODEL_DIR / metadata["model_file"])
    return model, shap.TreeExplainer(model), metadata


def build_row(record: dict) -> pd.DataFrame:
    # solo se toman las 7 claves predictoras del registro recibido
    row = pd.DataFrame([{col: record.get(col) for col in PREDICTORS}])
    return build_features(row, load_metadata()["domains"])


def explain_prediction(row: pd.DataFrame, top_n: int | None = None) -> list[dict]:
    """Contribuciones SHAP (log-odds) ordenadas por magnitud: es el JSON que va a prediccion.variables_shap."""
    _, explainer, _ = load_model()
    shap_values = explainer.shap_values(row)[0]
    contributions = sorted(zip(row.columns, shap_values), key=lambda x: abs(x[1]), reverse=True)
    if top_n:
        contributions = contributions[:top_n]
    return [
        {
            "variable": NATURAL_LABELS.get(col, col),
            "columna": col,
            "contribucion": round(float(value), 4),
            "sentido": "positivo" if value > 0 else "negativo",
        }
        for col, value in contributions
    ]


def predict(record: dict) -> tuple[float, list[dict], str]:
    """Devuelve (puntaje 0-100, variables_shap, version_modelo)."""
    missing = [col for col in REQUIRED_PREDICTORS if record.get(col) in (None, "")]
    if missing:  # el modelo no está calibrado para estos faltantes: no se emite un puntaje engañoso
        raise ValueError(f"Faltan predictores obligatorios para calcular el puntaje: {', '.join(missing)}")
    model, _, metadata = load_model()
    row = build_row(record)
    score = float(model.predict_proba(row)[0][1] * 100)
    return score, explain_prediction(row), metadata["model_version"]


def base_value() -> float:
    """Valor esperado del explainer (log-odds): punto de partida de la cascada SHAP."""
    _, explainer, _ = load_model()
    return float(np.ravel(explainer.expected_value)[0])
