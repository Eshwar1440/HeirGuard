FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Mirror the repo layout so hg.config finds <root>/ai_log and <root>/data.
WORKDIR /srv/app/backend

RUN groupadd --system app && useradd --system --gid app --home-dir /srv/app app

COPY pyproject.toml ./
COPY hg ./hg
COPY api ./api
RUN pip install .

RUN mkdir -p /srv/app/ai_log /srv/app/data && chown -R app:app /srv/app/ai_log /srv/app/data

USER app

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
