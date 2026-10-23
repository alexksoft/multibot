import numpy as np
from pathlib import Path

index_path = Path('data/building_bot/chroma_db/faq_index.npz')
data = np.load(index_path, allow_pickle=True)

answers = list(data['answers'])
questions = list(data['questions']) if 'questions' in data.files else [''] * len(answers)
block_ids = list(data['block_ids']) if 'block_ids' in data.files else [-1] * len(answers)
group_keys = data['group_keys'] if 'group_keys' in data.files else np.array([], dtype=np.int32)
group_langs = data['group_langs'] if 'group_langs' in data.files else np.array([], dtype=object)

BAD_PHRASES = ['недоступний', 'тимчасово', 'Вибачте, AI', 'не вдалося отримати']

bad = [(i, str(questions[i])[:80], str(answers[i])[:80])
       for i in range(len(answers))
       if any(p in str(answers[i]) for p in BAD_PHRASES)]

print(f"Found {len(bad)} bad entries:")
for i, q, a in bad:
    print(f"  [{i}] Q={q!r} A={a!r}")

if bad:
    keep = [i for i in range(len(answers)) if i not in {b[0] for b in bad}]
    new_embeddings = data['embeddings'][keep]
    new_answers = np.array([answers[i] for i in keep], dtype=object)
    new_questions = np.array([questions[i] for i in keep], dtype=object)
    new_block_ids = np.array([block_ids[i] for i in keep], dtype=np.int32)
    np.savez_compressed(index_path,
        embeddings=new_embeddings,
        answers=new_answers,
        questions=new_questions,
        block_ids=new_block_ids,
        group_keys=group_keys,
        group_langs=group_langs,
    )
    print(f"Removed {len(bad)} bad entries. Vectors: {len(answers)} -> {len(keep)}")
else:
    print("No bad entries found.")
