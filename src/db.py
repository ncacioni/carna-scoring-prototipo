"""Conexión a la base de datos y queries de la app.

DATABASE_URL (variable de entorno o .streamlit/secrets.toml) apunta a PostgreSQL (Neon en el despliegue).
Si no está definida, se usa un archivo SQLite local en data/carna_local.db para desarrollo.
Los nombres de tablas y columnas respetan la Estructura de Datos del TFG.
"""

import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError

from src.constants import ACCEPTED, DOMAINS, PREDICTORS, REJECTED

SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "carna_local.db"
LOCAL_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DEFAULT_PARTNERS = [{"nombre": "Socio 1", "rol": "Socio"}, {"nombre": "Socio 2", "rol": "Socio"}]

metadata = sa.MetaData()


def _check_in(col: str, values: list[str]) -> sa.CheckConstraint:
    allowed = ",".join("'" + v.replace("'", "''") + "'" for v in values)
    return sa.CheckConstraint(f"{col} IN ({allowed})", name=f"ck_{col}")


socio = sa.Table(
    "socio", metadata,
    sa.Column("id_socio", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("nombre", sa.String(100), nullable=False),
    sa.Column("rol", sa.String(50), nullable=False),
)

consulta = sa.Table(
    "consulta", metadata,
    sa.Column("id_consulta", sa.String(20), primary_key=True),
    sa.Column("fecha_consulta", sa.Date, nullable=False, server_default=sa.func.current_date()),
    sa.Column("canal_ingreso", sa.String(30), nullable=False),
    sa.Column("area_practica", sa.String(30), nullable=False),
    sa.Column("tipo_reclamo", sa.String(80), nullable=False),
    sa.Column("jurisdiccion", sa.String(40)),
    sa.Column("monto_estimado", sa.Numeric(14, 2)),
    sa.Column("estado_prescripcion", sa.String(40)),
    sa.Column("documentacion_aportada", sa.String(20)),
    sa.Column("observaciones", sa.Text),
    sa.Column("resultado_admision", sa.String(10)),
    sa.Column("motivo_rechazo", sa.String(60)),
    sa.Column("resultado_final_caso", sa.String(20)),  # NUNCA se usa como predictor
    sa.Column("fecha_carga", sa.DateTime, nullable=False, server_default=sa.func.now()),
    sa.Column("fecha_decision", sa.DateTime),
    _check_in("canal_ingreso", DOMAINS["canal_ingreso"]),
    _check_in("area_practica", DOMAINS["area_practica"]),
    _check_in("jurisdiccion", DOMAINS["jurisdiccion"]),
    _check_in("estado_prescripcion", DOMAINS["estado_prescripcion"]),
    _check_in("documentacion_aportada", DOMAINS["documentacion_aportada"]),
    _check_in("resultado_admision", [ACCEPTED, REJECTED]),
    _check_in("motivo_rechazo", DOMAINS["motivo_rechazo"]),
)

evaluacion = sa.Table(
    "evaluacion", metadata,
    sa.Column("id_evaluacion", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("id_consulta", sa.String(20), sa.ForeignKey("consulta.id_consulta"), nullable=False),
    sa.Column("id_socio", sa.Integer, sa.ForeignKey("socio.id_socio"), nullable=False),
    sa.Column("resultado_evaluacion", sa.String(10)),
    sa.Column("fecha_evaluacion", sa.DateTime, nullable=False, server_default=sa.func.now()),
    sa.UniqueConstraint("id_consulta", "id_socio"),
    _check_in("resultado_evaluacion", [ACCEPTED, REJECTED]),
)

prediccion = sa.Table(
    "prediccion", metadata,
    sa.Column("id_prediccion", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("id_consulta", sa.String(20), sa.ForeignKey("consulta.id_consulta"), nullable=False, index=True),
    sa.Column("puntaje_admision", sa.Numeric(5, 2), nullable=False),
    sa.Column("variables_shap", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    sa.Column("fecha_prediccion", sa.DateTime, nullable=False, server_default=sa.func.now()),
    sa.Column("version_modelo", sa.String(40), nullable=False),
    sa.CheckConstraint("puntaje_admision BETWEEN 0 AND 100", name="ck_puntaje"),
)

sa.Index("idx_consulta_pendientes", consulta.c.resultado_admision,
         postgresql_where=consulta.c.resultado_admision.is_(None),
         sqlite_where=consulta.c.resultado_admision.is_(None))


def now_local() -> datetime:
    """Hora de Buenos Aires sin tzinfo (las columnas son TIMESTAMP sin zona); el servidor de Cloud corre en UTC."""
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def today_local() -> date:
    return now_local().date()


def _database_url() -> str:
    # la variable de entorno tiene prioridad sobre secrets.toml: permite apuntar pruebas o scripts a otra base
    # sin riesgo de escribir en la de producción configurada en los secretos
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        import streamlit as st
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    # en un contenedor el disco es efímero: sin DATABASE_URL se perderían los datos en cada reinicio
    # (el Dockerfile define REQUIRE_DATABASE_URL para impedir el fallback a SQLite en el despliegue)
    if os.environ.get("REQUIRE_DATABASE_URL"):
        raise RuntimeError("DATABASE_URL no está configurada en las variables de entorno del servicio.")
    return f"sqlite:///{SQLITE_PATH}"


def create_db_engine(url: str | None = None) -> sa.Engine:
    url = url or _database_url()
    # pool chico y reciclado: Neon free limita conexiones y corta las inactivas
    options = {} if url.startswith("sqlite") else {"pool_size": 2, "max_overflow": 3, "pool_recycle": 280}
    engine = sa.create_engine(url, pool_pre_ping=True, **options)  # pre_ping: descarta conexiones cortadas
    metadata.create_all(engine)
    ensure_partners(engine)
    return engine


def ensure_partners(engine: sa.Engine) -> None:
    """El panel de decisión necesita los socios: se crean si la tabla está vacía."""
    with engine.begin() as conn:
        if not conn.execute(sa.select(sa.func.count()).select_from(socio)).scalar():
            conn.execute(socio.insert(), DEFAULT_PARTNERS)


# ---------------------------------------------------------------- consultas

def next_inquiry_id(conn: sa.Connection, year: int) -> str:
    """Formato C-AAAA-NNNN, correlativo dentro del año."""
    prefix = f"C-{year}-"
    last = conn.execute(
        sa.select(sa.func.max(consulta.c.id_consulta)).where(consulta.c.id_consulta.like(prefix + "%"))
    ).scalar()
    seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def insert_inquiry(engine: sa.Engine, data: dict) -> str:
    """HU-001 AC3 / HU-002: genera el id y persiste la consulta sin asignar evaluador."""
    # max()+1 puede colisionar con otra carga simultánea: se reintenta con el siguiente correlativo
    for attempt in range(5):
        try:
            with engine.begin() as conn:
                inquiry_id = next_inquiry_id(conn, data["fecha_consulta"].year)
                conn.execute(consulta.insert().values(id_consulta=inquiry_id, fecha_carga=now_local(), **data))
            return inquiry_id
        except IntegrityError:
            if attempt == 4:
                raise


def get_inquiry(engine: sa.Engine, inquiry_id: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(sa.select(consulta).where(consulta.c.id_consulta == inquiry_id)).mappings().first()
    if not row:
        return None
    inquiry = dict(row)
    if inquiry["monto_estimado"] is not None:
        inquiry["monto_estimado"] = float(inquiry["monto_estimado"])  # Numeric -> Decimal
    return inquiry


def get_predictors(engine: sa.Engine, inquiry_id: str) -> dict:
    """Lee SOLO las 7 columnas predictoras: resultado_final_caso no se selecciona nunca desde acá."""
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(*[consulta.c[col] for col in PREDICTORS]).where(consulta.c.id_consulta == inquiry_id)
        ).mappings().one()
    return dict(row)


def record_decision(engine: sa.Engine, inquiry_id: str, result: str,
                    reason: str | None, partner_id: int | None) -> None:
    """HU-006: actualiza la consulta y, si se indicó el socio, registra su evaluación individual."""
    if result == REJECTED and not reason:
        raise ValueError("Una consulta rechazada requiere un motivo de rechazo.")
    now = now_local()
    with engine.begin() as conn:
        conn.execute(
            consulta.update().where(consulta.c.id_consulta == inquiry_id).values(
                resultado_admision=result,
                motivo_rechazo=reason if result == REJECTED else None,
                fecha_decision=now,
            )
        )
        if partner_id is None:
            return
        existing = conn.execute(
            sa.select(evaluacion.c.id_evaluacion).where(
                evaluacion.c.id_consulta == inquiry_id, evaluacion.c.id_socio == partner_id)
        ).scalar()
        if existing:
            conn.execute(evaluacion.update().where(evaluacion.c.id_evaluacion == existing).values(
                resultado_evaluacion=result, fecha_evaluacion=now))
        else:
            conn.execute(evaluacion.insert().values(
                id_consulta=inquiry_id, id_socio=partner_id, resultado_evaluacion=result, fecha_evaluacion=now))


# ---------------------------------------------------------------- predicciones

def insert_prediction(engine: sa.Engine, inquiry_id: str, score: float,
                      shap_values: list[dict], model_version: str) -> None:
    with engine.begin() as conn:
        conn.execute(prediccion.insert().values(
            id_consulta=inquiry_id, puntaje_admision=round(score, 2), variables_shap=shap_values,
            version_modelo=model_version, fecha_prediccion=now_local(),
        ))


def get_latest_prediction(engine: sa.Engine, inquiry_id: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            sa.select(prediccion).where(prediccion.c.id_consulta == inquiry_id)
            .order_by(prediccion.c.id_prediccion.desc()).limit(1)
        ).mappings().first()
    if not row:
        return None
    prediction = dict(row)
    prediction["puntaje_admision"] = float(prediction["puntaje_admision"])
    return prediction


# ---------------------------------------------------------------- listados

def _with_latest_prediction():
    inner = prediccion.alias("p_latest")
    latest_id = (
        sa.select(sa.func.max(inner.c.id_prediccion))
        .where(inner.c.id_consulta == consulta.c.id_consulta)
        .scalar_subquery()
    )
    return consulta.outerjoin(prediccion, sa.and_(prediccion.c.id_consulta == consulta.c.id_consulta,
                                                  prediccion.c.id_prediccion == latest_id))


def list_pending(engine: sa.Engine) -> pd.DataFrame:
    """HU-005: consultas sin decisión, ordenadas por su puntaje más reciente (mayor a menor)."""
    query = (
        sa.select(consulta.c.id_consulta, consulta.c.fecha_consulta, consulta.c.area_practica,
                  consulta.c.tipo_reclamo, prediccion.c.puntaje_admision)
        .select_from(_with_latest_prediction())
        .where(consulta.c.resultado_admision.is_(None))
        .order_by(prediccion.c.puntaje_admision.desc().nulls_last(), consulta.c.id_consulta)
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df["puntaje_admision"] = df["puntaje_admision"].astype(float)
    df["estado"] = "Pendiente"
    return df


def list_history(engine: sa.Engine) -> pd.DataFrame:
    """HU-007: consultas con decisión registrada."""
    query = (
        sa.select(consulta.c.id_consulta, consulta.c.fecha_consulta, consulta.c.area_practica,
                  consulta.c.tipo_reclamo, consulta.c.resultado_admision, consulta.c.motivo_rechazo,
                  consulta.c.fecha_decision, prediccion.c.puntaje_admision)
        .select_from(_with_latest_prediction())
        .where(consulta.c.resultado_admision.is_not(None))
        .order_by(consulta.c.fecha_consulta.desc(), consulta.c.id_consulta.desc())
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df["puntaje_admision"] = df["puntaje_admision"].astype(float)
    df["fecha_consulta"] = pd.to_datetime(df["fecha_consulta"])
    df["fecha_decision"] = pd.to_datetime(df["fecha_decision"])
    return df


def list_partners(engine: sa.Engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(sa.select(socio).where(socio.c.rol == "Socio").order_by(socio.c.id_socio)).mappings()
        return [dict(r) for r in rows]


def count_inquiries(engine: sa.Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(sa.select(sa.func.count()).select_from(consulta)).scalar()


HINT_COLUMNS = {"area_practica", "tipo_reclamo", "jurisdiccion", "estado_prescripcion", "documentacion_aportada"}


def admission_rate_by(engine: sa.Engine, column: str) -> pd.DataFrame:
    """Tasa de admisión histórica por valor de una columna categórica (para las señales del formulario)."""
    if column not in HINT_COLUMNS:
        raise ValueError(f"Columna no permitida: {column}")
    col = consulta.c[column]
    query = (
        sa.select(
            col.label("value"),
            sa.func.count().label("n"),
            sa.func.sum(sa.case((consulta.c.resultado_admision == ACCEPTED, 1), else_=0)).label("accepted"),
        )
        .where(consulta.c.resultado_admision.is_not(None), col.is_not(None))
        .group_by(col)
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df["rate"] = df["accepted"] / df["n"]
    return df.set_index("value")
