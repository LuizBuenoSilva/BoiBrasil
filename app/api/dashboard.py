"""
app/api/dashboard.py — Estatisticas para o dashboard.
"""

from fastapi import APIRouter, Depends

import app.db.database as db
from app.api.auth import get_current_user
from app.db.schemas import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(current_user: dict = Depends(get_current_user)):
    return db.get_dashboard_stats(current_user["farm_id"])
