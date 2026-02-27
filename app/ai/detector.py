"""
app/ai/detector.py — Detector dual (pessoa + animais) para o sistema web.

Classes COCO detectadas:
  - 0:  person
  - 14: bird  | 15: cat   | 16: dog   | 17: horse
  - 18: sheep | 19: cow   | 20: elephant | 21: bear
  - 22: zebra | 23: giraffe
"""

import sys
from pathlib import Path

import numpy as np
from ultralytics import YOLO

# Permite importar o dataclass Detection do módulo original
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from detector import Detection  # noqa: E402

COCO_PERSON_CLASS = 0
# Todos os animais reconhecidos pelo modelo COCO
COCO_ANIMAL_CLASSES = {14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
COCO_DETECT_CLASSES = [COCO_PERSON_CLASS] + sorted(COCO_ANIMAL_CLASSES)


class DualDetector:
    """
    Detecta pessoas e animais (gado, cães, gatos, cavalos, ovelhas, etc.)
    no mesmo frame.

    Retorna lista de Detection com campo `entity_type`:
      - class_id == 0         → entity_type = "person"
      - class_id in animais   → entity_type = "animal"
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_threshold: float = 0.40,
        iou_threshold: float = 0.45,
        device: str = "",
    ):
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.device = device
        self.model = YOLO(model_path)

    def detect(self, bgr_frame: np.ndarray) -> list[Detection]:
        """
        Detecta pessoas e animais no frame BGR.
        Retorna lista de Detection com entity_type definido.
        """
        results = self.model.predict(
            source=bgr_frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            classes=COCO_DETECT_CLASSES,
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
            det = Detection(
                x1=int(xyxy[0]),
                y1=int(xyxy[1]),
                x2=int(xyxy[2]),
                y2=int(xyxy[3]),
                confidence=conf,
                class_id=cls_id,
            )
            det.entity_type = "person" if cls_id == COCO_PERSON_CLASS else "animal"
            detections.append(det)

        return detections

    def crop(
        self,
        bgr_frame: np.ndarray,
        det: Detection,
        padding: int = 10,
    ) -> np.ndarray:
        """Recorta a região do frame com padding, clipa às bordas."""
        h, w = bgr_frame.shape[:2]
        x1 = max(0, det.x1 - padding)
        y1 = max(0, det.y1 - padding)
        x2 = min(w, det.x2 + padding)
        y2 = min(h, det.y2 + padding)
        return bgr_frame[y1:y2, x1:x2].copy()
