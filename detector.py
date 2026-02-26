"""
detector.py — Detecção de gado com YOLOv8.

Filtra a classe COCO 19 (cow) para isolar apenas bovinos no frame.
"""

from dataclasses import dataclass

import numpy as np
from ultralytics import YOLO

COCO_COW_CLASS = 19  # Índice da classe "cow" no dataset COCO


@dataclass
class Detection:
    """Representa uma bounding box de gado detectado."""

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_id: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height


class CattleDetector:
    """
    Wrapper do YOLOv8 que detecta gado (COCO class 19) em frames BGR.

    Usa yolov8n.pt por padrão (rápido, 30+ FPS em CPU/GPU moderno).
    Os pesos são baixados automaticamente pelo ultralytics na primeira execução.
    """

    COW_CLASS = COCO_COW_CLASS

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.40,
        iou_threshold: float = 0.45,
        device: str = "",
    ):
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.device = device  # "" = auto-select pelo ultralytics
        self.model = YOLO(model_path)

    def detect(self, bgr_frame: np.ndarray) -> list[Detection]:
        """
        Executa inferência em um frame BGR do OpenCV.

        Retorna lista de Detection com todas as vacas encontradas.
        Lista vazia significa nenhuma vaca detectada acima do threshold.
        """
        results = self.model.predict(
            source=bgr_frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            classes=[self.COW_CLASS],
            verbose=False,
            device=self.device,
        )

        detections: list[Detection] = []
        if not results or results[0].boxes is None:
            return detections

        boxes = results[0].boxes
        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int)
            conf = float(boxes.conf[i].cpu().numpy())
            cls_id = int(boxes.cls[i].cpu().numpy())
            detections.append(
                Detection(
                    x1=int(xyxy[0]),
                    y1=int(xyxy[1]),
                    x2=int(xyxy[2]),
                    y2=int(xyxy[3]),
                    confidence=conf,
                    class_id=cls_id,
                )
            )

        return detections

    def crop(
        self,
        bgr_frame: np.ndarray,
        det: Detection,
        padding: int = 10,
    ) -> np.ndarray:
        """
        Extrai o crop do animal a partir do frame.
        Padding opcional adiciona contexto ao redor da bounding box.
        Clipa às bordas do frame para evitar índices fora dos limites.
        """
        h, w = bgr_frame.shape[:2]
        x1 = max(0, det.x1 - padding)
        y1 = max(0, det.y1 - padding)
        x2 = min(w, det.x2 + padding)
        y2 = min(h, det.y2 + padding)
        return bgr_frame[y1:y2, x1:x2].copy()
