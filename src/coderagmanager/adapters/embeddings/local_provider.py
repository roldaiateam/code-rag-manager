from __future__ import annotations


class LocalSentenceTransformerProvider:
    """Único proveedor de embeddings de la v1: modelo local ligero, sin red
    ni API key. El modelo se carga perezosamente para no penalizar los
    comandos de CLI que no embeben nada."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._load().encode(
            texts, batch_size=32, show_progress_bar=False
        ).tolist()

    def dimensions(self) -> int:
        return self._load().get_sentence_embedding_dimension()
