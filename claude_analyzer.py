"""
claude_analyzer.py — Descrição automática de gado via Claude claude-sonnet-4-6 Vision API.

Analisa a imagem do animal e gera uma descrição concisa em linguagem pecuária
(cor da pelagem, padrões, raça, características físicas).

Fallback silencioso se ANTHROPIC_API_KEY não estiver configurada ou em caso de
erro de API — o cadastro prossegue normalmente sem descrição.
"""

import base64
import io
import os

import numpy as np
from PIL import Image

CLAUDE_MODEL = "claude-sonnet-4-6"

CATTLE_ANALYSIS_PROMPT = """Você é um zootecnista especialista em bovinos.
Analise a imagem deste bovino e forneça uma ficha técnica estruturada para o banco de dados do rebanho.

Responda EXATAMENTE neste formato (sem texto extra):

RAÇA: <nome da raça identificada, ex: Nelore, Angus, Hereford, Girolando, Brahman, Gir, ou "Mestiço">
PESO_ESTIMADO: <peso em kg estimado visualmente, ex: 380, ou "N/A" se não for possível>
DESCRIÇÃO: <2 a 3 frases descrevendo: cor da pelagem, marcações (manchas, listras, face), condição corporal (robusto/médio/magro), características físicas visíveis (chifres, orelhas, corcova)>

Exemplos:
RAÇA: Nelore
PESO_ESTIMADO: 420
DESCRIÇÃO: Pelagem branca com reflexo cinza característico. Animal robusto com corcova proeminente e orelhas longas típicas do zebuíno. Sem chifres visíveis, bom estado corporal.
Não mencione incertezas — descreva apenas o que é claramente visível.
Use terminologia zootécnica precisa.

Exemplo: "Bovino Hereford de pelagem vermelha com face branca característica e quatro patas brancas. Manchas brancas no ventre e pescoço. Porte grande, compleição robusta. Sem chifres visíveis."
"""


class ClaudeAnalyzer:
    """
    Usa Claude claude-sonnet-4-6 Vision para gerar descrições de bovinos.
    Retorna string vazia em caso de erro ou chave ausente.
    """

    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None
        if key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=key)
            except ImportError:
                print(
                    "[ClaudeAnalyzer] Pacote 'anthropic' não instalado. "
                    "Execute: pip install anthropic"
                )

    @property
    def available(self) -> bool:
        return self._client is not None

    def analyze(self, crop_bgr: np.ndarray) -> dict:
        """
        Analisa um crop BGR e retorna dict com:
          { "description": str, "breed": str, "weight": float | None }

        Retorna dict com strings vazias em caso de falha.
        """
        empty = {"description": "", "breed": "", "weight": None}
        if self._client is None:
            return empty

        try:
            import cv2

            rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            max_dim = 800
            w, h = pil.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            buf = io.BytesIO()
            pil.save(buf, format="JPEG", quality=85)
            image_data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")

            import anthropic
            message = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=350,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/jpeg", "data": image_data,
                        }},
                        {"type": "text", "text": CATTLE_ANALYSIS_PROMPT},
                    ],
                }],
            )

            raw = message.content[0].text.strip()
            return self._parse_response(raw)

        except Exception as e:
            print(f"[ClaudeAnalyzer] Falha na API: {e}")
            return empty

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """
        Extrai campos estruturados da resposta do Claude.
        Formato esperado:
          RAÇA: <valor>
          PESO_ESTIMADO: <valor>
          DESCRIÇÃO: <texto>
        """
        result = {"description": raw, "breed": "", "weight": None}
        lines = {line.split(":", 1)[0].strip().upper(): line.split(":", 1)[1].strip()
                 for line in raw.splitlines() if ":" in line}
        if "RAÇA" in lines:
            result["breed"] = lines["RAÇA"]
        if "PESO_ESTIMADO" in lines:
            try:
                result["weight"] = float(lines["PESO_ESTIMADO"].replace("kg", "").strip())
            except (ValueError, AttributeError):
                pass
        if "DESCRIÇÃO" in lines:
            result["description"] = lines["DESCRIÇÃO"]
        return result
