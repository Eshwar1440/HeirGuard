FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build context is the repo root (docker-compose and Render both use it), so the image can
# carry the synthetic sample packets. Mirror the repo layout so hg.config finds
# <root>/ai_log and <root>/data.
WORKDIR /srv/app/backend

RUN groupadd --system app && useradd --system --gid app --home-dir /srv/app app

COPY backend/pyproject.toml ./
COPY backend/hg ./hg
COPY backend/api ./api
RUN pip install .

COPY data/packets /srv/app/data/packets
RUN mkdir -p /srv/app/ai_log /srv/app/data/uploads && chown -R app:app /srv/app/ai_log /srv/app/data

USER app

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
