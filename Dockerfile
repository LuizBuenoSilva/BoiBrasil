# ── Stage 1: build do frontend React ─────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build


# ── Stage 2: backend Python ───────────────────────────────────────────────────
FROM python:3.11-slim

# Dependências de sistema para OpenCV e GL
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python primeiro (aproveita cache de camada)
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Copia o código da aplicação
COPY . .

# Copia o build do React para dentro do container
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Garante que as pastas de dados existam (dev local)
# Em produção o volume /data é montado via DATA_DIR
RUN mkdir -p photos /data/photos

EXPOSE 8000

# Usa $PORT se disponível (Railway injeta automaticamente), senão 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
