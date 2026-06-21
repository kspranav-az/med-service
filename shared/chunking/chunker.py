"""Token-aware text chunker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from shared.ingestion.base import Page
from shared.logging import get_logger
from shared.models import Chunk

logger = get_logger(__name__)


def _whitespace_tokenizer(text: str) -> list[str]:
    """Approximate tokenizer using whitespace splits.

    Used as a fallback when no HuggingFace tokenizer is provided.
    """
    return text.split()


@dataclass
class ChunkingConfig:
    """Configuration for the chunker."""

    target_tokens: int = 400
    overlap_tokens: int = 200

    def __post_init__(self) -> None:
        if self.overlap_tokens >= self.target_tokens:
            raise ValueError("overlap_tokens must be less than target_tokens")


class Chunker:
    """Split extracted pages into overlapping token-based chunks."""

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        tokenizer: Callable[[str], list[str]] | None = None,
    ) -> None:
        """Initialise the chunker.

        Args:
            config: Chunk size and overlap settings.
            tokenizer: Optional tokenizer function. Defaults to whitespace split.
        """
        self.config = config or ChunkingConfig()
        self.tokenizer = tokenizer or _whitespace_tokenizer

    def chunk_pages(
        self,
        pages: list[Page],
        source_id: str,
        start_chunk_index: int = 0,
    ) -> list[Chunk]:
        """Chunk a list of pages into overlapping text chunks.

        Args:
            pages: Pages extracted from a source.
            source_id: Source identifier for chunk IDs and metadata.
            start_chunk_index: Starting index for chunk numbering.

        Returns:
            List of Chunk objects.
        """
        chunks: list[Chunk] = []
        chunk_index = start_chunk_index
        current_tokens: list[str] = []
        current_texts: list[str] = []
        page_start: int | None = None
        page_end: int | None = None

        for page in pages:
            page_tokens = self.tokenizer(page.text)
            if not page_tokens:
                continue

            if page_start is None:
                page_start = page.page_number
            page_end = page.page_number

            current_tokens.extend(page_tokens)
            current_texts.append(page.text)

            while len(current_tokens) >= self.config.target_tokens:
                boundary = self.config.target_tokens
                chunk_tokens = current_tokens[:boundary]
                chunk_text = self._reconstruct_text(chunk_tokens)

                chunks.append(
                    Chunk(
                        chunk_id=f"{source_id}_{chunk_index:05d}",
                        source_id=source_id,
                        chunk_index=chunk_index,
                        page_number=page_start,
                        text=chunk_text,
                        token_count=len(chunk_tokens),
                        metadata={
                            "page_start": page_start,
                            "page_end": page_end,
                        },
                    )
                )
                chunk_index += 1

                # Slide window by target - overlap tokens.
                slide = max(1, self.config.target_tokens - self.config.overlap_tokens)
                current_tokens = current_tokens[slide:]

                # Rebuild current_texts so it reflects remaining tokens approximately.
                remaining_text = self._reconstruct_text(current_tokens)
                current_texts = [remaining_text] if remaining_text else []

                # Update page_start to the page of the first remaining token.
                # This is approximate; we use the last seen page if unsure.
                page_start = page.page_number if current_tokens else None

        # Flush any remaining tokens.
        if current_tokens and page_start is not None:
            chunk_text = self._reconstruct_text(current_tokens)
            chunks.append(
                Chunk(
                    chunk_id=f"{source_id}_{chunk_index:05d}",
                    source_id=source_id,
                    chunk_index=chunk_index,
                    page_number=page_start,
                    text=chunk_text,
                    token_count=len(current_tokens),
                    metadata={
                        "page_start": page_start,
                        "page_end": page_end,
                    },
                )
            )

        logger.info(
            "pages_chunked",
            extra={
                "source_id": source_id,
                "pages": len(pages),
                "chunks": len(chunks),
            },
        )
        return chunks

    def _reconstruct_text(self, tokens: list[str]) -> str:
        """Reconstruct readable text from a list of tokens."""
        return " ".join(tokens)
