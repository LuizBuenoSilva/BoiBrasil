"""
app/api/cameras.py — CRUD de câmeras e stream MJPEG por câmera.

Endpoints:
  GET    /api/cameras              — lista câmeras
  POST   /api/cameras              — adiciona câmera
  PUT    /api/cameras/{id}         — edita câmera (nome, URL, tipo, ativo)
  DELETE /api/cameras/{id}         — remove câmera
  GET    /api/cameras/{id}/stream  — MJPEG com anotações YOLO
"""

import asyncio

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

import app.db.database as db
from app.api.auth import get_current_user
from app.api.camera import get_worker, start_worker, stop_worker
from app.db.schemas import CameraCreate, CameraOut, CameraUpdate

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _no_signal_jpeg() -> bytes:
    """Frame JPEG preto exibido quando câmera está offline ou parada."""
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.putText(img, "Sem sinal", (55, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (60, 60, 60), 2)
    cv2.putText(img, "Camera offline", (55, 140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (40, 40, 40), 1)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


_PLACEHOLDER = _no_signal_jpeg()   # gerado uma vez


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CameraOut])
def list_cameras(current_user: dict = Depends(get_current_user)):
    return db.list_cameras()


@router.post("", response_model=CameraOut, status_code=201)
def add_camera(body: CameraCreate, current_user: dict = Depends(get_current_user)):
    cam_id = db.add_camera(body.name, body.source_url, body.type or "ip")
    cam = db.get_camera(cam_id)
    if cam["is_active"]:
        start_worker(cam_id, body.source_url, body.name)
    return cam


@router.put("/{cam_id}", response_model=CameraOut)
def update_camera(
    cam_id: int,
    body: CameraUpdate,
    current_user: dict = Depends(get_current_user),
):
    if not db.get_camera(cam_id):
        raise HTTPException(status_code=404, detail="Câmera não encontrada")

    db.update_camera(
        cam_id,
        name=body.name,
        source_url=body.source_url,
        cam_type=body.type,
        is_active=body.is_active,
    )
    cam = db.get_camera(cam_id)

    # Reiniciar ou parar o worker conforme is_active
    if cam["is_active"]:
        stop_worker(cam_id)
        start_worker(cam_id, cam["source_url"], cam["name"])
    else:
        stop_worker(cam_id)

    return cam


@router.delete("/{cam_id}", status_code=204)
def delete_camera(
    cam_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not db.get_camera(cam_id):
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    stop_worker(cam_id)
    db.delete_camera(cam_id)


# ---------------------------------------------------------------------------
# Stream MJPEG
# ---------------------------------------------------------------------------

@router.get("/{cam_id}/stream")
async def stream_camera(cam_id: int):
    """
    Stream MJPEG da câmera com bounding boxes do YOLO.
    Enquanto a câmera não estiver disponível, exibe frame 'Sem sinal'.
    Não requer autenticação para compatibilidade com <img src=...>.
    """
    if not db.get_camera(cam_id):
        raise HTTPException(status_code=404, detail="Câmera não encontrada")

    async def gen():
        while True:
            worker = get_worker(cam_id)
            frame  = worker.get_latest_frame() if worker else None
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                + (frame or _PLACEHOLDER)
                + b"\r\n"
            )
            await asyncio.sleep(0.033)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")
