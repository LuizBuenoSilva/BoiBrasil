"""
ui.py — Utilitários de desenho OpenCV para o Cattle AI.

Funções para renderizar bounding boxes, labels, HUD e overlays de registro
diretamente no frame do OpenCV (in-place).
"""

import cv2
import numpy as np

from detector import Detection
from identifier import IdentityMatch

# Cores em BGR
COLOR_KNOWN = (0, 200, 0)       # Verde — animal identificado
COLOR_UNKNOWN = (0, 140, 255)   # Laranja — animal desconhecido
COLOR_REG_MODE = (220, 80, 30)  # Azul escuro — modo registro
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_YELLOW = (0, 210, 210)    # Amarelo escuro para descrição

FONT = cv2.FONT_HERSHEY_SIMPLEX


def draw_detection(
    frame: np.ndarray,
    det: Detection,
    match: IdentityMatch,
    is_registration_target: bool = False,
) -> None:
    """
    Desenha bounding box, label com similaridade e snippet de descrição no frame.

    Layout por detecção:
        [Label: "Mimosa [94.2%]"]   ← barra acima da box
        [==== bounding box ====]
        [Descrição truncada...  ]   ← abaixo da box (se disponível)
    """
    color = COLOR_KNOWN if match.is_known else COLOR_UNKNOWN
    if is_registration_target:
        color = COLOR_REG_MODE

    # Bounding box
    thickness = 3 if is_registration_target else 2
    cv2.rectangle(frame, (det.x1, det.y1), (det.x2, det.y2), color, thickness)

    # Label (nome + similaridade)
    sim_pct = f"{match.similarity * 100:.1f}%"
    label = f"{match.name} [{sim_pct}]"
    label_y = max(det.y1 - 32, 32)

    (lw, lh), baseline = cv2.getTextSize(label, FONT, 0.6, 2)
    # Fundo do label
    cv2.rectangle(
        frame,
        (det.x1, label_y - lh - baseline - 4),
        (det.x1 + lw + 8, label_y + baseline + 2),
        color,
        -1,
    )
    # Texto do label com sombra
    cv2.putText(
        frame, label,
        (det.x1 + 4, label_y - baseline),
        FONT, 0.6, COLOR_BLACK, 3,
    )
    cv2.putText(
        frame, label,
        (det.x1 + 4, label_y - baseline),
        FONT, 0.6, COLOR_WHITE, 1,
    )

    # Snippet de descrição (primeiros 65 caracteres)
    if match.description and match.is_known:
        snippet = match.description[:65]
        if len(match.description) > 65:
            snippet += "..."
        desc_y = min(det.y2 + 22, frame.shape[0] - 8)
        (dw, dh), _ = cv2.getTextSize(snippet, FONT, 0.42, 1)
        cv2.rectangle(
            frame,
            (det.x1, desc_y - dh - 4),
            (det.x1 + dw + 6, desc_y + 4),
            COLOR_BLACK,
            -1,
        )
        cv2.putText(
            frame, snippet,
            (det.x1 + 3, desc_y - 2),
            FONT, 0.42, COLOR_YELLOW, 1,
        )


def draw_registration_overlay(frame: np.ndarray, target_det: Detection) -> None:
    """
    Aplica overlay semi-transparente azul no animal alvo do registro.
    """
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (target_det.x1, target_det.y1),
        (target_det.x2, target_det.y2),
        COLOR_REG_MODE,
        -1,
    )
    cv2.addWeighted(overlay, 0.22, frame, 0.78, 0, frame)


def draw_hud(
    frame: np.ndarray,
    fps: float,
    registered_count: int,
    registration_mode: bool,
    target_index: int = 0,
    total_detections: int = 0,
) -> None:
    """
    Desenha o HUD (heads-up display) no canto superior esquerdo.

    Em modo normal: FPS, contagem de cadastrados, controles.
    Em modo registro: instruções específicas do fluxo de cadastro.
    """
    if registration_mode:
        lines = [
            ">>> MODO REGISTRO <<<",
            f"Animal selecionado: {target_index + 1}/{max(total_detections, 1)}",
            "Tab: proxima vaca  |  Enter: confirmar  |  Esc: cancelar",
        ]
        text_color = COLOR_REG_MODE
    else:
        lines = [
            f"FPS: {fps:.1f}   |   Cadastrados: {registered_count}",
            "R: registrar   Tab: selecionar   L: listar   Q: sair",
        ]
        text_color = COLOR_WHITE

    y = 28
    for line in lines:
        # Sombra preta para legibilidade
        cv2.putText(frame, line, (10, y), FONT, 0.52, COLOR_BLACK, 3)
        cv2.putText(frame, line, (10, y), FONT, 0.52, text_color, 1)
        y += 26
