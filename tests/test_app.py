"""Pruebas de los criterios de aceptación (HU-001 a HU-008) y de seguridad, con Streamlit AppTest.

Uso: python -m pytest tests -q
Cada prueba corre contra una base SQLite temporal cargada con el histórico simulado; la base local no se toca.
"""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "clave-de-prueba"


@pytest.fixture(scope="session", autouse=True)
def test_database(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.chdir(ROOT)

    from scripts.load_history import create_demo_pending, load_history
    from src import db

    engine = db.create_db_engine()
    load_history(engine)
    create_demo_pending(engine, 3)
    return engine


def new_app(page: str | None = None, authenticated: bool = True):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.secrets["APP_PASSWORD"] = PASSWORD
    if authenticated:
        at.session_state["authenticated"] = True
    if page:
        at.switch_page(page)
    return at.run()


def widget(group, label):
    return next(w for w in group if w.label == label)


# ---------------------------------------------------------------- seguridad

def test_login_gate_blocks_content_and_rejects_wrong_password():
    at = new_app(authenticated=False)
    assert not at.exception
    assert not any(t.value == "Nueva consulta" for t in at.title)
    at.text_input[0].input("incorrecta")
    at.button[0].click().run()
    assert [e.value for e in at.error] == ["Contraseña incorrecta."]
    at.text_input[0].input(PASSWORD)
    at.button[0].click().run()
    assert not at.exception and at.session_state["authenticated"]


# ---------------------------------------------------------------- HU-001 / HU-002 / HU-003

def test_intake_requires_mandatory_fields_and_persists_inquiry(test_database):
    from src import db

    at = new_app("views/intake.py")
    calculate = lambda: widget(at.button, "Calcular puntaje")
    assert calculate().disabled

    widget(at.button_group, "Canal de ingreso *").set_value("Referido")
    widget(at.button_group, "Área de práctica *").set_value("Laboral")
    at.run()
    widget(at.selectbox, "Tipo de reclamo *").select("Despido sin causa")
    widget(at.button_group, "Documentación aportada *").set_value("Completa")
    at.run()
    assert calculate().disabled  # falta el estado de prescripción
    assert "Plazo de prescripción" in at.info[0].value

    widget(at.selectbox, "Estado del plazo de prescripción *").select("Vigente")
    at.run()
    assert not calculate().disabled

    before = set(db.list_pending(test_database)["id_consulta"])
    calculate().click().run()
    assert not at.exception
    new_ids = set(db.list_pending(test_database)["id_consulta"]) - before
    assert len(new_ids) == 1
    new_id = new_ids.pop()
    assert new_id.startswith("C-")
    prediction = db.get_latest_prediction(test_database, new_id)
    assert prediction is not None and 0 <= prediction["puntaje_admision"] <= 100
    assert prediction["variables_shap"]


# ---------------------------------------------------------------- HU-003 / HU-004 / HU-006

def test_result_shows_warning_first_and_rejection_requires_reason(test_database):
    from src import db
    from src.constants import POC_WARNING

    inquiry_id = db.list_pending(test_database)["id_consulta"].iloc[0]
    at = new_app()
    at.session_state["current_inquiry"] = inquiry_id
    at.switch_page("views/result.py").run()
    assert not at.exception
    assert len(at.get("html")) and POC_WARNING in at.get("html")[0].proto.body

    widget(at.button_group, "Socio que registra la decisión").set_value("Socio 1")
    widget(at.button_group, "Decisión").set_value("Rechazar")
    at.run()
    confirm = lambda: widget(at.button, "Confirmar decisión")
    assert confirm().disabled
    widget(at.selectbox, "Motivo de rechazo *").select("Plazo vencido").run()
    assert not confirm().disabled
    confirm().click().run()

    inquiry = db.get_inquiry(test_database, inquiry_id)
    assert inquiry["resultado_admision"] == "Rechazada"
    assert inquiry["motivo_rechazo"] == "Plazo vencido"
    assert inquiry["fecha_decision"] is not None
    assert inquiry_id not in set(db.list_pending(test_database)["id_consulta"])  # HU-005 AC3


# ---------------------------------------------------------------- HU-005 / HU-007 / HU-008

def test_pending_queue_is_sorted_by_score(test_database):
    from src import db

    scores = db.list_pending(test_database)["puntaje_admision"].tolist()
    assert scores == sorted(scores, reverse=True)
    at = new_app("views/inquiries.py")
    assert not at.exception


def test_history_filters_combine():
    at = new_app("views/inquiries.py")
    widget(at.multiselect, "Área de práctica").set_value(["Laboral"])
    widget(at.multiselect, "Resultado de admisión").set_value(["Rechazada"])
    at.run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Rechazadas"] == "100%" and metrics["Admitidas"] == "0%"


def test_model_page_reports_metrics():
    at = new_app("views/model.py")
    assert not at.exception
    assert {m.label for m in at.metric} >= {"Exactitud", "Precisión", "Recall", "F1-score", "AUC-ROC"}


# ---------------------------------------------------------------- modelo

def test_features_never_include_post_decision_columns():
    import pandas as pd

    from src.features import MODEL_COLUMNS, build_features, load_dataset

    df = load_dataset()
    assert "resultado_final_caso" in df.columns
    X = build_features(df)
    assert list(X.columns) == MODEL_COLUMNS
    assert not {"resultado_final_caso", "socio_evaluador", "motivo_rechazo", "resultado_admision"} & set(X.columns)
    assert isinstance(X, pd.DataFrame) and len(X) == 1224


def test_predict_refuses_missing_uncalibrated_predictors():
    from src.prediction import predict

    record = {"canal_ingreso": "Referido", "area_practica": "Laboral", "tipo_reclamo": "Despido sin causa",
              "documentacion_aportada": "Completa"}
    with pytest.raises(ValueError, match="estado_prescripcion"):
        predict(record)
    score, shap_values, _ = predict({**record, "estado_prescripcion": "Vigente"})
    assert 0 <= score <= 100 and len(shap_values) == 8
