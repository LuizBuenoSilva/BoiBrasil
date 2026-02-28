"""
app/db/database.py — Banco de dados com multi-tenancy por fazenda.

Cada fazenda (farm) é isolada: usuários, animais, pessoas, movimentações,
vacinas, financeiro e câmeras são filtrados por farm_id.
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
    """Cria/migra todas as tabelas. Chamado no startup da aplicação."""
    PHOTOS_DIR.mkdir(exist_ok=True)
    with get_conn() as conn:
        # --- Fazendas (deve existir antes de todas as outras) ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farms (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL UNIQUE,
                created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # --- Usuários do sistema ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id       INTEGER REFERENCES farms(id),
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'operator',
                created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        _try_add_column(conn, "users", "farm_id", "INTEGER REFERENCES farms(id)")

        # --- Gado (cattle) ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cattle (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id        INTEGER REFERENCES farms(id),
                name           TEXT NOT NULL,
                description    TEXT,
                breed          TEXT DEFAULT '',
                weight         REAL,
                status         TEXT DEFAULT 'active',
                embedding_blob BLOB NOT NULL,
                photo_path     TEXT,
                registered_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        for col, defn in [
            ("breed",   "TEXT DEFAULT ''"),
            ("weight",  "REAL"),
            ("status",  "TEXT DEFAULT 'active'"),
            ("farm_id", "INTEGER REFERENCES farms(id)"),
        ]:
            _try_add_column(conn, "cattle", col, defn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cattle_farm ON cattle(farm_id)"
        )

        # --- Pessoas detectadas ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS people (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id        INTEGER REFERENCES farms(id),
                name           TEXT NOT NULL,
                role           TEXT DEFAULT 'visitor',
                description    TEXT,
                weight         REAL,
                embedding_blob BLOB NOT NULL,
                photo_path     TEXT,
                registered_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        for col, defn in [
            ("weight",  "REAL"),
            ("farm_id", "INTEGER REFERENCES farms(id)"),
        ]:
            _try_add_column(conn, "people", col, defn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_people_farm ON people(farm_id)"
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

        # --- Financeiro ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS financials (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id      INTEGER REFERENCES farms(id),
                type         TEXT NOT NULL,
                category     TEXT NOT NULL,
                amount       REAL NOT NULL,
                description  TEXT,
                entity_type  TEXT,
                entity_id    INTEGER,
                entity_name  TEXT,
                occurred_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                created_by   INTEGER REFERENCES users(id)
            )
        """)
        _try_add_column(conn, "financials", "farm_id", "INTEGER REFERENCES farms(id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_financials_farm ON financials(farm_id)"
        )

        # --- Movimentações ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movements (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id      INTEGER REFERENCES farms(id),
                entity_type  TEXT NOT NULL,
                entity_id    INTEGER NOT NULL,
                entity_name  TEXT NOT NULL,
                event_type   TEXT NOT NULL,
                source       TEXT NOT NULL DEFAULT 'webcam',
                detected_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                notes        TEXT
            )
        """)
        _try_add_column(conn, "movements", "farm_id", "INTEGER REFERENCES farms(id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_movements_farm ON movements(farm_id)"
        )

        # --- Câmeras ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id    INTEGER REFERENCES farms(id),
                name       TEXT    NOT NULL,
                source_url TEXT    NOT NULL,
                type       TEXT    NOT NULL DEFAULT 'ip',
                is_active  INTEGER NOT NULL DEFAULT 1,
                created_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        _try_add_column(conn, "cameras", "farm_id", "INTEGER REFERENCES farms(id)")

        # --- Migração: fazenda padrão para dados existentes sem farm_id ---
        _migrate_default_farm(conn)


def _try_add_column(conn: sqlite3.Connection, table: str, col: str, defn: str) -> None:
    """Adiciona coluna se ainda não existir (migração segura)."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
    except sqlite3.OperationalError:
        pass


def _migrate_default_farm(conn: sqlite3.Connection) -> None:
    """
    Se existem dados legados sem farm_id, cria uma fazenda padrão
    e associa todos os dados a ela.
    """
    # Só migra se ainda não existem fazendas
    farm_count = conn.execute("SELECT COUNT(*) FROM farms").fetchone()[0]
    if farm_count > 0:
        return

    # Verifica se há dados legados sem farm_id
    has_legacy = any(
        conn.execute(f"SELECT 1 FROM {t} WHERE farm_id IS NULL LIMIT 1").fetchone()
        for t in ("cattle", "people", "users", "cameras", "movements", "financials")
    )
    if not has_legacy:
        return

    # Cria fazenda padrão
    cur = conn.execute("INSERT INTO farms (name) VALUES (?)", ("Fazenda Principal",))
    farm_id = cur.lastrowid

    for table in ("cattle", "people", "users", "cameras", "movements", "financials"):
        conn.execute(
            f"UPDATE {table} SET farm_id=? WHERE farm_id IS NULL", (farm_id,)
        )

    print(f"[DB] Migração: fazenda padrão criada (id={farm_id}) para dados existentes.")


# ---------------------------------------------------------------------------
# Fazendas
# ---------------------------------------------------------------------------

def create_farm(name: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO farms (name) VALUES (?)", (name,))
        return cur.lastrowid


def get_farm_by_id(farm_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM farms WHERE id=?", (farm_id,)
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

def create_user(name: str, email: str, password_hash: str, role: str, farm_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (farm_id, name, email, password_hash, role) VALUES (?,?,?,?,?)",
            (farm_id, name, email, password_hash, role),
        )
        return cur.lastrowid


def get_user_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, farm_id, name, email, password_hash, role, created_at FROM users WHERE email=?",
            (email,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, farm_id, name, email, role, created_at FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def list_users(farm_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, farm_id, name, email, role, created_at FROM users "
            "WHERE farm_id=? ORDER BY created_at",
            (farm_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_user(user_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    return cur.rowcount > 0


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
    farm_id: int | None = None,
) -> int:
    blob = embedding.astype(np.float32).tobytes()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cattle (farm_id, name, description, breed, weight, status, embedding_blob, photo_path) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (farm_id, name, description, breed, weight, status, blob, photo_path),
        )
        return cur.lastrowid


def get_animal(animal_id: int, farm_id: int | None = None) -> dict | None:
    with get_conn() as conn:
        if farm_id is not None:
            row = conn.execute(
                "SELECT id, name, description, breed, weight, status, photo_path, registered_at "
                "FROM cattle WHERE id=? AND farm_id=?",
                (animal_id, farm_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, name, description, breed, weight, status, photo_path, registered_at "
                "FROM cattle WHERE id=?",
                (animal_id,),
            ).fetchone()
    return dict(row) if row else None


def list_animals(farm_id: int, status: str | None = None) -> list[dict]:
    query = (
        "SELECT id, name, description, breed, weight, status, photo_path, registered_at "
        "FROM cattle WHERE farm_id=?"
    )
    params: list = [farm_id]
    if status:
        query += " AND status=?"
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
    farm_id: int | None = None,
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
    query = f"UPDATE cattle SET {', '.join(fields)} WHERE id=?"
    if farm_id is not None:
        query += " AND farm_id=?"
        params.append(farm_id)
    with get_conn() as conn:
        cur = conn.execute(query, params)
    return cur.rowcount > 0


def delete_animal(animal_id: int, farm_id: int | None = None) -> bool:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM movements WHERE entity_type='animal' AND entity_id=?", (animal_id,)
        )
        if farm_id is not None:
            cur = conn.execute(
                "DELETE FROM cattle WHERE id=? AND farm_id=?", (animal_id, farm_id)
            )
        else:
            cur = conn.execute("DELETE FROM cattle WHERE id=?", (animal_id,))
    return cur.rowcount > 0


def update_animal_photo(animal_id: int, photo_path: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE cattle SET photo_path=? WHERE id=?", (photo_path, animal_id)
        )
    return cur.rowcount > 0


def load_all_animals_with_embeddings(farm_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if farm_id is not None:
            rows = conn.execute(
                "SELECT id, name, description, embedding_blob FROM cattle WHERE farm_id=?",
                (farm_id,),
            ).fetchall()
        else:
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


def animal_exists(name: str, farm_id: int | None = None) -> bool:
    with get_conn() as conn:
        if farm_id is not None:
            row = conn.execute(
                "SELECT 1 FROM cattle WHERE name=? AND farm_id=?", (name, farm_id)
            ).fetchone()
        else:
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
    farm_id: int | None = None,
) -> int:
    blob = embedding.astype(np.float32).tobytes()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO people (farm_id, name, role, description, weight, embedding_blob, photo_path) "
            "VALUES (?,?,?,?,?,?,?)",
            (farm_id, name, role, description, weight, blob, photo_path),
        )
        return cur.lastrowid


def get_person(person_id: int, farm_id: int | None = None) -> dict | None:
    with get_conn() as conn:
        if farm_id is not None:
            row = conn.execute(
                "SELECT id, name, role, description, weight, photo_path, registered_at "
                "FROM people WHERE id=? AND farm_id=?",
                (person_id, farm_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, name, role, description, weight, photo_path, registered_at "
                "FROM people WHERE id=?",
                (person_id,),
            ).fetchone()
    return dict(row) if row else None


def list_people(farm_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, role, description, weight, photo_path, registered_at "
            "FROM people WHERE farm_id=? ORDER BY registered_at DESC",
            (farm_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_person(
    person_id: int,
    name: str | None = None,
    role: str | None = None,
    description: str | None = None,
    weight: float | None = None,
    farm_id: int | None = None,
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
    query = f"UPDATE people SET {', '.join(fields)} WHERE id=?"
    if farm_id is not None:
        query += " AND farm_id=?"
        params.append(farm_id)
    with get_conn() as conn:
        cur = conn.execute(query, params)
    return cur.rowcount > 0


def delete_person(person_id: int, farm_id: int | None = None) -> bool:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM movements WHERE entity_type='person' AND entity_id=?", (person_id,)
        )
        if farm_id is not None:
            cur = conn.execute(
                "DELETE FROM people WHERE id=? AND farm_id=?", (person_id, farm_id)
            )
        else:
            cur = conn.execute("DELETE FROM people WHERE id=?", (person_id,))
    return cur.rowcount > 0


def update_person_photo(person_id: int, photo_path: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE people SET photo_path=? WHERE id=?", (photo_path, person_id)
        )
    return cur.rowcount > 0


def list_ids_without_photo(farm_id: int | None = None) -> dict[str, list[int]]:
    """Retorna IDs de animais e pessoas que ainda não têm foto salva."""
    with get_conn() as conn:
        if farm_id is not None:
            animal_ids = [r[0] for r in conn.execute(
                "SELECT id FROM cattle WHERE farm_id=? AND (photo_path IS NULL OR photo_path='')",
                (farm_id,),
            ).fetchall()]
            person_ids = [r[0] for r in conn.execute(
                "SELECT id FROM people WHERE farm_id=? AND (photo_path IS NULL OR photo_path='')",
                (farm_id,),
            ).fetchall()]
        else:
            animal_ids = [r[0] for r in conn.execute(
                "SELECT id FROM cattle WHERE photo_path IS NULL OR photo_path=''"
            ).fetchall()]
            person_ids = [r[0] for r in conn.execute(
                "SELECT id FROM people WHERE photo_path IS NULL OR photo_path=''"
            ).fetchall()]
    return {"animals": animal_ids, "people": person_ids}


def load_all_people_with_embeddings(farm_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if farm_id is not None:
            rows = conn.execute(
                "SELECT id, name, description, embedding_blob FROM people WHERE farm_id=?",
                (farm_id,),
            ).fetchall()
        else:
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


def person_exists(name: str, farm_id: int | None = None) -> bool:
    with get_conn() as conn:
        if farm_id is not None:
            row = conn.execute(
                "SELECT 1 FROM people WHERE name=? AND farm_id=?", (name, farm_id)
            ).fetchone()
        else:
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


def list_vaccines(animal_id: int | None = None, farm_id: int | None = None) -> list[dict]:
    query = """
        SELECT v.id, v.animal_id, c.name as animal_name,
               v.vaccine_name, v.applied_at, v.next_due, v.notes,
               u.name as applied_by_name
        FROM vaccines v
        JOIN cattle c ON c.id = v.animal_id
        LEFT JOIN users u ON u.id = v.applied_by
    """
    params = []
    conditions = []
    if animal_id is not None:
        conditions.append("v.animal_id=?")
        params.append(animal_id)
    if farm_id is not None:
        conditions.append("c.farm_id=?")
        params.append(farm_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY v.applied_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def delete_vaccine(vaccine_id: int, farm_id: int | None = None) -> bool:
    with get_conn() as conn:
        if farm_id is not None:
            cur = conn.execute(
                "DELETE FROM vaccines WHERE id=? AND animal_id IN "
                "(SELECT id FROM cattle WHERE farm_id=?)",
                (vaccine_id, farm_id),
            )
        else:
            cur = conn.execute("DELETE FROM vaccines WHERE id=?", (vaccine_id,))
    return cur.rowcount > 0


def list_upcoming_vaccines(days: int = 30, farm_id: int | None = None) -> list[dict]:
    """Vacinas com next_due nos próximos N dias."""
    query = """
        SELECT v.id, v.animal_id, c.name as animal_name,
               v.vaccine_name, v.next_due
        FROM vaccines v
        JOIN cattle c ON c.id = v.animal_id
        WHERE v.next_due IS NOT NULL
          AND date(v.next_due) BETWEEN date('now') AND date('now', '+' || ? || ' days')
    """
    params: list = [days]
    if farm_id is not None:
        query += " AND c.farm_id=?"
        params.append(farm_id)
    query += " ORDER BY v.next_due ASC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
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
    farm_id: int | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO movements (farm_id, entity_type, entity_id, entity_name, event_type, source, notes) "
            "VALUES (?,?,?,?,?,?,?)",
            (farm_id, entity_type, entity_id, entity_name, event_type, source, notes),
        )
        return cur.lastrowid


def list_movements(
    entity_type: str | None = None,
    limit: int = 100,
    farm_id: int | None = None,
) -> list[dict]:
    query = """
        SELECT id, entity_type, entity_id, entity_name,
               event_type, source, detected_at, notes
        FROM movements
    """
    conditions = []
    params = []
    if farm_id is not None:
        conditions.append("farm_id=?")
        params.append(farm_id)
    if entity_type:
        conditions.append("entity_type=?")
        params.append(entity_type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
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

def get_dashboard_stats(farm_id: int | None = None) -> dict:
    fid_clause = "AND farm_id=?" if farm_id is not None else ""
    fid_params = (farm_id,) if farm_id is not None else ()

    with get_conn() as conn:
        total_animals = conn.execute(
            f"SELECT COUNT(*) FROM cattle WHERE 1=1 {fid_clause}", fid_params
        ).fetchone()[0]
        total_people = conn.execute(
            f"SELECT COUNT(*) FROM people WHERE 1=1 {fid_clause}", fid_params
        ).fetchone()[0]
        total_users = conn.execute(
            f"SELECT COUNT(*) FROM users WHERE 1=1 {fid_clause}", fid_params
        ).fetchone()[0]
        movements_today = conn.execute(
            f"SELECT COUNT(*) FROM movements WHERE date(detected_at)=date('now','localtime') {fid_clause}",
            fid_params,
        ).fetchone()[0]

        # Vacinas via JOIN para filtrar por fazenda
        if farm_id is not None:
            vaccines_upcoming = conn.execute("""
                SELECT COUNT(*) FROM vaccines v
                JOIN cattle c ON c.id = v.animal_id
                WHERE v.next_due IS NOT NULL
                  AND date(v.next_due) BETWEEN date('now') AND date('now','+30 days')
                  AND c.farm_id=?
            """, (farm_id,)).fetchone()[0]
        else:
            vaccines_upcoming = conn.execute("""
                SELECT COUNT(*) FROM vaccines
                WHERE next_due IS NOT NULL
                  AND date(next_due) BETWEEN date('now') AND date('now','+30 days')
            """).fetchone()[0]

        chart_rows = conn.execute(f"""
            SELECT
                date(detected_at,'localtime') as day,
                SUM(CASE WHEN event_type='entry' THEN 1 ELSE 0 END) as entries,
                SUM(CASE WHEN event_type='exit' THEN 1 ELSE 0 END) as exits
            FROM movements
            WHERE detected_at >= datetime('now','-7 days','localtime') {fid_clause}
            GROUP BY day
            ORDER BY day ASC
        """, fid_params).fetchall()

        fin = conn.execute(f"""
            SELECT
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) as income_month,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as expense_month
            FROM financials
            WHERE strftime('%Y-%m', occurred_at) = strftime('%Y-%m', 'now', 'localtime')
            {fid_clause}
        """, fid_params).fetchone()

        active_animals = conn.execute(
            f"SELECT COUNT(*) FROM cattle WHERE status='active' {fid_clause}", fid_params
        ).fetchone()[0]
        sold_animals = conn.execute(
            f"SELECT COUNT(*) FROM cattle WHERE status='sold' {fid_clause}", fid_params
        ).fetchone()[0]
        slaughtered_animals = conn.execute(
            f"SELECT COUNT(*) FROM cattle WHERE status='slaughtered' {fid_clause}", fid_params
        ).fetchone()[0]

        cat_rows = conn.execute(f"""
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM financials
            WHERE type='expense'
              AND strftime('%Y-%m', occurred_at) = strftime('%Y-%m', 'now', 'localtime')
              {fid_clause}
            GROUP BY category
            ORDER BY total DESC
        """, fid_params).fetchall()

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
    farm_id: int | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO financials
               (farm_id, type, category, amount, description, entity_type, entity_id,
                entity_name, occurred_at, created_by)
               VALUES (?,?,?,?,?,?,?,?,COALESCE(?,datetime('now','localtime')),?)""",
            (farm_id, type, category, amount, description, entity_type, entity_id,
             entity_name, occurred_at, created_by),
        )
        return cur.lastrowid


def list_financials(
    type: str | None = None,
    limit: int = 100,
    farm_id: int | None = None,
) -> list[dict]:
    query = """
        SELECT f.id, f.type, f.category, f.amount, f.description,
               f.entity_type, f.entity_id, f.entity_name,
               f.occurred_at, u.name as created_by_name
        FROM financials f
        LEFT JOIN users u ON u.id = f.created_by
    """
    conditions = []
    params = []
    if farm_id is not None:
        conditions.append("f.farm_id=?")
        params.append(farm_id)
    if type:
        conditions.append("f.type=?")
        params.append(type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY f.occurred_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def delete_financial(financial_id: int, farm_id: int | None = None) -> bool:
    with get_conn() as conn:
        if farm_id is not None:
            cur = conn.execute(
                "DELETE FROM financials WHERE id=? AND farm_id=?", (financial_id, farm_id)
            )
        else:
            cur = conn.execute("DELETE FROM financials WHERE id=?", (financial_id,))
    return cur.rowcount > 0


def get_financial_summary(months: int = 6, farm_id: int | None = None) -> list[dict]:
    fid_clause = "AND farm_id=?" if farm_id is not None else ""
    fid_params = (f"-{months}", farm_id) if farm_id is not None else (f"-{months}",)
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT
                strftime('%Y-%m', occurred_at, 'localtime') as month,
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as expense
            FROM financials
            WHERE occurred_at >= datetime('now', ? || ' months', 'localtime')
            {fid_clause}
            GROUP BY month
            ORDER BY month ASC
        """, fid_params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Câmeras
# ---------------------------------------------------------------------------

def add_camera(name: str, source_url: str, cam_type: str = "ip", farm_id: int | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cameras (farm_id, name, source_url, type) VALUES (?,?,?,?)",
            (farm_id, name, source_url, cam_type),
        )
        return cur.lastrowid


def get_camera(cam_id: int, farm_id: int | None = None) -> dict | None:
    with get_conn() as conn:
        if farm_id is not None:
            row = conn.execute(
                "SELECT id, farm_id, name, source_url, type, is_active, created_at "
                "FROM cameras WHERE id=? AND farm_id=?",
                (cam_id, farm_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, farm_id, name, source_url, type, is_active, created_at "
                "FROM cameras WHERE id=?",
                (cam_id,),
            ).fetchone()
    return dict(row) if row else None


def list_cameras(farm_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if farm_id is not None:
            rows = conn.execute(
                "SELECT id, farm_id, name, source_url, type, is_active, created_at "
                "FROM cameras WHERE farm_id=? ORDER BY created_at",
                (farm_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, farm_id, name, source_url, type, is_active, created_at "
                "FROM cameras ORDER BY created_at"
            ).fetchall()
    return [dict(r) for r in rows]


def update_camera(
    cam_id: int,
    name: str | None = None,
    source_url: str | None = None,
    cam_type: str | None = None,
    is_active: bool | None = None,
    farm_id: int | None = None,
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
    query = f"UPDATE cameras SET {', '.join(fields)} WHERE id=?"
    if farm_id is not None:
        query += " AND farm_id=?"
        params.append(farm_id)
    with get_conn() as conn:
        cur = conn.execute(query, params)
    return cur.rowcount > 0


def delete_camera(cam_id: int, farm_id: int | None = None) -> bool:
    with get_conn() as conn:
        if farm_id is not None:
            cur = conn.execute(
                "DELETE FROM cameras WHERE id=? AND farm_id=?", (cam_id, farm_id)
            )
        else:
            cur = conn.execute("DELETE FROM cameras WHERE id=?", (cam_id,))
    return cur.rowcount > 0
