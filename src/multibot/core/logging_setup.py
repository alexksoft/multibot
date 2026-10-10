import logging
import re
import os


_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)\S+", re.IGNORECASE),
    re.compile(r"(\btoken[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"(\bapi[_-]?key[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"\+?\d[\d\s\-]{8,}\d"),  # phone numbers
]


class SecretMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _mask(str(record.msg))
        record.args = tuple(_mask(str(a)) for a in record.args) if record.args else record.args
        return True


def _mask(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0)[:4] + "***", text)
    return text


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(SecretMaskingFilter())
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[handler],
    )
