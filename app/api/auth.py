"""
app/api/auth.py — Endpoints de autenticação (login e registro).
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
    """Dependency: valida Bearer token e retorna payload do usuário."""
    try:
        payload = decode_token(credentials.credentials)
        user = db.get_user_by_id(int(payload["sub"]))
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest):
    if db.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    password_hash = hash_password(body.password)
    user_id = db.create_user(body.name, body.email, password_hash, body.role or "operator")
    token = create_token(user_id, body.email, body.role or "operator")
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        name=body.name,
        role=body.role or "operator",
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = db.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    token = create_token(user["id"], user["email"], user["role"])
    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        name=user["name"],
        role=user["role"],
    )


@router.get("/me", response_model=UserOut)
def me(current_user: dict = Depends(get_current_user)):
    return current_user
