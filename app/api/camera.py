"""
app/api/camera.py — Pipeline multi-câmera com CameraWorker.

Cada câmera roda em thread dedicada com YOLO + EfficientNet.
Deduplicação em duas camadas:
  1. _reg_lock + DEDUP_GUARD (0.60): check+register atômico, protege multi-câmera.
  2. Buffer por câmera (10 s / BUFFER_SIM 0.68): bloqueia re-cadastro em frames consecutivos.
"""

import asyncio
import random
import threading
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import app.db.database as db
from app.ai.analyzer import get_analyzer
from app.ai.detector import DualDetector
from app.ai.embedder import get_embedder
from app.ai.identifier import DualIdentifier, IdentityMatch, UNKNOWN_LABEL
from app.core.config import DETECTION_CONF, PHOTOS_DIR, SIMILARITY_THRESHOLD, YOLO_MODEL

router = APIRouter(prefix="/api/camera", tags=["camera"])

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
IDENTIFY_THRESHOLD = SIMILARITY_THRESHOLD   # 0.75
DEDUP_GUARD        = 0.60
BUFFER_TTL         = 10.0
BUFFER_SIM         = 0.68

# ---------------------------------------------------------------------------
# Nomes aleatórios
# ---------------------------------------------------------------------------
_CATTLE_NAMES = [
    "Mimosa", "Estrela", "Pintada", "Moreninha", "Branquinha", "Caramelo",
    "Pretinha", "Malhada", "Formosa", "Bonita", "Clarinha", "Rosinha",
    "Serena", "Vitória", "Aurora", "Bela", "Doce", "Flor", "Graça", "Hera",
    "Trovão", "Valente", "Bravo", "Capitão", "Guerreiro", "Forte", "Titã",
    "Rei", "Jaguar", "Sultan", "Barroso", "Manchado", "Pintado", "Gaúcho",
    "Cangaço", "Sertão", "Pampa", "Cerrado", "Chapadão", "Vaqueiro",
]
_VISITOR_PREFIXES = ["Visitante", "Funcionario", "Convidado", "Colaborador"]
_used_cattle_names: set[str] = set()
_visitor_counters: dict[str, int] = {}


def _random_cattle_name() -> str:
    available = [n for n in _CATTLE_NAMES if n not in _used_cattle_names]
    base = random.choice(available) if available else f"Boi_{random.randint(100, 999)}"
    name = base
    suffix = 2
    while db.animal_exists(name):
        name = f"{base}_{suffix}"
        suffix += 1
    _used_cattle_names.add(name)
    return name


def _auto_visitor_name() -> str:
    prefix = random.choice(_VISITOR_PREFIXES)
    _visitor_counters[prefix] = _visitor_counters.get(prefix, 0) + 1
    name = f"{prefix}_{_visitor_counters[prefix]:03d}"
    suffix = 2
    while db.person_exists(name):
        name = f"{prefix}_{_visitor_counters[prefix]:03d}_{suffix}"
        suffix += 1
    return name


# ---------------------------------------------------------------------------
# Estado global
# ---------------------------------------------------------------------------
_ws_clients: list[WebSocket] = []
_workers: dict[int, "CameraWorker"] = {}
_workers_lock = threading.Lock()
_seen_today: dict[tuple, str] = {}
_seen_lock = threading.Lock()
_reg_lock = threading.Lock()       # atomiza check+register entre câmeras
_identifier: DualIdentifier | None = None
_main_loop: asyncio.AbstractEventLoop | None = None
_no_photo: set[tuple[str, int]] = set()   # (entity_type, entity_id) sem foto
_no_photo_lock = threading.Lock()


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def _load_no_photo() -> None:
    """Popula _no_photo com IDs de entidades que ainda não têm foto."""
    missing = db.list_ids_without_photo()
    with _no_photo_lock:
        _no_photo.clear()
        for aid in missing["animals"]:
            _no_photo.add(("animal", aid))
        for pid in missing["people"]:
            _no_photo.add(("person", pid))


def get_identifier() -> DualIdentifier:
    global _identifier
    if _identifier is None:
        _identifier = DualIdentifier(threshold=IDENTIFY_THRESHOLD)
        _identifier.load_animals(db.load_all_animals_with_embeddings())
        _identifier.load_people(db.load_all_people_with_embeddings())
        _load_no_photo()
    return _identifier


def reload_identifier() -> None:
    global _identifier
    if _identifier is not None:
        _identifier.load_animals(db.load_all_animals_with_embeddings())
        _identifier.load_people(db.load_all_people_with_embeddings())
    _load_no_photo()


# ---------------------------------------------------------------------------
# Gerenciamento de workers (chamado de cameras.py)
# ---------------------------------------------------------------------------

def start_worker(cam_id: int, source_url: str, cam_name: str = "") -> None:
    """Inicia (ou reinicia) o worker de uma câmera."""
    with _workers_lock:
        if cam_id in _workers:
            _workers[cam_id].stop()
        identifier = get_identifier()
        w = CameraWorker(cam_id, source_url, cam_name, identifier)
        w.start()
        _workers[cam_id] = w


def stop_worker(cam_id: int) -> None:
    """Para e remove o worker de uma câmera."""
    with _workers_lock:
        w = _workers.pop(cam_id, None)
    if w:
        w.stop()


def get_worker(cam_id: int) -> "CameraWorker | None":
    with _workers_lock:
        return _workers.get(cam_id)


def stop_all_workers() -> None:
    with _workers_lock:
        for w in _workers.values():
            w.stop()
        _workers.clear()


# ---------------------------------------------------------------------------
# Deduplicação
# ---------------------------------------------------------------------------

def _is_duplicate(embedding: np.ndarray, entity_type: str, identifier: DualIdentifier) -> bool:
    bank = identifier._animals if entity_type == "animal" else identifier._people
    if not bank:
        return False
    matrix = np.stack([bank[n]["embedding"] for n in bank], axis=0)
    return float(np.max(matrix @ embedding)) >= DEDUP_GUARD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_crop(crop_bgr: np.ndarray, name: str) -> str:
    PHOTOS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    path = PHOTOS_DIR / f"{safe}_{ts}.jpg"
    cv2.imwrite(str(path), crop_bgr)
    return str(path)


def _extract_breed(description: str) -> str:
    for breed in ["Nelore", "Angus", "Hereford", "Brahman", "Gir", "Guzerá",
                  "Simmental", "Charolês", "Limousin", "Zebu", "Holstein", "Girolando"]:
        if breed.lower() in description.lower():
            return breed
    return ""


def _auto_register(
    worker: "CameraWorker",
    crop_bgr: np.ndarray,
    embedding: np.ndarray,
    entity_type: str,
) -> dict | None:
    """
    Registra entidade nova de forma atômica (com _reg_lock).
    Retorna dict do evento ou None se duplicata detectada.
    """
    with _reg_lock:
        if worker._is_in_buffer(embedding) or _is_duplicate(embedding, entity_type, worker.identifier):
            return None

        name        = _random_cattle_name() if entity_type == "animal" else _auto_visitor_name()
        analyzer    = get_analyzer()
        analysis    = analyzer.analyze(crop_bgr) if analyzer.available else {}
        description = analysis.get("description", "")
        breed       = analysis.get("breed", "") or _extract_breed(description)
        weight      = analysis.get("weight")
        photo_path  = _save_crop(crop_bgr, name)

        try:
            if entity_type == "animal":
                entity_id = db.register_animal(name, embedding, description, photo_path,
                                               breed=breed, weight=weight)
                worker.identifier.add_animal(entity_id, name, embedding, description)
            else:
                entity_id = db.register_person(name, embedding, role="visitor",
                                               description=description, photo_path=photo_path)
                worker.identifier.add_person(entity_id, name, embedding, description)

            source = f"camera_{worker.cam_id}"
            db.add_movement(entity_type, entity_id, name, "entry", source)
            with _seen_lock:
                _seen_today[(entity_type, entity_id)] = datetime.now().date().isoformat()
            worker._reg_buffer.append((embedding.copy(), time.time()))

            return {
                "event":       "auto_registered",
                "entity_type": entity_type,
                "entity_id":   entity_id,
                "name":        name,
                "description": description,
                "photo_path":  photo_path,
                "camera_id":   worker.cam_id,
                "camera_name": worker.cam_name,
            }
        except Exception as e:
            print(f"[Camera {worker.cam_id}] Auto-cadastro falhou: {e}")
            return None


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

async def _broadcast(event: dict) -> None:
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


def _broadcast_from_thread(event: dict) -> None:
    """Agenda broadcast no event loop principal a partir de uma thread."""
    if _main_loop and not _main_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_broadcast(event), _main_loop)


# ---------------------------------------------------------------------------
# Anotação
# ---------------------------------------------------------------------------

def _annotate(frame: np.ndarray, detections: list, matches: list) -> np.ndarray:
    display = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    for det, match in zip(detections, matches):
        et = getattr(det, "entity_type", "animal")
        color = ((0, 200, 0) if et == "animal" else (200, 130, 0)) if match.is_known else (0, 140, 255)
        cv2.rectangle(display, (det.x1, det.y1), (det.x2, det.y2), color, 2)
        label = f"{match.name} [{match.similarity * 100:.0f}%]"
        ly = max(det.y1 - 10, 20)
        (lw, lh), _ = cv2.getTextSize(label, font, 0.55, 1)
        cv2.rectangle(display, (det.x1, ly - lh - 4), (det.x1 + lw + 4, ly + 2), color, -1)
        cv2.putText(display, label, (det.x1 + 2, ly - 2), font, 0.55, (255, 255, 255), 1)
    ts = datetime.now().strftime("%H:%M:%S")
    cv2.putText(display, f"Cattle AI | {ts}", (10, 22), font, 0.55, (0, 0, 0), 3)
    cv2.putText(display, f"Cattle AI | {ts}", (10, 22), font, 0.55, (255, 255, 255), 1)
    return display


# ---------------------------------------------------------------------------
# CameraWorker
# ---------------------------------------------------------------------------

class CameraWorker:
    """Thread dedicada a uma câmera: captura, detecção e auto-cadastro."""

    def __init__(
        self,
        cam_id: int,
        source_url: str,
        cam_name: str,
        identifier: DualIdentifier,
    ) -> None:
        self.cam_id     = cam_id
        self.source_url = source_url
        self.cam_name   = cam_name
        self.identifier = identifier
        self._lock      = threading.Lock()
        self._latest_frame: bytes | None = None
        self._running   = False
        self._thread: threading.Thread | None = None
        self._reg_buffer: deque[tuple[np.ndarray, float]] = deque(maxlen=50)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name=f"cam-{self.cam_id}", daemon=True
        )
        self._thread.start()
        print(f"[Camera {self.cam_id}] Worker iniciado → {self.source_url}")

    def stop(self) -> None:
        self._running = False
        print(f"[Camera {self.cam_id}] Worker parado.")

    def get_latest_frame(self) -> bytes | None:
        with self._lock:
            return self._latest_frame

    def _set_frame(self, frame_bytes: bytes) -> None:
        with self._lock:
            self._latest_frame = frame_bytes

    def _is_in_buffer(self, embedding: np.ndarray) -> bool:
        now = time.time()
        for prev_emb, ts in self._reg_buffer:
            if now - ts <= BUFFER_TTL and float(np.dot(prev_emb, embedding)) >= BUFFER_SIM:
                return True
        return False

    def _open_capture(self) -> cv2.VideoCapture:
        src = self.source_url
        cap = cv2.VideoCapture(int(src) if src.isdigit() else src)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _loop(self) -> None:
        detector = DualDetector(model_path=YOLO_MODEL, conf_threshold=DETECTION_CONF)
        embedder = get_embedder()
        cap: cv2.VideoCapture | None = None

        while self._running:
            # --- Abrir / reconectar ---
            if cap is None or not cap.isOpened():
                if cap:
                    cap.release()
                try:
                    cap = self._open_capture()
                except Exception as e:
                    print(f"[Camera {self.cam_id}] Erro ao abrir: {e}")
                    time.sleep(3.0)
                    continue
                if not cap.isOpened():
                    print(f"[Camera {self.cam_id}] Não foi possível conectar: {self.source_url}")
                    time.sleep(3.0)
                    continue

            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            try:
                detections = detector.detect(frame)
                matches: list[IdentityMatch] = []
                pending_events = []

                for det in detections:
                    et = getattr(det, "entity_type", "animal")
                    crop = detector.crop(frame, det, padding=10)
                    if crop.size == 0 or min(crop.shape[:2]) < 20:
                        matches.append(IdentityMatch(
                            name=UNKNOWN_LABEL, entity_id=-1, similarity=0.0, is_known=False
                        ))
                        continue

                    emb   = embedder.extract_from_bgr(crop)
                    match = self.identifier.identify(emb, et)
                    matches.append(match)

                    if not match.is_known:
                        event = _auto_register(self, crop, emb, et)
                        if event:
                            pending_events.append(event)
                    else:
                        key   = (et, match.entity_id)
                        today = datetime.now().date().isoformat()
                        with _seen_lock:
                            if _seen_today.get(key) != today:
                                db.add_movement(
                                    et, match.entity_id, match.name,
                                    "entry", f"camera_{self.cam_id}"
                                )
                                _seen_today[key] = today

                        # Salva foto automaticamente se entidade ainda não tem
                        with _no_photo_lock:
                            needs_photo = key in _no_photo
                        if needs_photo:
                            photo_path = _save_crop(crop, match.name)
                            if et == "animal":
                                db.update_animal_photo(match.entity_id, photo_path)
                            else:
                                db.update_person_photo(match.entity_id, photo_path)
                            with _no_photo_lock:
                                _no_photo.discard(key)
                            print(f"[Camera {self.cam_id}] Foto salva para {match.name}: {photo_path}")

                annotated = _annotate(frame, detections, matches)
                _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
                self._set_frame(buf.tobytes())

                for ev in pending_events:
                    _broadcast_from_thread(ev)

            except Exception as e:
                print(f"[Camera {self.cam_id}] Erro no loop: {e}")

            time.sleep(0.033)   # ~30 fps cap

        if cap:
            cap.release()


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------

@router.websocket("/events")
async def camera_events(websocket: WebSocket):
    """WebSocket que recebe eventos de auto-cadastro de todas as câmeras."""
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


@router.post("/reload")
async def reload_models():
    reload_identifier()
    return {"status": "reloaded"}
