#!/usr/bin/env python3
"""Build (or rebuild) the ChromaDB vector index from all Q&A JSON files.

Usage (run from project root):
    python data/building_bot/build_vector_kb.py

Run again any time you add more JSON files — it rebuilds from scratch.
"""
import sys
from pathlib import Path

# allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from multibot.core.vector_faq import VectorFAQ

QA_DIR = Path(__file__).parent / "questionsand_answers"
DB_DIR = Path(__file__).parent / "chroma_db"

if __name__ == "__main__":
    DB_DIR.mkdir(parents=True, exist_ok=True)
    vfaq = VectorFAQ(qa_dir=QA_DIR, db_dir=DB_DIR)
    vfaq.build()
    print("Done. Index stored in:", DB_DIR)
