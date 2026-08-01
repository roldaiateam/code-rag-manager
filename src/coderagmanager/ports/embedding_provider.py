from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    def dimensions(self) -> int: ...
