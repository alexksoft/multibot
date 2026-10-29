import numpy as np
d = np.load('data/building_bot/chroma_db/faq_index.npz', allow_pickle=True)
questions = list(d['questions'])
answers = list(d['answers'])
print(f"Total vectors: {len(questions)}\n")
print("=== AI-learned entries (beyond base 4000) ===\n")
for i in range(4000, len(questions)):
    print(f"[{i}] Q: {questions[i]}")
    print(f"     A: {answers[i]}")
    print()
