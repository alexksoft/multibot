from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from threading import Thread

logger = logging.getLogger(__name__)

_HEADER = ["timestamp", "bot_name", "user_id", "direction", "flow_id", "step_id", "text"]
_ws_cache: dict[str, object] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _get_worksheet(sheet_id: str, creds_path: str, ws_name: str):
    key = f"{sheet_id}:{ws_name}"
    if key in _ws_cache:
        return _ws_cache[key]
    if not sheet_id or not creds_path or not os.path.exists(creds_path):
        return None
    try:
        import gspread
        gc = gspread.service_account(filename=creds_path)
        spreadsheet = gc.open_by_key(sheet_id)
        try:
            ws = spreadsheet.worksheet(ws_name)
        except Exception:
            ws = spreadsheet.add_worksheet(title=ws_name, rows=1000, cols=len(_HEADER))
            ws.append_row(_HEADER)
        _ws_cache[key] = ws
        return ws
    except Exception as e:
        logger.warning(f"[dialog_log] Cannot open worksheet '{ws_name}': {e}")
        return None


def _write(bot_name: str, user_id: int, direction: str, text: str,
           flow_id: str, step_id: str, sheet_id: str, creds_path: str) -> None:
    try:
        ws = _get_worksheet(sheet_id, creds_path, f"log_{bot_name}")
        if ws is None:
            return
        ws.append_row([_utcnow(), bot_name, str(user_id), direction, flow_id, step_id, text[:500]])
    except Exception as e:
        logger.warning(f"[dialog_log] skip ({bot_name}): {e}")


def log_message(
    bot_name: str,
    user_id: int,
    direction: str,
    text: str,
    flow_id: str = "",
    step_id: str = "",
    *,
    enabled: bool = True,
    sheet_id: str = "",
    creds_path: str = "",
) -> None:
    if not enabled:
        return
    Thread(
        target=_write,
        args=(bot_name, user_id, direction, text, flow_id, step_id, sheet_id, creds_path),
        daemon=True,
    ).start()
