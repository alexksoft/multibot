# show_learned.py
# Shows AI-learned entries (beyond base 4000) from the vector database on the server.
#
# Usage — run directly on the server (do NOT delete after running, it's a utility script):
#   scp -i %USERPROFILE%\.ssh\oracle-6gb.key show_learned.py opc@130.61.84.155:/home/opc/marketing_multibot_telegram/
#   ssh -i %USERPROFILE%\.ssh\oracle-6gb.key opc@130.61.84.155 "cd /home/opc/marketing_multibot_telegram && python3 show_learned.py"

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
