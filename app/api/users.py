"""
app/api/users.py — CRUD de usuarios da fazenda (apenas admin).
"""

from fastapi import APIRouter, HTTPException, Depends

import app.db.database as db
from app.api.auth import require_admin
from app.core.security import hash_password
from app.db.schemas import CreateUserRequest, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(current_user: dict = Depends(require_admin)):
    return db.list_users(current_user["farm_id"])


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: CreateUserRequest, current_user: dict = Depends(require_admin)):
    if db.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="E-mail ja cadastrado")
    if body.role not in ("admin", "operator", "viewer"):
        raise HTTPException(status_code=422, detail="Role invalido. Use: admin, operator, viewer")
    password_hash = hash_password(body.password)
    user_id = db.create_user(
        body.name, body.email, password_hash, body.role, current_user["farm_id"]
    )
    return db.get_user_by_id(user_id)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, current_user: dict = Depends(require_admin)):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Nao e possivel excluir seu proprio usuario")
    target = db.get_user_by_id(user_id)
    if not target or target.get("farm_id") != current_user["farm_id"]:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    db.delete_user(user_id)
