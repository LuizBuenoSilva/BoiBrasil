"""
app/api/animals.py — CRUD de animais (gado).
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse

import app.db.database as db
from app.api.auth import get_current_user
from app.db.schemas import AnimalOut, AnimalUpdate

router = APIRouter(prefix="/api/animals", tags=["animals"])


@router.get("", response_model=list[AnimalOut])
def list_animals(
    status: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    return db.list_animals(current_user["farm_id"], status)


@router.get("/{animal_id}", response_model=AnimalOut)
def get_animal(animal_id: int, current_user: dict = Depends(get_current_user)):
    animal = db.get_animal(animal_id, current_user["farm_id"])
    if not animal:
        raise HTTPException(status_code=404, detail="Animal nao encontrado")
    return animal


@router.put("/{animal_id}", response_model=AnimalOut)
def update_animal(
    animal_id: int,
    body: AnimalUpdate,
    current_user: dict = Depends(get_current_user),
):
    farm_id = current_user["farm_id"]
    previous = db.get_animal(animal_id, farm_id)
    if not previous:
        raise HTTPException(status_code=404, detail="Animal nao encontrado")

    updated = db.update_animal(
        animal_id, body.name, body.description, body.breed, body.weight, body.status, farm_id
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Animal nao encontrado")

    if body.status and body.status != previous.get("status"):
        animal_name = body.name or previous["name"]
        if body.status == "sold" and body.sale_value and body.sale_value > 0:
            db.add_financial(
                type="income",
                category="venda_animal",
                amount=body.sale_value,
                description=f"Venda do animal: {animal_name}",
                entity_type="animal",
                entity_id=animal_id,
                entity_name=animal_name,
                created_by=current_user["id"],
                farm_id=farm_id,
            )
        elif body.status == "slaughtered" and body.sale_value and body.sale_value > 0:
            db.add_financial(
                type="income",
                category="abate",
                amount=body.sale_value,
                description=f"Abate do animal: {animal_name}",
                entity_type="animal",
                entity_id=animal_id,
                entity_name=animal_name,
                created_by=current_user["id"],
                farm_id=farm_id,
            )

    return db.get_animal(animal_id, farm_id)


@router.delete("/{animal_id}", status_code=204)
def delete_animal(animal_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("admin",):
        raise HTTPException(status_code=403, detail="Apenas administradores podem excluir")
    if not db.delete_animal(animal_id, current_user["farm_id"]):
        raise HTTPException(status_code=404, detail="Animal nao encontrado")


@router.get("/{animal_id}/photo")
def animal_photo(animal_id: int):
    animal = db.get_animal(animal_id)
    if not animal or not animal.get("photo_path"):
        raise HTTPException(status_code=404, detail="Foto nao disponivel")
    return FileResponse(animal["photo_path"])
