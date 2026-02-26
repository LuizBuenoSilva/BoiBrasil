"""
embedder.py — Extração de embeddings visuais com EfficientNet-B0.

Remove o classificador e usa a saída do avgpool (1280-dim) como
vetor de features L2-normalizado para comparação por cosine similarity.
"""

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms
from torchvision.models import EfficientNet_B0_Weights

EMBEDDING_DIM = 1280  # Dimensão de saída do avgpool do EfficientNet-B0


class CattleEmbedder:
    """
    Extrai embeddings L2-normalizados de 1280-dim de imagens de gado
    usando EfficientNet-B0 sem o classificador.

    O modelo é carregado uma vez e mantido em modo eval.
    Usa GPU (CUDA) se disponível, caso contrário CPU.
    """

    def __init__(self, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._build_model()
        self._build_transform()

    def _build_model(self) -> None:
        weights = EfficientNet_B0_Weights.DEFAULT
        base = models.efficientnet_b0(weights=weights)
        # Substituir classificador por Identity para obter saída 1280-dim
        # O forward() do EfficientNet chama: classifier(avgpool(features(x)).flatten(1))
        # Com Identity, o vetor 1280-dim é retornado diretamente.
        base.classifier = nn.Identity()
        self.model = base.to(self.device)
        self.model.eval()

    def _build_transform(self) -> None:
        # Pré-processamento oficial do EfficientNet-B0 (ImageNet)
        self.transform = transforms.Compose([
            transforms.Resize(
                256, interpolation=transforms.InterpolationMode.BICUBIC
            ),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    @torch.no_grad()
    def extract(self, pil_image: Image.Image) -> np.ndarray:
        """
        Args:
            pil_image: Imagem PIL RGB (crop do animal).
        Returns:
            Vetor float32 L2-normalizado de shape (1280,).
        """
        tensor = self.transform(pil_image).unsqueeze(0).to(self.device)
        features = self.model(tensor)  # (1, 1280)
        vec = features.squeeze().cpu().numpy().astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec = vec / norm
        return vec

    def extract_from_bgr(self, bgr_crop: np.ndarray) -> np.ndarray:
        """
        Aceita crop BGR do OpenCV (HxWxC uint8).
        Converte para PIL RGB e chama extract().
        """
        import cv2
        rgb = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        return self.extract(pil)
