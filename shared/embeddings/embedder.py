"""Dense embedding model wrapper using sentence-transformers."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import torch
from numpy.typing import NDArray

from shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"


def _select_device() -> str:
    """Select the best available torch device.

    Prefers MPS on Apple Silicon, falls back to CPU.
    """
    if torch.backends.mps.is_available():
        try:
            torch.zeros(1, device="mps")
            return "mps"
        except Exception as exc:  # pragma: no cover
            logger.warning("mps_probe_failed", extra={"error": str(exc)})
    return "cpu"


class Embedder:
    """Wrapper around a sentence-transformers embedding model."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
        cache_dir: Path | str | None = None,
    ) -> None:
        """Load the embedding model.

        Args:
            model_name: HuggingFace model name.
            device: Torch device override. Auto-detected if not provided.
            cache_dir: Optional local cache directory for model weights.
        """
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.device = device or _select_device()
        self.cache_dir = Path(cache_dir) if cache_dir else None

        logger.info(
            "loading_embedding_model",
            extra={
                "model": self.model_name,
                "device": self.device,
                "cache_dir": str(self.cache_dir) if self.cache_dir else None,
            },
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=str(self.cache_dir) if self.cache_dir else None,
            )

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        if hasattr(self._model, "get_embedding_dimension"):
            return int(self._model.get_embedding_dimension())
        return int(self._model.get_sentence_embedding_dimension())

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = True,
    ) -> NDArray[np.float32]:
        """Encode a list of texts into normalized dense vectors.

        Args:
            texts: Texts to embed.
            batch_size: Inference batch size.
            show_progress: Whether to show a progress bar.

        Returns:
            Array of shape ``(len(texts), dimension)`` with L2-normalized vectors.
        """
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return np.asarray(embeddings, dtype=np.float32)
