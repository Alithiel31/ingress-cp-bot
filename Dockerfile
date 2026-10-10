FROM python:3.11-slim

# Pas de .pyc, logs affichés immédiatement, chemin du fichier heartbeat (surveillé par le HEALTHCHECK)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEARTBEAT_FILE=/app/data/heartbeat

WORKDIR /app

# Aucune dépendance ne nécessite de compilation : pas d'outils de build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Utilisateur non-root, propriétaire de /app et du dossier de données
RUN useradd --create-home --shell /usr/sbin/nologin botuser \
    && mkdir -p /app/data \
    && chown -R botuser:botuser /app

COPY --chown=botuser:botuser main.py commands.py ingress.py auth.py ./

USER botuser

# Le bot écrit un heartbeat toutes les 30 s : "unhealthy" s'il a plus de 2 minutes
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os, sys, time; sys.exit(0 if time.time() - os.path.getmtime(os.environ['HEARTBEAT_FILE']) < 120 else 1)"

CMD ["python", "main.py"]
