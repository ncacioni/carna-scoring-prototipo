"""Carga inicial de la base: socios + las 1224 consultas históricas simuladas (con su decisión ya tomada).

Uso:
    python -m scripts.load_history                 # base vacía -> socios + histórico
    python -m scripts.load_history --demo-pending 6  # además, N consultas pendientes con su predicción
    python -m scripts.load_history --reset         # borra todo y vuelve a cargar

Usa DATABASE_URL si está definida (variable de entorno); si no, el SQLite local data/carna_local.db.
"""

import argparse
from datetime import datetime

import numpy as np
import pandas as pd
import sqlalchemy as sa

from src import db
from src.constants import PREDICTORS
from src.features import load_dataset
from src.prediction import predict

def _clean(value):
    return None if pd.isna(value) else value


def load_history(engine: sa.Engine) -> int:
    df = load_dataset()
    with engine.begin() as conn:
        # los socios ya los crea db.create_db_engine (ensure_partners)
        partner_ids = {r.nombre: r.id_socio for r in conn.execute(sa.select(db.socio))}

        loaded_at = db.now_local()
        inquiries = [
            {
                "id_consulta": r.id_consulta, "fecha_consulta": r.fecha_consulta,
                **{col: _clean(getattr(r, col)) for col in PREDICTORS},
                "observaciones": _clean(r.observaciones), "resultado_admision": r.resultado_admision,
                "motivo_rechazo": _clean(r.motivo_rechazo), "resultado_final_caso": _clean(r.resultado_final_caso),
                "fecha_carga": loaded_at,
                # el dataset no registra cuándo se decidió: queda NULL para distinguir histórico de decisiones nuevas
                "fecha_decision": None,
            }
            for r in df.itertuples()
        ]
        conn.execute(db.consulta.insert(), inquiries)

        # el histórico registra un único socio evaluador por consulta (Anexo A del TFG)
        evaluations = [
            {"id_consulta": r.id_consulta, "id_socio": partner_ids[r.socio_evaluador],
             "resultado_evaluacion": r.resultado_admision,
             "fecha_evaluacion": datetime.combine(r.fecha_consulta, datetime.min.time())}
            for r in df.itertuples()
        ]
        conn.execute(db.evaluacion.insert(), evaluations)
    return len(df)


def create_demo_pending(engine: sa.Engine, n: int, seed: int = 7) -> list[str]:
    """Consultas pendientes de ejemplo para la demo de HU-005: combinaciones de predictores tomadas del dataset."""
    rng = np.random.default_rng(seed)
    sample = load_dataset().sample(n, random_state=int(rng.integers(1_000_000)))
    created = []
    for r in sample.itertuples():
        record = {col: _clean(getattr(r, col)) for col in PREDICTORS}
        if record["monto_estimado"] is not None:
            record["monto_estimado"] = float(record["monto_estimado"])
        inquiry_id = db.insert_inquiry(engine, {"fecha_consulta": db.today_local(), **record,
                                                "observaciones": "Consulta de ejemplo para la demo."})
        score, shap_values, version = predict(record)
        db.insert_prediction(engine, inquiry_id, score, shap_values, version)
        created.append(inquiry_id)
    return created


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="borra todas las tablas antes de cargar")
    parser.add_argument("--demo-pending", type=int, default=0, metavar="N")
    args = parser.parse_args()

    engine = db.create_db_engine()
    print(f"Base: {engine.url.render_as_string(hide_password=True)}")
    if args.reset:
        db.metadata.drop_all(engine)
        db.metadata.create_all(engine)
        db.ensure_partners(engine)

    if db.count_inquiries(engine) == 0:
        print(f"Histórico cargado: {load_history(engine)} consultas.")
    else:
        print("La base ya tiene consultas: se omite la carga del histórico (usar --reset para recargar).")

    if args.demo_pending:
        print("Pendientes de demo:", ", ".join(create_demo_pending(engine, args.demo_pending)))


if __name__ == "__main__":
    main()
