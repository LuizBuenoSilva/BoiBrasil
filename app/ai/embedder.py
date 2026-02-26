"""
app/ai/embedder.py — Singleton do CattleEmbedder para uso no contexto web.

Importa diretamente o módulo original para evitar duplicação de código.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from embedder import CattleEmbedder  # noqa: E402

# Instância singleton — carregada uma vez no startup do FastAPI
_embedder: CattleEmbedder | None = None


def get_embedder() -> CattleEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = CattleEmbedder()
    return _embedder
