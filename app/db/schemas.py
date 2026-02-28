"""
schemas.py — Modelos Pydantic para request/response da API.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """Registro de novo admin + criacao da fazenda."""
    name: str
    farm_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    role: str
    farm_id: int
    farm_name: str


class UserOut(BaseModel):
    id: int
    farm_id: int
    name: str
    email: str
    role: str
    created_at: str


class CreateUserRequest(BaseModel):
    """Criacao de usuario pelo admin da fazenda."""
    name: str
    email: EmailStr
    password: str
    role: str = "operator"


# ---------------------------------------------------------------------------
# Animals
# ---------------------------------------------------------------------------

class AnimalOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = ""
    breed: Optional[str] = ""
    weight: Optional[float] = None
    status: Optional[str] = "active"
    photo_path: Optional[str] = ""
    registered_at: str


class AnimalUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    breed: Optional[str] = None
    weight: Optional[float] = None
    status: Optional[str] = None       # active | sold | slaughtered | transferred
    sale_value: Optional[float] = None # valor da venda ou do abate


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

class PersonOut(BaseModel):
    id: int
    name: str
    role: Optional[str] = "visitor"
    description: Optional[str] = ""
    weight: Optional[float] = None
    photo_path: Optional[str] = ""
    registered_at: str


class PersonCreate(BaseModel):
    name: str
    role: Optional[str] = "visitor"
    description: Optional[str] = ""


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None


# ---------------------------------------------------------------------------
# Vaccines
# ---------------------------------------------------------------------------

class VaccineCreate(BaseModel):
    animal_id: int
    vaccine_name: str
    applied_at: str
    next_due: Optional[str] = None
    notes: Optional[str] = ""


class VaccineOut(BaseModel):
    id: int
    animal_id: int
    animal_name: str
    vaccine_name: str
    applied_at: str
    next_due: Optional[str] = None
    notes: Optional[str] = ""
    applied_by_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Movements
# ---------------------------------------------------------------------------

class MovementCreate(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    event_type: str
    source: Optional[str] = "manual"
    notes: Optional[str] = ""


class MovementOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    entity_name: str
    event_type: str
    source: str
    detected_at: str
    notes: Optional[str] = ""


# ---------------------------------------------------------------------------
# Financeiro
# ---------------------------------------------------------------------------

class FinancialCreate(BaseModel):
    type: str               # "income" | "expense"
    category: str           # "venda", "racao", "vacina", "abate", "manutencao", etc.
    amount: float
    description: Optional[str] = ""
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None
    occurred_at: Optional[str] = None


class FinancialOut(BaseModel):
    id: int
    type: str
    category: str
    amount: float
    description: Optional[str] = ""
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None
    occurred_at: str
    created_by_name: Optional[str] = None


class MonthSummary(BaseModel):
    month: str
    income: float
    expense: float


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class ActivityPoint(BaseModel):
    day: str
    entries: int
    exits: int


class CategoryBreakdown(BaseModel):
    category: str
    total: float


class DashboardStats(BaseModel):
    total_animals: int
    active_animals: int
    sold_animals: int
    slaughtered_animals: int
    total_people: int
    total_users: int
    movements_today: int
    vaccines_upcoming: int
    activity_chart: list[ActivityPoint]
    income_month: float
    expense_month: float
    balance_month: float
    expense_by_category: list[CategoryBreakdown]


# ---------------------------------------------------------------------------
# Cameras
# ---------------------------------------------------------------------------

class CameraCreate(BaseModel):
    name: str
    source_url: str
    type: Optional[str] = "ip"   # 'ip' | 'rtsp' | 'webcam'


class CameraOut(BaseModel):
    id: int
    name: str
    source_url: str
    type: str
    is_active: bool
    created_at: str


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    source_url: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None
