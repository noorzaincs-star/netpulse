FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NETPULSE_DEMO=true \
    PORT=7860
WORKDIR /app/backend

COPY backend/requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt
COPY backend/ ./
RUN python -m pip install --no-cache-dir --no-deps -e . \
    && useradd --create-home --uid 1000 netpulse \
    && chown -R netpulse:netpulse /app/backend
COPY --from=frontend-build /app/frontend/dist /app/backend/netpulse/static

USER netpulse
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn netpulse.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
