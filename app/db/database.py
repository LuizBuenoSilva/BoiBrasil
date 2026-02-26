"""
app/db/database.py — Banco de dados estendido para o sistema web.

Adiciona tabelas: users, people, vaccines, movements.
Mantém compatibilidade com a tabela cattle existente.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np

from app.core.config import DB_PATH, PHOTOS_DIR


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Cria todas as tabelas se não existirem. Chamado no startup da aplicação."""
    PHOTOS_DIR.mkdir(exist_ok=True)
    with get_conn() as conn:
        # --- Tabela original ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cattle (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL UNIQUE,
                description    TEXT,
                breed          TEXT DEFAULT '',
                weight         REAL,
                embedding_blob BLOB NOT NULL,
                photo_path     TEXT,
                registered_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        # Migração: adiciona colunas se banco já existia sem elas
        for col, defn in [
            ("breed",  "TEXT DEFAULT ''"),
            ("weight", "REAL"),
            ("status", "TEXT DEFAULT 'active'"),
        ]:
            try:
                conn.execute(f"ALTER TABLE cattle ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cattle_name ON cattle(name)"
        )

        # --- Usuários do sistema ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'operator',
                created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # --- Pessoas detectadas na fazenda ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS people (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL UNIQUE,
                role           TEXT DEFAULT 'visitor',
                description    TEXT,
                weight         REAL,
                embedding_blob BLOB NOT NULL,
                photo_path     TEXT,
                registered_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        try:
            conn.execute("ALTER TABLE people ADD COLUMN weight REAL")
        except sqlite3.OperationalError:
            pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_people_name ON people(name)"
        )

        # --- Vacinas ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vaccines (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id    INTEGER NOT NULL REFERENCES cattle(id) ON DELETE CASCADE,
                vaccine_name TEXT NOT NULL,
                applied_at   TEXT NOT NULL,
                next_due     TEXT,
                notes        TEXT,
                applied_by   INTEGER REFERENCES users(id)
            )
        """)

        # --- Financeiro (gastos e receitas da fazenda) ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS financials (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                type         TEXT NOT NULL,       -- 'income' | 'expense'
                category     TEXT NOT NULL,       -- 'venda', 'vacina', 'racao', 'abate', etc.
                amount       REAL NOT NULL,
                description  TEXT,
                entity_type  TEXT,               -- 'animal' | 'general' | NULL
                entity_id    INTEGER,
                entity_name  TEXT,
                occurred_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                created_by   INTEGER REFERENCES users(id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_financials_occurred ON financials(occurred_at)"
        )

        # --- Movimentações (entradas/saídas) ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movements (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type  TEXT NOT NULL,
                entity_id    INTEGER NOT NULL,
                entity_name  TEXT NOT NULL,
                event_type   TEXT NOT NULL,
                source       TEXT NOT NULL DEFAULT 'webcam',
                detected_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                notes        TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_movements_detected ON movements(detected_at)"
        )

        # --- Câmeras configuradas ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                source_url TEXT    NOT NULL,
                type       TEXT    NOT NULL DEFAULT 'ip',
                is_active  INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

def create_user(name: str, email: str, password_hash: str, role: str = "operator") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)",
            (name, email, password_hash, role),
        )
        return cur.lastrowid


def get_user_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, email, password_hash, role, created_at FROM users WHERE email=?",
            (email,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, email, role, created_at FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, email, role, created_at FROM users ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Gado (cattle)
# ---------------------------------------------------------------------------

def register_animal(
    name: str,
    embedding: np.ndarray,
    description: str = "",
    photo_path: str = "",
    breed: str = "",
    weight: float | None = None,
    status: str = "active",
) -> int:
    blob = embedding.astype(np.float32).tobytes()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cattle (name, description, breed, weight, status, embedding_blob, photo_path) VALUES (?,?,?,?,?,?,?)",
            (name, description, breed, weight, status, blob, photo_path),
        )
        return cur.lastrowid


def get_animal(animal_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, description, breed, weight, status, photo_path, registered_at FROM cattle WHERE id=?",
            (animal_id,),
        ).fetchone()
    return dict(row) if row else None


def list_animals(status: str | None = None) -> list[dict]:
    query = "SELECT id, name, description, breed, weight, status, photo_path, registered_at FROM cattle"
    params = []
    if status:
        query += " WHERE status=?"
        params.append(status)
    query += " ORDER BY registered_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_animal(
    animal_id: int,
    name: str | None = None,
    description: str | None = None,
    breed: str | None = None,
    weight: float | None = None,
    status: str | None = None,
) -> bool:
    fields, params = [], []
    if name is not None:
        fields.append("name=?"); params.append(name)
    if description is not None:
        fields.append("description=?"); params.append(description)
    if breed is not None:
        fields.append("breed=?"); params.append(breed)
    if weight is not None:
        fields.append("weight=?"); params.append(weight)
    if status is not None:
        fields.append("status=?"); params.append(status)
    if not fields:
        return False
    params.append(animal_id)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE cattle SET {', '.join(fields)} WHERE id=?", params
        )
    return cur.rowcount > 0


def delete_animal(animal_id: int) -> bool:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM movements WHERE entity_type='animal' AND entity_id=?", (animal_id,)
        )
        cur = conn.execute("DELETE FROM cattle WHERE id=?", (animal_id,))
    return cur.rowcount > 0


def update_animal_photo(animal_id: int, photo_path: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE cattle SET photo_path=? WHERE id=?", (photo_path, animal_id)
        )
    return cur.rowcount > 0


def load_all_animals_with_embeddings() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, description, embedding_blob FROM cattle"
        ).fetchall()
    result = []
    for row in rows:
        result.append({
            "id":          row["id"],
            "name":        row["name"],
            "description": row["description"] or "",
            "embedding":   np.frombuffer(row["embedding_blob"], dtype=np.float32).copy(),
        })
    return result


def animal_exists(name: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM cattle WHERE name=?", (name,)
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Pessoas
# ---------------------------------------------------------------------------

def register_person(
    name: str,
    embedding: np.ndarray,
    role: str = "visitor",
    description: str = "",
    photo_path: str = "",
    weight: float | None = None,
) -> int:
    blob = embedding.astype(np.float32).tobytes()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO people (name, role, description, weight, embedding_blob, photo_path) VALUES (?,?,?,?,?,?)",
            (name, role, description, weight, blob, photo_path),
        )
        return cur.lastrowid


def get_person(person_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, role, description, weight, photo_path, registered_at FROM people WHERE id=?",
            (person_id,),
        ).fetchone()
    return dict(row) if row else None


def list_people() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, role, description, weight, photo_path, registered_at FROM people ORDER BY registered_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_person(
    person_id: int,
    name: str | None = None,
    role: str | None = None,
    description: str | None = None,
    weight: float | None = None,
) -> bool:
    fields, params = [], []
    if name is not None:
        fields.append("name=?"); params.append(name)
    if role is not None:
        fields.append("role=?"); params.append(role)
    if description is not None:
        fields.append("description=?"); params.append(description)
    if weight is not None:
        fields.append("weight=?"); params.append(weight)
    if not fields:
        return False
    params.append(person_id)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE people SET {', '.join(fields)} WHERE id=?", params
        )
    return cur.rowcount > 0


def delete_person(person_id: int) -> bool:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM movements WHERE entity_type='person' AND entity_id=?", (person_id,)
        )
        cur = conn.execute("DELETE FROM people WHERE id=?", (person_id,))
    return cur.rowcount > 0


def update_person_photo(person_id: int, photo_path: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE people SET photo_path=? WHERE id=?", (photo_path, person_id)
        )
    return cur.rowcount > 0


def list_ids_without_photo() -> dict[str, list[int]]:
    """Retorna IDs de animais e pessoas que ainda não têm foto salva."""
    with get_conn() as conn:
        animal_ids = [r[0] for r in conn.execute(
            "SELECT id FROM cattle WHERE photo_path IS NULL OR photo_path=''"
        ).fetchall()]
        person_ids = [r[0] for r in conn.execute(
            "SELECT id FROM people WHERE photo_path IS NULL OR photo_path=''"
        ).fetchall()]
    return {"animals": animal_ids, "people": person_ids}


def load_all_people_with_embeddings() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, description, embedding_blob FROM people"
        ).fetchall()
    result = []
    for row in rows:
        result.append({
            "id":          row["id"],
            "name":        row["name"],
            "description": row["description"] or "",
            "embedding":   np.frombuffer(row["embedding_blob"], dtype=np.float32).copy(),
        })
    return result


def person_exists(name: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM people WHERE name=?", (name,)
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Vacinas
# ---------------------------------------------------------------------------

def add_vaccine(
    animal_id: int,
    vaccine_name: str,
    applied_at: str,
    next_due: str | None = None,
    notes: str = "",
    applied_by: int | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO vaccines (animal_id, vaccine_name, applied_at, next_due, notes, applied_by) "
            "VALUES (?,?,?,?,?,?)",
            (animal_id, vaccine_name, applied_at, next_due, notes, applied_by),
        )
        return cur.lastrowid


def list_vaccines(animal_id: int | None = None) -> list[dict]:
    query = """
        SELECT v.id, v.animal_id, c.name as animal_name,
               v.vaccine_name, v.applied_at, v.next_due, v.notes,
               u.name as applied_by_name
        FROM vaccines v
        JOIN cattle c ON c.id = v.animal_id
        LEFT JOIN users u ON u.id = v.applied_by
    """
    params = []
    if animal_id is not None:
        query += " WHERE v.animal_id=?"
        params.append(animal_id)
    query += " ORDER BY v.applied_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def delete_vaccine(vaccine_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM vaccines WHERE id=?", (vaccine_id,))
    return cur.rowcount > 0


def list_upcoming_vaccines(days: int = 30) -> list[dict]:
    """Vacinas com next_due nos próximos N dias."""
    query = """
        SELECT v.id, v.animal_id, c.name as animal_name,
               v.vaccine_name, v.next_due
        FROM vaccines v
        JOIN cattle c ON c.id = v.animal_id
        WHERE v.next_due IS NOT NULL
          AND date(v.next_due) BETWEEN date('now') AND date('now', '+' || ? || ' days')
        ORDER BY v.next_due ASC
    """
    with get_conn() as conn:
        rows = conn.execute(query, (days,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Movimentações
# ---------------------------------------------------------------------------

def add_movement(
    entity_type: str,
    entity_id: int,
    entity_name: str,
    event_type: str,
    source: str = "webcam",
    notes: str = "",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO movements (entity_type, entity_id, entity_name, event_type, source, notes) "
            "VALUES (?,?,?,?,?,?)",
            (entity_type, entity_id, entity_name, event_type, source, notes),
        )
        return cur.lastrowid


def list_movements(
    entity_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query = """
        SELECT id, entity_type, entity_id, entity_name,
               event_type, source, detected_at, notes
        FROM movements
    """
    params = []
    if entity_type:
        query += " WHERE entity_type=?"
        params.append(entity_type)
    query += " ORDER BY detected_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_last_movement(entity_type: str, entity_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT detected_at FROM movements WHERE entity_type=? AND entity_id=? "
            "ORDER BY detected_at DESC LIMIT 1",
            (entity_type, entity_id),
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

def get_dashboard_stats() -> dict:
    with get_conn() as conn:
        total_animals = conn.execute("SELECT COUNT(*) FROM cattle").fetchone()[0]
        total_people = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        movements_today = conn.execute(
            "SELECT COUNT(*) FROM movements WHERE date(detected_at)=date('now','localtime')"
        ).fetchone()[0]
        vaccines_upcoming = conn.execute(
            "SELECT COUNT(*) FROM vaccines WHERE next_due IS NOT NULL "
            "AND date(next_due) BETWEEN date('now') AND date('now','+30 days')"
        ).fetchone()[0]

        # Atividade dos últimos 7 dias
        chart_rows = conn.execute("""
            SELECT
                date(detected_at,'localtime') as day,
                SUM(CASE WHEN event_type='entry' THEN 1 ELSE 0 END) as entries,
                SUM(CASE WHEN event_type='exit' THEN 1 ELSE 0 END) as exits
            FROM movements
            WHERE detected_at >= datetime('now','-7 days','localtime')
            GROUP BY day
            ORDER BY day ASC
        """).fetchall()

        # Resumo financeiro do mês
        fin = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) as income_month,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as expense_month
            FROM financials
            WHERE strftime('%Y-%m', occurred_at) = strftime('%Y-%m', 'now', 'localtime')
        """).fetchone()

        active_animals   = conn.execute("SELECT COUNT(*) FROM cattle WHERE status='active'").fetchone()[0]
        sold_animals     = conn.execute("SELECT COUNT(*) FROM cattle WHERE status='sold'").fetchone()[0]
        slaughtered_animals = conn.execute("SELECT COUNT(*) FROM cattle WHERE status='slaughtered'").fetchone()[0]

        # Breakdown de despesas por categoria no mês corrente
        cat_rows = conn.execute("""
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM financials
            WHERE type='expense'
              AND strftime('%Y-%m', occurred_at) = strftime('%Y-%m', 'now', 'localtime')
            GROUP BY category
            ORDER BY total DESC
        """).fetchall()

    return {
        "total_animals":        total_animals,
        "active_animals":       active_animals,
        "sold_animals":         sold_animals,
        "slaughtered_animals":  slaughtered_animals,
        "total_people":         total_people,
        "total_users":          total_users,
        "movements_today":      movements_today,
        "vaccines_upcoming":    vaccines_upcoming,
        "activity_chart":       [dict(r) for r in chart_rows],
        "income_month":         round(fin["income_month"], 2),
        "expense_month":        round(fin["expense_month"], 2),
        "balance_month":        round(fin["income_month"] - fin["expense_month"], 2),
        "expense_by_category":  [{"category": r["category"], "total": round(r["total"], 2)} for r in cat_rows],
    }


# ---------------------------------------------------------------------------
# Financeiro
# ---------------------------------------------------------------------------

def add_financial(
    type: str,
    category: str,
    amount: float,
    description: str = "",
    entity_type: str | None = None,
    entity_id: int | None = None,
    entity_name: str | None = None,
    occurred_at: str | None = None,
    created_by: int | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO financials
               (type, category, amount, description, entity_type, entity_id, entity_name, occurred_at, created_by)
               VALUES (?,?,?,?,?,?,?,COALESCE(?,datetime('now','localtime')),?)""",
            (type, category, amount, description, entity_type, entity_id, entity_name, occurred_at, created_by),
        )
        return cur.lastrowid


def list_financials(
    type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query = """
        SELECT f.id, f.type, f.category, f.amount, f.description,
               f.entity_type, f.entity_id, f.entity_name,
               f.occurred_at, u.name as created_by_name
        FROM financials f
        LEFT JOIN users u ON u.id = f.created_by
    """
    params = []
    if type:
        query += " WHERE f.type=?"
        params.append(type)
    query += " ORDER BY f.occurred_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def delete_financial(financial_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM financials WHERE id=?", (financial_id,))
    return cur.rowcount > 0


def get_financial_summary(months: int = 6) -> list[dict]:
    """Resumo mensal de receitas e despesas para gráfico."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m', occurred_at, 'localtime') as month,
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as expense
            FROM financials
            WHERE occurred_at >= datetime('now', ? || ' months', 'localtime')
            GROUP BY month
            ORDER BY month ASC
        """, (f"-{months}",)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Câmeras
# ---------------------------------------------------------------------------

def add_camera(name: str, source_url: str, cam_type: str = "ip") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cameras (name, source_url, type) VALUES (?,?,?)",
            (name, source_url, cam_type),
        )
        return cur.lastrowid


def get_camera(cam_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, source_url, type, is_active, created_at FROM cameras WHERE id=?",
            (cam_id,),
        ).fetchone()
    return dict(row) if row else None


def list_cameras() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, source_url, type, is_active, created_at FROM cameras ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def update_camera(
    cam_id: int,
    name: str | None = None,
    source_url: str | None = None,
    cam_type: str | None = None,
    is_active: bool | None = None,
) -> bool:
    fields, params = [], []
    if name is not None:
        fields.append("name=?"); params.append(name)
    if source_url is not None:
        fields.append("source_url=?"); params.append(source_url)
    if cam_type is not None:
        fields.append("type=?"); params.append(cam_type)
    if is_active is not None:
        fields.append("is_active=?"); params.append(int(is_active))
    if not fields:
        return False
    params.append(cam_id)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE cameras SET {', '.join(fields)} WHERE id=?", params
        )
    return cur.rowcount > 0


def delete_camera(cam_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM cameras WHERE id=?", (cam_id,))
    return cur.rowcount > 0
