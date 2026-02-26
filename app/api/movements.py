"""
app/api/movements.py — Log de movimentações (entradas/saídas).
"""

from fastapi import APIRouter, Depends
from typing import Optional

import app.db.database as db
from app.api.auth import get_current_user
from app.db.schemas import MovementCreate, MovementOut

router = APIRouter(prefix="/api/movements", tags=["movements"])


@router.get("", response_model=list[MovementOut])
def list_movements(
    entity_type: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    return db.list_movements(entity_type, limit)


@router.post("", response_model=MovementOut, status_code=201)
def create_movement(body: MovementCreate, current_user: dict = Depends(get_current_user)):
    movement_id = db.add_movement(
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        entity_name=body.entity_name,
        event_type=body.event_type,
        source=body.source or "manual",
        notes=body.notes or "",
    )
    movements = db.list_movements(limit=1)
    return movements[0] if movements else {}
