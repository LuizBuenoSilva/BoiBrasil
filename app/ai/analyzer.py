"""
app/ai/analyzer.py — Wrapper do ClaudeAnalyzer para o contexto web.

Importa o módulo original e fornece instância singleton.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from claude_analyzer import ClaudeAnalyzer  # noqa: E402
from app.core.config import ANTHROPIC_API_KEY

_analyzer: ClaudeAnalyzer | None = None


def get_analyzer() -> ClaudeAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = ClaudeAnalyzer(api_key=ANTHROPIC_API_KEY or None)
    return _analyzer
