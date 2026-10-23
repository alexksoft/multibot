from __future__ import annotations
import json
import logging
import re
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_THRESHOLD = 0.85   # cosine similarity minimum
_INDEX_FILE = "faq_index.npz"
_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"

_UKR_LETTERS = set("іїєґ")
_RUS_LETTERS = set("ыэъё")
_SURZHYK_WORDS = {
    # --- Будівництво, ремонт та інструменти ---
    "расход", "строїтєль", "строїтєлі", "прораб", "шпатєль", "уровень", "рулєтка", 
    "краска", "красить", "покрасить", "обой", "обої", "плиточник", "кафєль", "кафєльна",
    "шпакльовка", "шпаклювать", "зашпаклювать", "грунтовка", "грунтувать", "потолок", 
    "пол", "на полу", "стєна", "стєни", "стєнка", "угловий", "угол", "угли", "проводка",
    "пóводка", "розєтка", "розєтки", "вимикач", "включатєль", "люстра", "труба", "труби",
    "сантехніка", "сантехнік", "плінтус", "плінтуса", "дира", "дири", "откос", "откоси",
    "клей", "мусор", "мусорку", "уборка", "убирать", "цемент", "раствор", "мєбєль", 
    "шафа", "диван", "двері", "дверна", "коробка", "бракодєл", "бракодєлы", "матеріал", 
    "інструмент", "інструменти", "дворнік", "дворнікі", "вилка", "каструля", "сільодка",
    "водка", "сігарєти", "рельси", "окно", "окна", "подоконник", "парапєт", "криша",

    # --- Спільні дієслова та процеси (найчастіші кальки) ---
    "дєлать", "здєлать", "получається", "получиться", "хватить", "хватає", "не хватає", 
    "ковирятися", "ковирятись", "мішати", "перемішувати", "замішувати", "сойти", "іспортить", 
    "іспортили", "ужас", "попадуться", "міняти", "поміняти", "переносити", "прикручувати", 
    "вставляти", "виносити", "вимивати", "збирати", "обмивати", "хвастатися", "клястися",
    "посчитать", "составить", "умножати", "поїхати", "накупить", "забути", "рішіть", 
    "найняти", "шукати", "ободрать", "отколупати", "вирівнювати", "зашкурить", "прорвати",
    "клеїти", "кидати", "прикрутити", "закрити", "повилазити", "відвалитися", "тріснути",

    # --- Побутові сполучники, вставні слова та прислівники ---
    "короче", "вообщє", "тіпа", "щас", "щасливо", "сразу", "по-любому", "єлє", "капєць", 
    "каждий", "кажді", "кажда", "кажде", "болєє-мєнєє", "ровненькі", "ровно", "красіво", 
    "бистріше", "зазвичай", "просто", "туди", "сюди", "зручно", "ближчі", "найближчі", 
    "більше", "нічого", "так", "як", "тоді", "оце", "оці", "шо", "шоб", "де-то", "чисто",

    # --- Числа, міри та загальні будівельні поняття ---
    "бюджет", "список", "планіровка", "магазін", "сума", "рулон", "кіло", "кілограм", 
    "квадрат", "куб", "метр", "сантиметр", "міліметр", "шаг", "зазор", "процент", 
    "проценти", "запас", "брак", "партія", "код", "колір", "цвєт", "тон", "відтінок",
    "прострочений", "обморок", "причина", "результат", "ефект", "проект", "план", "схема"
}


def detect_lang(text: str) -> str:
    """Detect language: uk / ru / en / surzhyk."""
    t = text.lower()
    cyrillic = set(re.sub(r'[^а-яіїєґёъыэ]', '', t))
    has_ukr = bool(cyrillic & _UKR_LETTERS)
    has_rus = bool(cyrillic & _RUS_LETTERS)
    if has_ukr and has_rus:
        return "surzhyk"
    words = set(re.findall(r'\b[а-яіїєґёъыэ]+\b', t))
    if words & _SURZHYK_WORDS:
        return "surzhyk"
    if has_rus and not has_ukr:
        return "ru"
    if not cyrillic:
        return "en"
    return "uk"


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

    def build(self, source_files: list[str] | None = None) -> None:
        """(Re)build the numpy index. If source_files given, index only those files (skips missing)."""
        from sentence_transformers import SentenceTransformer

        logger.info("[vector_faq] building index from %s", self._qa_dir)
        model = SentenceTransformer(_MODEL_NAME)

        questions: list[str] = []
        answers: list[str] = []
        entry_ids: list[int] = []
        langs: list[str] = []
        groups: dict[int, dict[str, str]] = {}

        if source_files:
            files = [self._qa_dir / f for f in source_files if (self._qa_dir / f).exists()]
        else:
            files = sorted(self._qa_dir.glob("*.json"))

        for json_file in files:
            try:
                entries = json.loads(json_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("[vector_faq] skip %s: %s", json_file.name, e)
                continue
            for entry in entries:
                q = entry.get("question", "").strip()
                a = entry.get("answer", "").strip()
                eid = entry.get("id")
                lang = entry.get("lang", "uk")
                if q and a:
                    questions.append(q)
                    answers.append(a)
                    entry_ids.append(eid if eid is not None else -1)
                    langs.append(lang)
                    if eid is not None:
                        groups.setdefault(eid, {})[lang] = a

        if not questions:
            logger.warning("[vector_faq] no documents found")
            return

        # Build group_id lookup: entry_id → canonical group_id (block of 4)
        # IDs are grouped as consecutive blocks: 1,2,3,4 → group 1; 5,6,7,8 → group 5
        # We store the min id of each block as group key
        group_map: dict[int, int] = {}
        for eid in groups:
            block_start = ((eid - 1) // 4) * 4 + 1
            group_map[eid] = block_start

        # Rebuild groups keyed by block_start
        canonical_groups: dict[int, dict[str, str]] = {}
        for eid, lang_answers in groups.items():
            key = group_map[eid]
            canonical_groups.setdefault(key, {}).update(lang_answers)

        # Per-vector: store block_start so we can look up the right language at query time
        block_ids = [group_map.get(eid, -1) for eid in entry_ids]

        embeddings = model.encode(questions, batch_size=64, show_progress_bar=False)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        embeddings = (embeddings / norms).astype(np.float32)

        self._db_dir.mkdir(parents=True, exist_ok=True)
        index_path = self._db_dir / _INDEX_FILE
        # answers kept for legacy fallback; also store block_ids and groups
        np.savez_compressed(
            index_path,
            embeddings=embeddings,
            answers=np.array(answers, dtype=object),
            questions=np.array(questions, dtype=object),
            block_ids=np.array(block_ids, dtype=np.int32),
            group_keys=np.array(list(canonical_groups.keys()), dtype=np.int32),
            group_langs=np.array(
                [json.dumps(v, ensure_ascii=False) for v in canonical_groups.values()],
                dtype=object,
            ),
        )
        logger.info("[vector_faq] indexed %d questions → %s", len(questions), index_path)

    def match(self, text: str) -> Optional[str]:
        """Return answer in the detected language of text, or None if below threshold."""
        if not self._ready:
            self._load()
        if self._embeddings is None:
            return None
        try:
            user_lang = detect_lang(text)
            model = self._get_model()
            vec = model.encode([text])
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            scores = self._embeddings @ vec[0]
            best_idx = int(np.argmax(scores))
            best_score = float(scores[best_idx])
            logger.debug("[vector_faq] query=%r lang=%s score=%.3f", text[:60], user_lang, best_score)
            if best_score < _THRESHOLD:
                logger.info("[vector_faq] MISS score=%.3f | q=%r", best_score, text[:60])
                return None
            # Try to return answer in user's language
            answer = self._answer_in_lang(best_idx, user_lang)
            logger.info("[vector_faq] HIT score=%.3f lang=%s | q=%r", best_score, user_lang, text[:60])
            return answer
        except Exception as e:
            logger.warning("[vector_faq] match error: %s", e)
        return None

    def _answer_in_lang(self, idx: int, lang: str) -> str:
        """Return answer for vector idx in requested lang, fallback to uk then any."""
        if self._block_ids is not None and self._groups is not None:
            block_id = int(self._block_ids[idx])
            group = self._groups.get(block_id)
            if group:
                return group.get(lang) or group.get("uk") or next(iter(group.values()))
        return self._answers[idx]

    # ── private ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        index_path = self._db_dir / _INDEX_FILE
        try:
            data = np.load(index_path, allow_pickle=True)
            self._embeddings = data["embeddings"]
            self._answers = list(data["answers"])
            self._questions = list(data["questions"]) if "questions" in data else [""] * len(self._answers)
            # Load multilingual groups if present (new format)
            if "block_ids" in data and "group_keys" in data:
                self._block_ids = data["block_ids"]
                self._groups = {
                    int(k): json.loads(v)
                    for k, v in zip(data["group_keys"], data["group_langs"])
                }
            else:
                self._block_ids = None
                self._groups = None
            self._ready = True
            logger.info("[vector_faq] loaded %d vectors from %s",
                        len(self._answers), index_path)
        except Exception as e:
            logger.warning("[vector_faq] index not found (%s) — run build first", e)
            self._ready = True

    _block_ids: Optional[np.ndarray] = None
    _groups: Optional[dict] = None
    _questions: list = []
    _model_cache = None

    def _get_model(self):
        if VectorFAQ._model_cache is None:
            from sentence_transformers import SentenceTransformer
            VectorFAQ._model_cache = SentenceTransformer(_MODEL_NAME)
        return VectorFAQ._model_cache
