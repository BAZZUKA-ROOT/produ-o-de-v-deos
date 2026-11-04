FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    STORAGE_DIR=/data/storage TEMP_DIR=/data/tmp MODELS_DIR=/data/models FONTS_DIR=/app/assets/fonts

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak-ng libsndfile1 fontconfig curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY assets ./assets
RUN mkdir -p /usr/share/fonts/truetype/forja && cp assets/fonts/*.ttf /usr/share/fonts/truetype/forja/ && fc-cache -f

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN useradd --create-home --uid 1000 forja \
    && mkdir -p /data/storage /data/tmp /data/models \
    && chown -R forja:forja /data /app \
    && chmod +x /usr/local/bin/docker-entrypoint.sh
USER forja

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD curl -fs http://localhost:8000/api/health || exit 1
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["api"]
