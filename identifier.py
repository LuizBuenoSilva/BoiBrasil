"""
identifier.py — Motor de correspondência de embeddings por cosine similarity.

Mantém um banco in-memory de vetores L2-normalizados e identifica
animais por similaridade de cosseno via produto escalar (dot product).
"""

from dataclasses import dataclass, field

import numpy as np

COSINE_THRESHOLD = 0.75  # Threshold padrão; ajustável via CLI
UNKNOWN_LABEL = "Desconhecido"


@dataclass
class IdentityMatch:
    """Resultado da identificação de um animal."""

    name: str
    similarity: float
    is_known: bool
    description: str = field(default="")


class CattleIdentifier:
    """
    Motor de identificação in-memory por cosine similarity.

    Banco de identidades: { nome: { "embedding": ndarray, "description": str } }

    Todos os embeddings armazenados são L2-normalizados (feito pelo CattleEmbedder),
    então cosine similarity == produto escalar (dot product), operação O(1) por par.

    Para N animais: matrix @ query_vec executa N dot products em paralelo com numpy.
    Eficiente até ~10.000 animais sem necessidade de banco vetorial externo.
    """

    def __init__(self, threshold: float = COSINE_THRESHOLD):
        self.threshold = threshold
        self._bank: dict[str, dict] = {}

    def load_from_db(self, records: list[dict]) -> None:
        """
        Carrega todos os registros do CattleDatabase.load_all().
        Chamado uma vez na inicialização.
        """
        self._bank.clear()
        for rec in records:
            self._bank[rec["name"]] = {
                "embedding":   rec["embedding"],
                "description": rec["description"] or "",
            }

    def add(self, name: str, embedding: np.ndarray, description: str = "") -> None:
        """
        Adiciona ou sobrescreve entrada no banco in-memory.
        Chamado imediatamente após cadastro bem-sucedido, sem reload do DB.
        """
        self._bank[name] = {
            "embedding":   embedding.copy(),
            "description": description,
        }

    def remove(self, name: str) -> None:
        """Remove um animal do banco in-memory."""
        self._bank.pop(name, None)

    def identify(self, query_embedding: np.ndarray) -> IdentityMatch:
        """
        Encontra o melhor match para um embedding de consulta.

        Como todos os embeddings são L2-normalizados, cosine similarity
        é equivalente ao produto escalar. Usa matrix @ query_vec para
        calcular todas as similaridades em uma operação numpy.

        Retorna IdentityMatch com:
        - is_known=True se similarity >= threshold
        - is_known=False (Desconhecido) caso contrário ou banco vazio
        """
        if not self._bank:
            return IdentityMatch(
                name=UNKNOWN_LABEL, similarity=0.0, is_known=False
            )

        names = list(self._bank.keys())
        # Empilha todos os embeddings: (N, 1280)
        matrix = np.stack(
            [self._bank[n]["embedding"] for n in names], axis=0
        )
        # Cosine similarity via dot product (ambos L2-normalizados)
        similarities = matrix @ query_embedding  # shape: (N,)

        best_idx = int(np.argmax(similarities))
        best_name = names[best_idx]
        best_sim = float(similarities[best_idx])

        if best_sim >= self.threshold:
            return IdentityMatch(
                name=best_name,
                similarity=best_sim,
                is_known=True,
                description=self._bank[best_name]["description"],
            )

        return IdentityMatch(
            name=UNKNOWN_LABEL,
            similarity=best_sim,
            is_known=False,
        )

    @property
    def registered_count(self) -> int:
        return len(self._bank)

    def all_names(self) -> list[str]:
        return list(self._bank.keys())
