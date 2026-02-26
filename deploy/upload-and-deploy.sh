#!/bin/bash
# upload-and-deploy.sh — Copia o projeto para a VM e dispara o setup.
# Uso: bash deploy/upload-and-deploy.sh [VM_NAME] [ZONE] [PROJECT_ID]
set -e

VM_NAME="${1:-cattle-ai}"
ZONE="${2:-southamerica-east1-b}"
PROJECT_ID="${3:-$(gcloud config get-value project)}"
REMOTE_USER="$(gcloud config get-value account 2>/dev/null | cut -d@ -f1 | tr '.' '_')"

# Raiz do projeto (pasta acima de deploy/)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================"
echo "  Cattle AI — Upload para GCE           "
echo "========================================"
echo "Projeto local : $PROJECT_DIR"
echo "VM            : $VM_NAME ($ZONE)"
echo "Projeto GCP   : $PROJECT_ID"
echo ""

# ── 1. Empacotar o projeto (exclui node_modules, venv, banco local) ───────────
echo "[1/3] Empacotando arquivos..."
TMPTAR="/tmp/cattle-ai-deploy.tar.gz"
tar -czf "$TMPTAR" \
    --exclude="./frontend/node_modules" \
    --exclude="./frontend/dist" \
    --exclude="./.venv" \
    --exclude="./venv" \
    --exclude="./cattle.db" \
    --exclude="./photos" \
    --exclude="./.git" \
    --exclude="./__pycache__" \
    --exclude="./**/__pycache__" \
    -C "$PROJECT_DIR" .

echo "  Pacote: $TMPTAR ($(du -sh "$TMPTAR" | cut -f1))"

# ── 2. Enviar para a VM ────────────────────────────────────────────────────────
echo "[2/3] Enviando para a VM via SCP..."
gcloud compute scp "$TMPTAR" "${VM_NAME}:/tmp/cattle-ai-deploy.tar.gz" \
    --zone="$ZONE" \
    --project="$PROJECT_ID"

# ── 3. Extrair e executar setup na VM ─────────────────────────────────────────
echo "[3/3] Executando setup na VM..."
gcloud compute ssh "$VM_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="
        set -e
        echo '--- Extraindo arquivos...'
        mkdir -p ~/cattle-ai
        tar -xzf /tmp/cattle-ai-deploy.tar.gz -C ~/cattle-ai
        rm /tmp/cattle-ai-deploy.tar.gz
        echo '--- Iniciando setup...'
        bash ~/cattle-ai/deploy/setup-vm.sh
    "

# ── IP final ───────────────────────────────────────────────────────────────────
EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "========================================"
echo "  Deploy concluído!"
echo "  Acesse: http://$EXTERNAL_IP:8000"
echo "========================================"
