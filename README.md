# Scoring predictivo de admisión de consultas — Carna, Mango & Asoc.

Prototipo de prueba de concepto del Trabajo Final de Grado *"Scoring Predictivo de Admisión de Casos en Carna, Mango & Asoc."* (Licenciatura en Ciencia de Datos, Universidad Siglo 21). Nahuel Gustavo Cacioni.

Estima un puntaje de admisión para cada consulta legal ingresada, explica cada puntaje con SHAP y registra la decisión final del socio. **Apoya el criterio de los socios, no lo reemplaza.**

**Aplicación pública:** https://carna-scoring-prototipo.onrender.com (acceso con contraseña; puede tardar alrededor de un minuto en despertar si estuvo inactiva).

> **Advertencia.** El modelo se entrenó sobre `Carna_Dataset_Simulado.xlsx`, un conjunto de datos **100% simulado**. Ni los puntajes ni las métricas representan probabilidades o desempeño sobre consultas reales del estudio.

## Stack

Python · pandas · scikit-learn · XGBoost · SHAP · Streamlit · PostgreSQL (Neon; SQLite local para desarrollo) · Docker · Render · Jupyter

## Estructura

```
app.py                     # punto de entrada: contraseña, tema, navegación
Dockerfile                 # imagen del despliegue (Python 3.12, puerto 8501)
requirements.txt           # dependencias con versiones fijadas
views/
  intake.py                # Pantalla 1 — Formulario de intake (HU-001, HU-002)
  result.py                # Pantalla 2 — Puntaje + cascada SHAP + decisión (HU-003, HU-004, HU-006)
  inquiries.py             # Pantalla 3 — Cola de pendientes e historial analítico (HU-005, HU-007)
  model.py                 # Desempeño del modelo (HU-008)
src/
  constants.py             # dominios cerrados, predictores, etiquetas
  features.py              # preprocesamiento compartido entrenamiento/inferencia
  prediction.py            # carga del modelo, puntaje y explicación SHAP
  db.py                    # esquema y queries (SQLAlchemy)
  ui.py                    # sistema visual (CSS, encabezados, tarjetas) + caché de lecturas
  explain_ui.py            # medidor del puntaje, cascada SHAP y resumen en lenguaje natural
assets/logo.svg
.streamlit/config.toml     # tema (colores, tipografías, paletas de gráficos)
model/                     # modelo serializado + dominios + metadata (métricas)
notebooks/
  01_eda.ipynb             # análisis exploratorio (T-008)
  02_model_training.ipynb  # encoding, split, entrenamiento, evaluación, SHAP, serialización (T-009 a T-012)
scripts/load_history.py    # carga de socios + histórico simulado en la base
sql/schema.sql             # DDL PostgreSQL
tests/test_app.py          # pruebas de los criterios de aceptación (Streamlit AppTest)
data/Carna_Dataset_Simulado.xlsx
```

## Instalación y ejecución local

Requiere Python 3.11 a 3.13 (el despliegue usa 3.12; con 3.14 algunas dependencias fijadas no tienen versión precompilada).

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

# contraseña de acceso
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # y editar APP_PASSWORD

# base de datos: socios + 1224 consultas históricas simuladas (+ 6 pendientes de ejemplo)
python -m scripts.load_history --demo-pending 6

streamlit run app.py
```

Sin `DATABASE_URL`, la app usa el archivo SQLite `data/carna_local.db`. Para reiniciar la base: `python -m scripts.load_history --reset --demo-pending 6`.

## Pruebas

```bash
pip install pytest
python -m pytest tests -q
```

Verifican los criterios de aceptación de HU-001 a HU-008 y el acceso por contraseña contra una base temporal (no modifican la base local).

## Reentrenar el modelo (flujo offline)

La app **nunca reentrena**: solo carga el artefacto de `model/`. Para regenerarlo, ejecutar `notebooks/02_model_training.ipynb` de principio a fin; escribe el `.joblib`, `domains.json` y `metadata.json` (versión, hiperparámetros, métricas).

## Despliegue (Render + PostgreSQL en Neon)

La versión pública corre en [Render](https://render.com) (plan gratuito) a partir del `Dockerfile` del repositorio, con la base en [Neon](https://neon.tech) (plan gratuito, región AWS us-east-1).

1. Crear una base gratuita en Neon y copiar su cadena de conexión.
2. Cargar la base desde la máquina local apuntando a esa URL:
   ```bash
   set DATABASE_URL=postgresql://usuario:clave@host/base?sslmode=require
   python -m scripts.load_history --demo-pending 6
   ```
   (Las tablas se crean solas; `sql/schema.sql` documenta el mismo esquema en SQL.)
3. En Render: **New → Web Service** → conectar este repositorio (lenguaje **Docker**, rama `main`, región Virginia, plan **Free**) y cargar las variables de entorno:
   ```
   APP_PASSWORD = ...
   DATABASE_URL = postgresql://...
   PORT         = 8501
   ```
   Health check: `/_stcore/health`. Cada push a `main` redespliega la app.

El plan gratuito suspende el servicio tras 15 minutos sin uso: el primer acceso posterior tarda alrededor de un minuto en reactivarlo.

> Se evaluó primero Streamlit Community Cloud, pero su infraestructura entregaba la interfaz de forma intermitente (pedidos colgados y websocket inestable) aun con la misma versión que funciona sin fallas en local y en Render.

## Resultados del modelo (conjunto de evaluación, datos simulados)

XGBoost (`max_depth=2`, `n_estimators=100`, `learning_rate=0.1`, elegidos por validación cruzada sobre el conjunto de entrenamiento), evaluado sobre 245 consultas (20%, estratificado):

| Exactitud | Precisión | Recall | F1-score | AUC-ROC |
|---|---|---|---|---|
| 0,788 | 0,757 | 0,937 | 0,838 | 0,816 |

Matriz de confusión (filas = real, columnas = predicho): Rechazada → 59 / 43 · Aceptada → 9 / 134.

Referencias: clasificador trivial (siempre "Aceptada") exactitud 0,584; regresión logística exactitud 0,788 / AUC 0,820. Las variables con mayor peso son la documentación aportada, el estado del plazo de prescripción y la jurisdicción, en línea con la lógica con la que se generó la simulación. Detalle completo en `notebooks/02_model_training.ipynb` y en la página *Desempeño del modelo* de la app.

## Seguridad

Acceso por contraseña compartida, guardada como variable de entorno secreta del servicio en Render (en local, en `.streamlit/secrets.toml`, que no se versiona); nunca en el código ni en el repositorio. Los cinco integrantes del estudio comparten el mismo nivel de acceso; no hay usuarios individuales ni auditoría por usuario (limitación documentada en el TFG).
