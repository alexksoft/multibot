# Marketing Multibot — Project Context

## Server
- **Host:** `opc@130.61.84.155`
- **SSH key:** `%USERPROFILE%\.ssh\oracle-6gb.key`
- **Project path:** `/home/opc/marketing_multibot_telegram/`

## Vector Database
- The vector DB is on the server, NOT local.
- **Index file:** `/home/opc/marketing_multibot_telegram/data/building_bot/chroma_db/faq_index.npz`
- Base entries: first 4000 vectors (from JSON files in `questionsand_answers/`)
- AI-learned entries: index 4000+ (saved automatically by `ai_orchestrator.py`)

## Scripts for Vector DB Operations

### Check new entries (index > 4000)
Use `show_learned.py`. Run directly on the server (do NOT delete after, it's a reusable utility):
```
scp -i %USERPROFILE%\.ssh\oracle-6gb.key show_learned.py opc@130.61.84.155:/home/opc/marketing_multibot_telegram/
ssh -i %USERPROFILE%\.ssh\oracle-6gb.key opc@130.61.84.155 "cd /home/opc/marketing_multibot_telegram && python3 show_learned.py"
```

### Remove bad entries (e.g. with ** markdown stars)
Use `fix_stars.py`. Steps:
```
scp -i %USERPROFILE%\.ssh\oracle-6gb.key fix_stars.py opc@130.61.84.155:/home/opc/marketing_multibot_telegram/
ssh -i %USERPROFILE%\.ssh\oracle-6gb.key opc@130.61.84.155 "cd /home/opc/marketing_multibot_telegram && python3 fix_stars.py && rm fix_stars.py"
```

### Remove specific entries by index
Use a custom script with the pattern from `fix_stars.py` — load npz, filter by index, savez_compressed back.
Always: only slice arrays where `len(arr) == len(answers)`. Leave `group_keys` and `group_langs` (size ~1000) untouched.

## Deploy
```
deploy.bat
```

## OS
Windows CMD only. No `tail`, `grep`, `cat`. Use `findstr`, `type`, `scp`, `ssh`.
