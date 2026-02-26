"""
database.py — SQLite CRUD para cadastro de gado.

Armazena embeddings como bytes float32 raw via ndarray.tobytes() /
np.frombuffer() para máxima velocidade de serialização.
"""

import sqlite3
from pathlib import Path

import numpy as np

DB_PATH = "cattle.db"
PHOTOS_DIR = Path("photos")


class CattleDatabase:
    """
    Wrapper SQLite para dados de cadastro de gado.
    Todos os embeddings são armazenados como bytes float32 raw.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        PHOTOS_DIR.mkdir(exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cattle (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    name           TEXT NOT NULL UNIQUE,
                    description    TEXT,
                    embedding_blob BLOB NOT NULL,
                    photo_path     TEXT,
                    registered_at  TEXT NOT NULL
                                   DEFAULT (datetime('now','localtime'))
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cattle_name ON cattle(name)"
            )

    def register(
        self,
        name: str,
        embedding: np.ndarray,
        description: str = "",
        photo_path: str = "",
    ) -> int:
        """
        Insere novo registro de gado.
        Lança sqlite3.IntegrityError se o nome já existir.
        Retorna o id da nova linha.
        """
        blob = embedding.astype(np.float32).tobytes()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO cattle
                   (name, description, embedding_blob, photo_path)
                   VALUES (?,?,?,?)""",
                (name, description, blob, photo_path),
            )
            return cur.lastrowid

    def update_embedding(self, name: str, embedding: np.ndarray) -> None:
        """Atualiza o embedding de um animal já cadastrado."""
        blob = embedding.astype(np.float32).tobytes()
        with self._connect() as conn:
            conn.execute(
                "UPDATE cattle SET embedding_blob=? WHERE name=?",
                (blob, name),
            )

    def load_all(self) -> list[dict]:
        """
        Retorna todos os registros com embedding reconstruído como ndarray.
        Chamado uma vez na inicialização para popular o banco in-memory.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, description, embedding_blob, "
                "photo_path, registered_at FROM cattle"
            ).fetchall()
        result = []
        for row in rows:
            result.append({
                "id":            row["id"],
                "name":          row["name"],
                "description":   row["description"] or "",
                "embedding":     np.frombuffer(
                    row["embedding_blob"], dtype=np.float32
                ).copy(),
                "photo_path":    row["photo_path"] or "",
                "registered_at": row["registered_at"],
            })
        return result

    def list_all(self) -> list[dict]:
        """Export CLI: retorna linhas sem bytes de embedding."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, description, photo_path, registered_at "
                "FROM cattle ORDER BY registered_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def exists(self, name: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM cattle WHERE name=?", (name,)
            ).fetchone()
        return row is not None

    def delete(self, name: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM cattle WHERE name=?", (name,))
        return cur.rowcount > 0
