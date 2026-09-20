"""Model type detection from tensor names and shapes."""

from sd_model_hub.core.detection.models import BASE_MODELS, MODEL_KINDS, DetectionResult
from sd_model_hub.core.detection.service import DetectionService

__all__ = ["BASE_MODELS", "MODEL_KINDS", "DetectionResult", "DetectionService"]
