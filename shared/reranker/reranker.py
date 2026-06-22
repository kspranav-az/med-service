"""Cross-encoder reranker for retrieved RAG chunks.

The reranker is a two-tier component:

* Lightweight ``cross-encoder/ms-marco-MiniLM-L-6-v2`` (default) for
  fast, high-quality reranking on CPU or MPS.
* Heavyweight ``BAAI/bge-reranker-v2-m3`` for maximum accuracy when
  memory and download bandwidth are available.

Raw cross-encoder logits are mapped to ``[0, 1]`` probabilities with a
sigmoid so downstream confidence scoring is consistent with Qdrant
cosine scores.
"""

from __future__ import annotations

import math
from typing import Any

import torch
from sentence_transformers import CrossEncoder

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)

DEFAULT_RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_MODELS: dict[str, str] = {
    "minilm": DEFAULT_RERANKER,
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
}


def _select_device() -> str:
    """Select the best available torch device for the reranker.

    Prefers MPS on Apple Silicon, falls back to CPU.
    """
    if torch.backends.mps.is_available():
        try:
            torch.zeros(1, device="mps")
            return "mps"
        except Exception as exc:  # pragma: no cover
            logger.warning("reranker_mps_probe_failed", extra={"error": str(exc)})
    return "cpu"


class Reranker:
    """Cross-encoder reranker with deterministic score normalization."""

    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER,
        device: str | None = None,
        max_length: int = 512,
        batch_size: int = 16,
    ) -> None:
        """Load the cross-encoder model.

        Args:
            model_name: HuggingFace model name or alias.
            device: Torch device. Auto-detected if omitted.
            max_length: Maximum token length per query+document pair.
            batch_size: Inference batch size.
        """
        self.model_name = model_name
        self.device = device or settings.rag_reranker_device or _select_device()
        self.max_length = max_length
        self.batch_size = batch_size

        logger.info(
            "loading_reranker",
            extra={
                "model": self.model_name,
                "device": self.device,
                "max_length": self.max_length,
            },
        )

        self._model = CrossEncoder(
            self.model_name,
            device=self.device,
            max_length=self.max_length,
        )

    @staticmethod
    def _normalize_scores(scores: list[float]) -> list[float]:
        """Map raw cross-encoder logits to ``[0, 1]`` probabilities."""
        return [round(1.0 / (1.0 + math.exp(-score)), 4) for score in scores]

    def rerank(
        self,
        query: str,
        hits: list[dict[str, Any]],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Rerank retrieved hits for ``query`` and return the top-k.

        Args:
            query: User query.
            hits: Retrieved chunks from the vector store.
            top_k: Number of hits to return. Defaults to all hits.

        Returns:
            Reranked hits sorted by descending cross-encoder score. Each
            hit's ``score`` field is overwritten with the normalized
            reranker score.
        """
        if not hits:
            return []

        if top_k is None:
            top_k = len(hits)

        pairs: list[tuple[str, str]] = []
        for hit in hits:
            payload = hit.get("payload", {})
            text = payload.get("text", "") if isinstance(payload, dict) else ""
            pairs.append((query, text))

        raw_scores = self._model.predict(
            pairs,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()

        normalized = self._normalize_scores(raw_scores)
        scored = sorted(
            zip(hits, normalized, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )

        reranked: list[dict[str, Any]] = []
        for hit, score in scored[:top_k]:
            new_hit = dict(hit)
            new_hit["score"] = float(score)
            reranked.append(new_hit)

        logger.info(
            "reranked_chunks",
            extra={
                "query": query,
                "input_hits": len(hits),
                "output_hits": len(reranked),
                "model": self.model_name,
            },
        )
        return reranked


def get_reranker(name: str | None = None) -> Reranker:
    """Return a :class:`Reranker` for a configured alias or model name.

    Args:
        name: Alias (``minilm``, ``bge-reranker-v2-m3``) or a full
            HuggingFace model identifier. Defaults to the configured
            default reranker.

    Returns:
        Configured reranker instance.
    """
    resolved = RERANKER_MODELS.get(name or "", name) or settings.rag_default_reranker
    return Reranker(model_name=resolved)
