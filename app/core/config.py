"""
config.py — Configurações centrais do sistema web.
"""

import os
from pathlib import Path

# Diretório raiz do projeto cattle-ai
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Em produção (Railway), DATA_DIR aponta para o volume persistente (/data)
# Em desenvolvimento, usa a raiz do projeto normalmente
_DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR)))

# Banco de dados
DB_PATH = str(_DATA_DIR / "cattle.db")
PHOTOS_DIR = _DATA_DIR / "photos"

# Porta do servidor (Railway injeta PORT automaticamente)
PORT = int(os.environ.get("PORT", "8000"))

# JWT
JWT_SECRET = os.environ.get("JWT_SECRET", "cattle-ai-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

# Câmera
CAMERA_SOURCE = os.environ.get("CAMERA_SOURCE", "0")  # 0=webcam, ou caminho/RTSP

# IA
YOLO_MODEL = os.environ.get("YOLO_MODEL", "yolov8n.pt")
DETECTION_CONF = float(os.environ.get("DETECTION_CONF", "0.40"))
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.75"))

# Claude
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Auto-cadastro: cooldown em segundos antes de registrar nova entrada do mesmo animal
MOVEMENT_COOLDOWN_SECONDS = int(os.environ.get("MOVEMENT_COOLDOWN", "300"))  # 5 min
