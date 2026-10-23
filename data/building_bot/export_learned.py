#!/usr/bin/env python3
"""Export all Q&A entries from faq_index.npz to export_all_data.json.

Run before deploy_rebuild_index.bat to preserve AI-learned entries.

Usage (from project root):
    python data/building_bot/export_learned.py
"""
import json
import numpy as np
from pathlib import Path

DB_DIR = Path(__file__).parent / "chroma_db"
QA_DIR = Path(__file__).parent / "questionsand_answers"
OUTPUT = QA_DIR / "export_all_data.json"

if __name__ == "__main__":
    index_path = DB_DIR / "faq_index.npz"
    data = np.load(index_path, allow_pickle=True)

    answers = list(data["answers"])
    questions = list(data["questions"]) if "questions" in data else [""] * len(answers)
    block_ids = list(data["block_ids"]) if "block_ids" in data else [-1] * len(answers)

    # Export only AI-learned entries (block_id == -1) that have a question
    entries = []
    for i, (q, a, bid) in enumerate(zip(questions, answers, block_ids)):
        q = str(q).strip()
        a = str(a).strip()
        if q and a:
            entries.append({
                "id": i + 1,
                "category": "ai_learned",
                "lang": "uk",
                "question": q,
                "answer": a,
            })

    OUTPUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(entries)} entries to {OUTPUT}")
