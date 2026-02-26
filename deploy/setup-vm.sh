#!/bin/bash
# setup-vm.sh — Roda UMA VEZ na VM do Google Cloud para instalar tudo e subir o Cattle AI.
# Uso: bash setup-vm.sh
set -e

echo "========================================"
echo "  Cattle AI — Setup da VM Google Cloud  "
echo "========================================"

# ── 1. Atualizar sistema ──────────────────────────────────────────────────────
echo "[1/6] Atualizando pacotes..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl ca-certificates gnupg lsb-release

# ── 2. Instalar Docker ────────────────────────────────────────────────────────
echo "[2/6] Instalando Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    echo "  Docker instalado."
else
    echo "  Docker já instalado, pulando."
fi

# ── 3. Instalar Docker Compose plugin ────────────────────────────────────────
echo "[3/6] Verificando Docker Compose..."
if ! docker compose version &>/dev/null; then
    sudo apt-get install -y -qq docker-compose-plugin
fi
docker compose version

# ── 4. Criar .env se não existir ─────────────────────────────────────────────
echo "[4/6] Configurando variáveis de ambiente..."
cd ~/cattle-ai

if [ ! -f .env ]; then
    cp .env.example .env
    # Gera JWT_SECRET aleatório automaticamente
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|troque-por-um-segredo-forte-em-producao|$JWT_SECRET|g" .env
    echo "  .env criado com JWT_SECRET aleatório."
    echo ""
    echo "  *** IMPORTANTE: edite ~/cattle-ai/.env e adicione sua ANTHROPIC_API_KEY ***"
    echo "  Comando: nano ~/cattle-ai/.env"
    echo ""
else
    echo "  .env já existe, mantendo."
fi

# ── 5. Build e iniciar ────────────────────────────────────────────────────────
echo "[5/6] Fazendo build e iniciando containers (pode demorar ~10-15 min na primeira vez)..."
# Precisa de novo shell para ter o grupo docker — usa sudo por segurança
sudo docker compose up -d --build

# ── 6. Configurar restart automático ─────────────────────────────────────────
echo "[6/6] Containers configurados para restart automático."
sudo docker compose ps

echo ""
echo "========================================"
echo "  Deploy concluído!"
echo "  Acesse: http://$(curl -s ifconfig.me):8000"
echo "========================================"
