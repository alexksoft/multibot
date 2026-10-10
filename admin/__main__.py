"""python -m admin [hash-password <pw>]"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if len(sys.argv) >= 2 and sys.argv[1] == "hash-password":
    from admin.auth import hash_password
    pw = sys.argv[2] if len(sys.argv) > 2 else input("Password: ")
    print(hash_password(pw))
    sys.exit(0)

from src.multibot.config.settings import settings

if not settings.admin_enabled:
    print("Admin panel is disabled. Set ADMIN_ENABLED=true in .env")
    sys.exit(1)

import uvicorn
from admin.app import app

uvicorn.run(app, host=settings.admin_host, port=settings.admin_port)
