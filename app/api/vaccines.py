"""
app/api/vaccines.py — Registro e consulta de vacinas por animal.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

import app.db.database as db
from app.api.auth import get_current_user
from app.db.schemas import VaccineCreate, VaccineOut

router = APIRouter(prefix="/api/vaccines", tags=["vaccines"])


@router.get("", response_model=list[VaccineOut])
def list_vaccines(
    animal_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    return db.list_vaccines(animal_id, current_user["farm_id"])


@router.post("", response_model=VaccineOut, status_code=201)
def add_vaccine(body: VaccineCreate, current_user: dict = Depends(get_current_user)):
    animal = db.get_animal(body.animal_id, current_user["farm_id"])
    if not animal:
        raise HTTPException(status_code=404, detail="Animal nao encontrado")
    vaccine_id = db.add_vaccine(
        animal_id=body.animal_id,
        vaccine_name=body.vaccine_name,
        applied_at=body.applied_at,
        next_due=body.next_due,
        notes=body.notes or "",
        applied_by=current_user["id"],
    )
    vaccines = db.list_vaccines(body.animal_id, current_user["farm_id"])
    return next(v for v in vaccines if v["id"] == vaccine_id)


@router.delete("/{vaccine_id}", status_code=204)
def delete_vaccine(vaccine_id: int, current_user: dict = Depends(get_current_user)):
    if not db.delete_vaccine(vaccine_id, current_user["farm_id"]):
        raise HTTPException(status_code=404, detail="Vacina nao encontrada")


@router.get("/upcoming", response_model=list[VaccineOut])
def upcoming_vaccines(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
):
    """Vacinas com vencimento nos proximos N dias."""
    rows = db.list_upcoming_vaccines(days, current_user["farm_id"])
    return [
        {**r, "notes": "", "applied_by_name": None} for r in rows
    ]
