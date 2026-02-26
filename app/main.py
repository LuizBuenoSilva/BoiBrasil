"""
app/main.py — FastAPI application principal do Cattle AI Web.

Rodar:
  uvicorn app.main:app --reload --port 8000
"""

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import app.db.database as db
from app.api import auth, animals, people, vaccines, movements, camera, cameras, dashboard, financials
from app.api.camera import set_main_loop, start_worker
from app.core.config import BASE_DIR, PHOTOS_DIR

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

app = FastAPI(
    title="Cattle AI",
    description="Sistema de cadastro e identificação de gado em tempo real",
    version="1.0.0",
)

# CORS — permite que o frontend React (localhost:5173) acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra todos os routers
app.include_router(auth.router)
app.include_router(animals.router)
app.include_router(people.router)
app.include_router(vaccines.router)
app.include_router(movements.router)
app.include_router(camera.router)
app.include_router(cameras.router)
app.include_router(dashboard.router)
app.include_router(financials.router)

# Serve fotos estáticas (crops salvos pela câmera)
PHOTOS_DIR.mkdir(exist_ok=True)
app.mount("/photos", StaticFiles(directory=str(PHOTOS_DIR)), name="photos")

# Serve frontend React buildado (produção)
# Em dev o Vite roda separado na porta 5173; em produção servimos o dist/
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Catch-all: retorna index.html para o React Router funcionar."""
        return FileResponse(str(FRONTEND_DIST / "index.html"))


@app.on_event("startup")
async def startup():
    """Inicializa banco de dados e câmeras configuradas."""
    db.init_db()
    print("[Startup] Banco de dados inicializado.")

    # Registra o event loop para os workers de câmera
    set_main_loop(asyncio.get_event_loop())

    # Auto-inicia câmeras ativas salvas no banco
    cam_list = db.list_cameras()
    for cam in cam_list:
        if cam["is_active"]:
            start_worker(cam["id"], cam["source_url"], cam["name"])
            print(f"[Startup] Câmera iniciada: {cam['name']} ({cam['source_url']})")

    print("[Startup] Cattle AI Web pronto em http://localhost:8000")
    print("[Startup] Documentação: http://localhost:8000/docs")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Cattle AI"}
