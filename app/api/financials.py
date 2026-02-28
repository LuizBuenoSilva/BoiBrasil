"""
app/api/financials.py — Controle financeiro da fazenda (receitas e despesas).
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

import app.db.database as db
from app.api.auth import get_current_user
from app.db.schemas import FinancialCreate, FinancialOut, MonthSummary

router = APIRouter(prefix="/api/financials", tags=["financials"])

CATEGORIES_INCOME  = ["venda_animal", "abate", "leite", "servico", "subsidio", "outros_entrada"]
CATEGORIES_EXPENSE = ["racao", "vacina", "medicamento", "manutencao", "funcionario",
                      "energia", "transporte", "equipamento", "outros_saida"]


@router.get("", response_model=list[FinancialOut])
def list_financials(
    type: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    return db.list_financials(type, limit, current_user["farm_id"])


@router.post("", response_model=FinancialOut, status_code=201)
def add_financial(body: FinancialCreate, current_user: dict = Depends(get_current_user)):
    if body.type not in ("income", "expense"):
        raise HTTPException(status_code=422, detail="type deve ser 'income' ou 'expense'")
    if body.amount <= 0:
        raise HTTPException(status_code=422, detail="amount deve ser positivo")

    farm_id = current_user["farm_id"]
    fin_id = db.add_financial(
        type=body.type,
        category=body.category,
        amount=body.amount,
        description=body.description or "",
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        entity_name=body.entity_name,
        occurred_at=body.occurred_at,
        created_by=current_user["id"],
        farm_id=farm_id,
    )
    records = db.list_financials(limit=200, farm_id=farm_id)
    return next(r for r in records if r["id"] == fin_id)


@router.delete("/{fin_id}", status_code=204)
def delete_financial(fin_id: int, current_user: dict = Depends(get_current_user)):
    if not db.delete_financial(fin_id, current_user["farm_id"]):
        raise HTTPException(status_code=404, detail="Registro nao encontrado")


@router.get("/summary", response_model=list[MonthSummary])
def financial_summary(
    months: int = 6,
    current_user: dict = Depends(get_current_user),
):
    return db.get_financial_summary(months, current_user["farm_id"])


@router.get("/categories")
def get_categories(current_user: dict = Depends(get_current_user)):
    return {"income": CATEGORIES_INCOME, "expense": CATEGORIES_EXPENSE}
