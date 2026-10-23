import json, numpy as np, sys
from pathlib import Path
sys.path.insert(0, 'src')
from multibot.core.vector_faq import VectorFAQ

qa_dir = Path('data/building_bot/questionsand_answers')
db_dir = Path('data/building_bot/chroma_db')
index_path = db_dir / 'faq_index.npz'

entries = json.loads((qa_dir / 'ai_learned.json').read_text())
vfaq = VectorFAQ(qa_dir=qa_dir, db_dir=db_dir)
model = vfaq._get_model()

data = np.load(index_path, allow_pickle=True)
embeddings = data['embeddings']
answers = list(data['answers'])
block_ids = list(data['block_ids']) if 'block_ids' in data else [-1] * len(answers)
group_keys = data['group_keys'] if 'group_keys' in data else np.array([], dtype=np.int32)
group_langs = data['group_langs'] if 'group_langs' in data else np.array([], dtype=object)

for entry in entries:
    q, a = entry['question'], entry['answer']
    vec = model.encode([q]).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0: vec = vec / norm
    embeddings = np.vstack([embeddings, vec])
    answers.append(a)
    block_ids.append(-1)

np.savez_compressed(index_path,
    embeddings=embeddings,
    answers=np.array(answers, dtype=object),
    block_ids=np.array(block_ids, dtype=np.int32),
    group_keys=group_keys,
    group_langs=group_langs,
)
print('Done. Total vectors:', len(answers))
