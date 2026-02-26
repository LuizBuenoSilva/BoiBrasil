"""
app/ai/identifier.py — DualIdentifier: bancos separados para animais e pessoas.

Cosine similarity via dot product (embeddings L2-normalizados).
"""

from dataclasses import dataclass, field

import numpy as np

COSINE_THRESHOLD = 0.75
UNKNOWN_LABEL = "Desconhecido"


@dataclass
class IdentityMatch:
    name: str
    entity_id: int
    similarity: float
    is_known: bool
    description: str = field(default="")


class DualIdentifier:
    """
    Dois bancos in-memory independentes: animais e pessoas.
    Operações thread-safe para leitura concorrente do stream MJPEG.
    """

    def __init__(self, threshold: float = COSINE_THRESHOLD):
        self.threshold = threshold
        self._animals: dict[str, dict] = {}
        self._people: dict[str, dict] = {}

    # --- Carregamento ---

    def load_animals(self, records: list[dict]) -> None:
        self._animals.clear()
        for r in records:
            self._animals[r["name"]] = {
                "id":          r["id"],
                "embedding":   r["embedding"],
                "description": r.get("description", ""),
            }

    def load_people(self, records: list[dict]) -> None:
        self._people.clear()
        for r in records:
            self._people[r["name"]] = {
                "id":          r["id"],
                "embedding":   r["embedding"],
                "description": r.get("description", ""),
            }

    # --- Hot-reload (após cadastro sem reiniciar) ---

    def add_animal(self, entity_id: int, name: str, embedding: np.ndarray, description: str = "") -> None:
        self._animals[name] = {
            "id":          entity_id,
            "embedding":   embedding.copy(),
            "description": description,
        }

    def add_person(self, entity_id: int, name: str, embedding: np.ndarray, description: str = "") -> None:
        self._people[name] = {
            "id":          entity_id,
            "embedding":   embedding.copy(),
            "description": description,
        }

    def remove_animal(self, name: str) -> None:
        self._animals.pop(name, None)

    def remove_person(self, name: str) -> None:
        self._people.pop(name, None)

    # --- Identificação ---

    def _identify(self, bank: dict, query: np.ndarray) -> IdentityMatch:
        if not bank:
            return IdentityMatch(name=UNKNOWN_LABEL, entity_id=-1, similarity=0.0, is_known=False)

        names = list(bank.keys())
        matrix = np.stack([bank[n]["embedding"] for n in names], axis=0)
        sims = matrix @ query
        best_idx = int(np.argmax(sims))
        best_name = names[best_idx]
        best_sim = float(sims[best_idx])

        if best_sim >= self.threshold:
            return IdentityMatch(
                name=best_name,
                entity_id=bank[best_name]["id"],
                similarity=best_sim,
                is_known=True,
                description=bank[best_name]["description"],
            )
        return IdentityMatch(
            name=UNKNOWN_LABEL, entity_id=-1, similarity=best_sim, is_known=False
        )

    def identify_animal(self, query: np.ndarray) -> IdentityMatch:
        return self._identify(self._animals, query)

    def identify_person(self, query: np.ndarray) -> IdentityMatch:
        return self._identify(self._people, query)

    def identify(self, query: np.ndarray, entity_type: str) -> IdentityMatch:
        if entity_type == "person":
            return self.identify_person(query)
        return self.identify_animal(query)

    # --- Contagens ---

    @property
    def animal_count(self) -> int:
        return len(self._animals)

    @property
    def people_count(self) -> int:
        return len(self._people)
