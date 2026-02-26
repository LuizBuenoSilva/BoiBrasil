#!/bin/bash
# create-vm.sh — Cria a VM no Google Cloud e configura o firewall.
# Pré-requisito: gcloud instalado e autenticado (gcloud auth login)
#
# Uso: bash deploy/create-vm.sh [SEU_PROJECT_ID]
set -e

PROJECT_ID="${1:-$(gcloud config get-value project)}"
VM_NAME="cattle-ai"
ZONE="southamerica-east1-b"     # São Paulo — troque se preferir outra região
MACHINE_TYPE="e2-standard-4"    # 4 vCPUs, 16 GB RAM (mínimo para PyTorch+YOLO)
DISK_SIZE="60GB"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"

echo "Projeto  : $PROJECT_ID"
echo "VM       : $VM_NAME"
echo "Zona     : $ZONE"
echo "Máquina  : $MACHINE_TYPE"
echo ""

# ── Criar VM ──────────────────────────────────────────────────────────────────
echo "[1/3] Criando VM..."
gcloud compute instances create "$VM_NAME" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --image-family="$IMAGE_FAMILY" \
    --image-project="$IMAGE_PROJECT" \
    --boot-disk-size="$DISK_SIZE" \
    --boot-disk-type="pd-ssd" \
    --tags="cattle-ai-server" \
    --metadata="enable-oslogin=TRUE"

# ── Regra de firewall para porta 8000 ─────────────────────────────────────────
echo "[2/3] Criando regra de firewall (porta 8000)..."
gcloud compute firewall-rules create allow-cattle-ai \
    --project="$PROJECT_ID" \
    --allow="tcp:8000" \
    --target-tags="cattle-ai-server" \
    --description="Acesso ao Cattle AI Web" \
    --quiet 2>/dev/null || echo "  Regra já existe, pulando."

# ── Mostrar IP externo ─────────────────────────────────────────────────────────
echo "[3/3] VM criada com sucesso!"
EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "IP externo: $EXTERNAL_IP"
echo ""
echo "Próximo passo — rode no terminal:"
echo "  bash deploy/upload-and-deploy.sh $VM_NAME $ZONE $PROJECT_ID"
