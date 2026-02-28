"""
app/api/auth.py — Endpoints de autenticacao (login e registro).
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

import app.db.database as db
from app.core.security import hash_password, verify_password, create_token, decode_token
from app.db.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    """Dependency: valida Bearer token e retorna payload do usuario com farm_id."""
    try:
        payload = decode_token(credentials.credentials)
        user = db.get_user_by_id(int(payload["sub"]))
        if not user:
            raise HTTPException(status_code=401, detail="Usuario nao encontrado")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalido ou expirado")


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency: exige que o usuario seja administrador."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest):
    """Registra novo admin e cria sua fazenda."""
    if db.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="E-mail ja cadastrado")
    try:
        farm_id = db.create_farm(body.farm_name)
    except Exception:
        raise HTTPException(status_code=409, detail="Nome de fazenda ja cadastrado")
    password_hash = hash_password(body.password)
    user_id = db.create_user(body.name, body.email, password_hash, "admin", farm_id)
    token = create_token(user_id, body.email, "admin", farm_id)
    farm = db.get_farm_by_id(farm_id)
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        name=body.name,
        role="admin",
        farm_id=farm_id,
        farm_name=farm["name"],
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = db.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    farm_id = user.get("farm_id") or 0
    farm = db.get_farm_by_id(farm_id) if farm_id else None
    token = create_token(user["id"], user["email"], user["role"], farm_id)
    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        name=user["name"],
        role=user["role"],
        farm_id=farm_id,
        farm_name=farm["name"] if farm else "",
    )


@router.get("/me", response_model=UserOut)
def me(current_user: dict = Depends(get_current_user)):
    return current_user
