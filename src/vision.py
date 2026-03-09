import logging
import os
from pathlib import Path
from typing import Dict

# Reduz logs verbosos do OpenCV (incluindo warnings de codecs corrompidos).
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")

import cv2
import easyocr
import numpy as np

# Desativa logs desnecessários do EasyOCR no terminal
logging.getLogger('easyocr').setLevel(logging.ERROR)

try:
    # OpenCV moderno
    cv2.setLogLevel(0)
except Exception:
    try:
        # Compatibilidade com builds mais antigos
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
    except Exception:
        pass

class VisionProcessor:
    def __init__(self, profile: str | None = None):
        # Perfis para equilibrar estabilidade vs throughput.
        # stable: menor risco no Windows
        # balanced: melhor ocupacao de GPU em cenarios comuns
        # throughput: agressivo, pode variar por maquina
        p = (profile or os.getenv("OCR_PROFILE") or "stable").strip().lower()
        if p not in {"stable", "balanced", "throughput"}:
            p = "stable"
        self.profile = p

        # Nota pratica (Windows): workers>0 pode aumentar overhead e piorar taxa.
        # Mantemos workers=0 e variamos batch/downscale por perfil.
        config_map: Dict[str, Dict[str, int]] = {
            "stable": {"workers": 0, "batch_size": 1, "max_side": 0},
            "balanced": {"workers": 0, "batch_size": 2, "max_side": 1920},
            "throughput": {"workers": 0, "batch_size": 4, "max_side": 1600},
        }
        cfg = config_map[self.profile]
        self.read_workers = int(cfg["workers"])
        self.read_batch_size = int(cfg["batch_size"])
        self.max_side = int(cfg["max_side"])

        # Configuracao estavel: um reader por processo com inferencia em GPU.
        self.reader = easyocr.Reader(['pt', 'en'], gpu=True)

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        if self.max_side <= 0:
            return img

        h, w = img.shape[:2]
        side = max(h, w)
        if side <= self.max_side:
            return img

        scale = self.max_side / float(side)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def ler_imagem(self, caminho_imagem):
        try:
            # Usa decode por bytes para suportar paths Unicode no Windows.
            path = Path(caminho_imagem)
            buffer = np.fromfile(str(path), dtype=np.uint8)
            img = cv2.imdecode(buffer, cv2.IMREAD_COLOR)

            if img is None:
                return ""

            img = self._preprocess(img)

            # Lê apenas o texto (sem detalhes de posição para ser mais rápido)
            resultados = self.reader.readtext(
                img,
                detail=0,
                paragraph=False,
                workers=self.read_workers,
                batch_size=self.read_batch_size,
            )
            return " ".join(resultados)[:500]
        except Exception:
            return ""