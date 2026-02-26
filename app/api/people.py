"""
app/api/people.py — CRUD de pessoas detectadas na fazenda.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse

import app.db.database as db
from app.api.auth import get_current_user
from app.db.schemas import PersonOut, PersonUpdate

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("", response_model=list[PersonOut])
def list_people(current_user: dict = Depends(get_current_user)):
    return db.list_people()


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, current_user: dict = Depends(get_current_user)):
    person = db.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    return person


@router.put("/{person_id}", response_model=PersonOut)
def update_person(
    person_id: int,
    body: PersonUpdate,
    current_user: dict = Depends(get_current_user),
):
    updated = db.update_person(person_id, body.name, body.role, body.description)
    if not updated:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    return db.get_person(person_id)


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("admin",):
        raise HTTPException(status_code=403, detail="Apenas administradores podem excluir")
    if not db.delete_person(person_id):
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")


@router.get("/{person_id}/photo")
def person_photo(person_id: int):
    person = db.get_person(person_id)
    if not person or not person.get("photo_path"):
        raise HTTPException(status_code=404, detail="Foto não disponível")
    return FileResponse(person["photo_path"])
