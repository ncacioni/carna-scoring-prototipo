# Imagen del prototipo para Hugging Face Spaces (SDK Docker) o cualquier hosting de contenedores.
# Secretos esperados como variables de entorno: APP_PASSWORD y DATABASE_URL (PostgreSQL en Neon).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REQUIRE_DATABASE_URL=1

# Hugging Face Spaces ejecuta el contenedor con el usuario de UID 1000
RUN useradd --create-home --uid 1000 appuser
WORKDIR /home/appuser/app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY --chown=appuser:appuser . .
USER appuser

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
