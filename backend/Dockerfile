FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NETPULSE_DEMO=true \
    CORS_ORIGINS=https://noorzan-netpulse-network-monitor.static.hf.space \
    NETPULSE_DATABASE_URL=sqlite+aiosqlite:////data/netpulse.db \
    PORT=7860

WORKDIR /app/backend

COPY backend/requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt
COPY backend/ ./
RUN python -m pip install --no-cache-dir --no-deps .

RUN mkdir -p /data \
    && useradd --create-home --uid 1000 netpulse \
    && chown -R netpulse:netpulse /app/backend /data

VOLUME ["/data"]
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c 'import os,urllib.request; urllib.request.urlopen("http://127.0.0.1:%s/api/health" % os.getenv("PORT", "7860"), timeout=3)' || exit 1

USER netpulse
CMD ["sh", "-c", "exec python -m uvicorn netpulse.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
