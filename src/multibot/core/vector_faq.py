from __future__ import annotations
import json
import logging
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_THRESHOLD = 0.88   # cosine similarity minimum
_INDEX_FILE = "faq_index.npz"
_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"


class VectorFAQ:
    """FAQ search via sentence-transformers + numpy cosine similarity.

    No chromadb required — index stored as a plain .npz file.
    Lazy-loaded on first match() call.
    """

    def __init__(self, qa_dir: str | Path, db_dir: str | Path):
        self._qa_dir = Path(qa_dir)
        self._db_dir = Path(db_dir)
        self._embeddings: Optional[np.ndarray] = None  # (N, D) float32
        self._answers: list[str] = []
        self._ready = False

    # ── public ────────────────────────────────────────────────────────────────

    def build(self) -> None:
        """(Re)build the numpy index from all JSON files in qa_dir."""
        from sentence_transformers import SentenceTransformer

        logger.info("[vector_faq] building index from %s", self._qa_dir)
        model = SentenceTransformer(_MODEL_NAME)

        questions: list[str] = []
        answers: list[str] = []

        for json_file in sorted(self._qa_dir.glob("*.json")):
            try:
                entries = json.loads(json_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("[vector_faq] skip %s: %s", json_file.name, e)
                continue
            for entry in entries:
                q = entry.get("question", "").strip()
                a = entry.get("answer", "").strip()
                if q and a:
                    questions.append(q)
                    answers.append(a)

        if not questions:
            logger.warning("[vector_faq] no documents found")
            return

        embeddings = model.encode(questions, batch_size=64, show_progress_bar=False)
        # L2-normalise so dot product == cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        embeddings = (embeddings / norms).astype(np.float32)

        self._db_dir.mkdir(parents=True, exist_ok=True)
        index_path = self._db_dir / _INDEX_FILE
        np.savez_compressed(
            index_path,
            embeddings=embeddings,
            answers=np.array(answers, dtype=object),
        )
        logger.info("[vector_faq] indexed %d questions → %s", len(questions), index_path)

    def match(self, text: str) -> Optional[str]:
        """Return answer string if similarity >= threshold, else None."""
        if not self._ready:
            self._load()
        if self._embeddings is None:
            return None
        try:
            model = self._get_model()
            vec = model.encode([text])
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            scores = self._embeddings @ vec[0]   # dot product = cosine similarity
            best_idx = int(np.argmax(scores))
            best_score = float(scores[best_idx])
            logger.debug("[vector_faq] query=%r score=%.3f", text[:60], best_score)
            if best_score >= _THRESHOLD:
                logger.info("[vector_faq] HIT score=%.3f | q=%r", best_score, text[:60])
                return self._answers[best_idx]
            else:
                logger.info("[vector_faq] MISS score=%.3f | q=%r", best_score, text[:60])
        except Exception as e:
            logger.warning("[vector_faq] match error: %s", e)
        return None

    # ── private ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        index_path = self._db_dir / _INDEX_FILE
        try:
            data = np.load(index_path, allow_pickle=True)
            self._embeddings = data["embeddings"]          # (N, D) float32
            self._answers = list(data["answers"])
            self._ready = True
            logger.info("[vector_faq] loaded %d vectors from %s",
                        len(self._answers), index_path)
        except Exception as e:
            logger.warning("[vector_faq] index not found (%s) — run build first", e)
            self._ready = True  # don't retry on every call

    _model_cache = None

    def _get_model(self):
        if VectorFAQ._model_cache is None:
            from sentence_transformers import SentenceTransformer
            VectorFAQ._model_cache = SentenceTransformer(_MODEL_NAME)
        return VectorFAQ._model_cache
